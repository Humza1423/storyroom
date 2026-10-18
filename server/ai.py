"""Cloud adapters, tier-specific readiness checks, caching, and request reservations."""

import hashlib
import json
import logging
import math
import os
import re
from typing import Protocol

from . import config, db
from .media import verification_clip
from .models import VisualVerdict

log = logging.getLogger("storyroom.ai")


class VisualProviderError(RuntimeError):
    """A provider failure with a deliberately limited, safe-to-display summary."""

    def __init__(self, message, status_code=None, provider_status=None):
        super().__init__(message)
        self.safe_message = message
        self.code = status_code
        self.status_code = status_code
        self.provider_status = provider_status


def _safe_provider_error(exc):
    """Extract useful provider diagnostics without logging request data/secrets."""
    status_code = getattr(exc, "code", None)
    if not isinstance(status_code, int):
        status_code = getattr(exc, "status_code", None)
    if not isinstance(status_code, int):
        status_code = None

    provider_status = getattr(exc, "status", None)
    if not isinstance(provider_status, str):
        provider_status = None
    else:
        provider_status = re.sub(r"[^A-Za-z0-9_.-]", "", provider_status)[:64]

    # google-genai exposes the response's message separately. Avoid serializing
    # `details`, the response object, or the complete exception representation.
    message = getattr(exc, "message", None)
    if not isinstance(message, str) or not message.strip():
        message = str(exc)
    message = " ".join(message.split())
    message = re.sub(r"AIza[0-9A-Za-z_-]{20,}", "[REDACTED_KEY]", message)
    message = re.sub(
        r"(?i)(api[_ -]?key|authorization|bearer)(\s*[:=]\s*|\s+)[^\s,;]+",
        r"\1\2[REDACTED]",
        message,
    )
    message = re.sub(r"/(?:Users|private|tmp)/[^\s,'\"]+", "[REDACTED_PATH]", message)
    message = message[:400]
    if not message:
        message = "Provider returned no error message."

    parts = ["Gemini video verifier request failed"]
    if status_code is not None:
        parts[-1] += f" (HTTP {status_code}"
        if provider_status:
            parts[-1] += f", {provider_status}"
        parts[-1] += ")"
    elif provider_status:
        parts[-1] += f" ({provider_status})"
    return f"{parts[0]}: {message}", status_code, provider_status


def estimate(seconds=0, text_chars=0, output_tokens=4096):
    # Deliberately conservative video token allowance at 2 fps, including overhead.
    input_tokens = math.ceil(seconds * 2 * 350 + text_chars + 2000)
    return round(
        (input_tokens * config.INPUT_RATE + output_tokens * config.OUTPUT_RATE)
        / 1_000_000,
        6,
    )


def client():
    if not config.ai_ready():
        raise ValueError(
            "Set GEMINI_API_KEY and confirm model prices in .env, then restart. Manual tools work without AI."
        )
    from google import genai
    from google.genai import types

    return genai.Client(
        api_key=os.environ["GEMINI_API_KEY"],
        http_options=types.HttpOptions(
            timeout=120_000, retry_options=types.HttpRetryOptions(attempts=1)
        ),
    )


def embedding_client():
    if not config.visual_ai_ready():
        if not os.getenv("GEMINI_API_KEY"):
            raise ValueError("Set GEMINI_API_KEY before using visual search.")
        if config.VISUAL_TIER == "unpaid":
            raise ValueError(
                "Acknowledge the Gemini unpaid-service data terms before visual search."
            )
        raise ValueError("Confirm Gemini pricing before using paid visual search.")
    from google import genai
    from google.genai import types

    return genai.Client(
        api_key=os.environ["GEMINI_API_KEY"],
        http_options=types.HttpOptions(
            timeout=120_000, retry_options=types.HttpRetryOptions(attempts=1)
        ),
    )


def complete(job_id, prompt, schema, video=None, seconds=0):
    from google.genai import types

    key = hashlib.sha256(
        (
            config.MODEL
            + config.PROMPT_VERSION
            + prompt
            + (hashlib.sha256(video).hexdigest() if video else "")
        ).encode()
    ).hexdigest()
    cached = db.cache_get(key)
    if cached is not None:
        return schema.model_validate(cached)
    api = client()
    reservation = db.reserve(job_id, config.MODEL, estimate(seconds, len(prompt)))
    try:
        contents = [prompt]
        if video:
            contents.insert(
                0,
                types.Part(
                    inline_data=types.Blob(data=video, mime_type="video/mp4"),
                    video_metadata=types.VideoMetadata(fps=2),
                ),
            )
        response = api.models.generate_content(
            model=config.MODEL,
            contents=contents,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=schema,
                max_output_tokens=4096,
                temperature=0.2,
            ),
        )
        usage = response.usage_metadata
        if usage:
            amount = (
                (usage.prompt_token_count or 0) * config.INPUT_RATE
                + (
                    (usage.candidates_token_count or 0)
                    + (usage.thoughts_token_count or 0)
                )
                * config.OUTPUT_RATE
            ) / 1e6
            db.execute(
                "UPDATE usage SET actual=?,status='settled' WHERE id=?",
                (amount, reservation),
            )
        else:
            db.execute(
                "UPDATE usage SET status='unconfirmed' WHERE id=?", (reservation,)
            )
        parsed = schema.model_validate_json(response.text or "")
        db.cache_set(key, parsed.model_dump())
        return parsed
    except Exception:
        # A timeout may still have incurred provider charges. Retain its reservation.
        db.execute(
            "UPDATE usage SET status='unconfirmed' WHERE id=? AND actual IS NULL",
            (reservation,),
        )
        raise
    finally:
        api.close()


def embedding_key(text):
    return (
        "embedding:" + hashlib.sha256((config.EMBED_MODEL + text).encode()).hexdigest()
    )


def cached_embedding(text):
    return db.cache_get(embedding_key(text))


def embed(text, job_id=None):
    key = embedding_key(text)
    cached = db.cache_get(key)
    if cached is not None:
        return cached
    api = client()
    reservation = db.reserve(
        job_id, config.EMBED_MODEL, (len(text) + 100) * config.EMBED_RATE / 1e6
    )
    try:
        from google.genai import types

        result = api.models.embed_content(
            model=config.EMBED_MODEL,
            contents=text,
            config=types.EmbedContentConfig(output_dimensionality=768),
        )
        values = result.embeddings[0].values
        norm = math.sqrt(sum(v * v for v in values)) or 1
        values = [v / norm for v in values]
        # Keep conservative reservation where SDK does not provide token usage.
        db.execute("UPDATE usage SET status='estimated' WHERE id=?", (reservation,))
        db.cache_set(key, values)
        return values
    except Exception:
        db.execute("UPDATE usage SET status='unconfirmed' WHERE id=?", (reservation,))
        raise
    finally:
        api.close()


class EmbeddingProvider(Protocol):
    """Capability boundary for cross-modal clip-to-text retrieval."""

    provider: str
    model: str

    def embed_video_range(self, content: bytes, cache_fingerprint: str, job_id: str):
        ...

    def embed_text_query(self, query: str, job_id: str | None = None):
        ...


def _normalized_vector(values):
    if values is None or len(values) != config.EMBED_DIMENSIONS:
        raise ValueError(
            f"Embedding provider returned an invalid vector; expected {config.EMBED_DIMENSIONS} values."
        )
    values = [float(value) for value in values]
    if not all(math.isfinite(value) for value in values):
        raise ValueError("Embedding provider returned non-finite values.")
    norm = math.sqrt(sum(value * value for value in values))
    if not norm:
        raise ValueError("Embedding provider returned a zero vector.")
    return [value / norm for value in values]


class GeminiEmbeddingProvider:
    provider = "gemini"
    model = config.EMBED_MODEL

    def _embed(self, contents, cache_key, job_id, reserve_amount):
        key = "visual-embedding:" + hashlib.sha256(cache_key.encode()).hexdigest()
        cached = db.cache_get(key)
        if cached is not None:
            return cached
        api = embedding_client()
        reservation = None
        try:
            reservation = db.reserve(job_id, self.model, reserve_amount)
            from google.genai import types

            result = api.models.embed_content(
                model=self.model,
                contents=contents,
                config=types.EmbedContentConfig(
                    output_dimensionality=config.EMBED_DIMENSIONS
                ),
            )
            embeddings = getattr(result, "embeddings", None) or []
            values = _normalized_vector(
                embeddings[0].values if embeddings else None
            )
            # EmbedContent does not return token usage. Keep the published
            # per-frame/list-price reservation for both tiers: Storyroom cannot
            # verify the provider project's billing status, even when the local
            # setting says "unpaid". The UI can still show the free-tier price.
            db.execute(
                "UPDATE usage SET status='estimated' WHERE id=?",
                (reservation,),
            )
            db.cache_set(key, values)
            return values
        except Exception:
            if reservation:
                db.execute(
                    "UPDATE usage SET status='unconfirmed' WHERE id=? AND actual IS NULL",
                    (reservation,),
                )
            raise
        finally:
            api.close()

    def embed_video_range(self, content: bytes, cache_fingerprint: str, job_id: str):
        from google.genai import types

        cache_key = (
            f"{self.provider}:{self.model}:{config.EMBED_DIMENSIONS}:"
            f"{config.VISUAL_INDEX_VERSION}:{cache_fingerprint}"
        )
        # The API samples clips of this duration at 1 fps. Keep the charge
        # reservation at the published per-frame list price, even in free mode.
        duration_frames = int(cache_fingerprint.rsplit(":", 1)[-1])
        frame_count = max(1, math.ceil(duration_frames / config.FPS))
        return self._embed(
            types.Part.from_bytes(data=content, mime_type="video/mp4"),
            cache_key,
            job_id,
            frame_count * config.VISUAL_VIDEO_FRAME_RATE,
        )

    def embed_text_query(self, query: str, job_id: str | None = None):
        if not query.strip():
            raise ValueError("Enter a search phrase first.")

        prepared = f"task: search result | query: {query.strip()}"
        cache_key = (
            f"{self.provider}:{self.model}:{config.EMBED_DIMENSIONS}:query:{prepared}"
        )
        estimated_tokens = max(1, math.ceil(len(prepared) / 4))
        return self._embed(
            prepared,
            cache_key,
            job_id,
            estimated_tokens * config.EMBED_RATE / 1_000_000,
        )


def embedding_provider() -> EmbeddingProvider:
    if config.EMBED_PROVIDER == "gemini":
        return GeminiEmbeddingProvider()
    raise ValueError(f"Unsupported embedding provider: {config.EMBED_PROVIDER}")


VISUAL_VERIFIER_VERSION = "visual-verifier-v1-3fps"


def visual_verifier_cache_key(query, proxy_hash, start_frame, end_frame):
    normalized_query = " ".join(query.lower().split())
    cache_input = json.dumps(
        [VISUAL_VERIFIER_VERSION, config.VISUAL_VERIFIER_MODEL, normalized_query, proxy_hash,
         start_frame, end_frame], separators=(",", ":"),
    )
    return "visual-verdict:" + hashlib.sha256(cache_input.encode()).hexdigest()


def verify_visual_match(query, proxy, proxy_hash, start_frame, end_frame):
    """Ask a video model whether this exact range visibly satisfies the query.

    An embedding score only nominates this range. No model-generated confidence
    is interpreted as a calibrated probability.
    """
    key = visual_verifier_cache_key(query, proxy_hash, start_frame, end_frame)
    cached = db.cache_get(key)
    if cached is not None:
        return VisualVerdict.model_validate(cached)

    video = verification_clip(proxy, start_frame, end_frame)
    from google.genai import types

    prompt = (
        "Judge whether the requested visible action or object is actually in this "
        "short unlabeled video. Use only visual evidence in the video, not likely "
        "associations with the setting or equipment. Similar exercises do not count. "
        "For an action, require visible body movement that identifies that action; "
        "a person merely holding equipment or standing in a related pose does not "
        "count. If the video is too short or unclear, choose uncertain. "
        "Choose match only if you can name concrete visible evidence. "
        "Keep visible_evidence brief; leave it empty for no_match or uncertain. "
        f"Requested footage: {query.strip()}"
    )
    duration = (end_frame - start_frame) / config.FPS
    # Conservative list-price reservation, including sampled frames and output.
    input_tokens = math.ceil(duration * 3 * 350 + len(prompt) + 2000)
    reserved_cost = (
        input_tokens * config.VISUAL_VERIFIER_INPUT_RATE
        + 768 * config.VISUAL_VERIFIER_OUTPUT_RATE
    ) / 1_000_000
    reservation = db.reserve(None, config.VISUAL_VERIFIER_MODEL, reserved_cost)
    api = None
    try:
        api = embedding_client()
        response = api.models.generate_content(
            model=config.VISUAL_VERIFIER_MODEL,
            contents=[
                types.Part(
                    inline_data=types.Blob(data=video, mime_type="video/mp4"),
                    video_metadata=types.VideoMetadata(fps=3),
                ),
                prompt,
            ],
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema={
                    "type": "OBJECT",
                    "properties": {
                        "decision": {
                            "type": "STRING",
                            "enum": ["match", "no_match", "uncertain"],
                        },
                        "visible_evidence": {"type": "STRING"},
                    },
                    "required": ["decision", "visible_evidence"],
                },
                max_output_tokens=768,
                temperature=0,
            ),
        )
        usage = response.usage_metadata
        if usage:
            amount = (
                (usage.prompt_token_count or 0) * config.VISUAL_VERIFIER_INPUT_RATE
                + ((usage.candidates_token_count or 0) + (usage.thoughts_token_count or 0))
                * config.VISUAL_VERIFIER_OUTPUT_RATE
            ) / 1e6
            db.execute(
                "UPDATE usage SET actual=?,status='settled' WHERE id=?",
                (amount, reservation),
            )
        else:
            db.execute("UPDATE usage SET status='unconfirmed' WHERE id=?", (reservation,))
        verdict = VisualVerdict.model_validate_json(response.text or "")
        db.cache_set(key, verdict.model_dump())
        return verdict
    except Exception as exc:
        # A rejected request (bad schema, quota) cannot have generated tokens;
        # a timeout may have, so retain its reservation instead.
        safe_message, code, provider_status = _safe_provider_error(exc)
        log.warning(
            "Visual verifier provider failure model=%s http_status=%s provider_status=%s message=%s",
            config.VISUAL_VERIFIER_MODEL,
            code if code is not None else "unknown",
            provider_status or "unknown",
            safe_message,
        )
        if code in (400, 401, 403, 404, 429):
            db.execute(
                "UPDATE usage SET actual=0,status='rejected' WHERE id=?",
                (reservation,),
            )
        else:
            db.execute(
                "UPDATE usage SET status='unconfirmed' WHERE id=? AND actual IS NULL",
                (reservation,),
            )
        raise VisualProviderError(safe_message, code, provider_status) from exc
    finally:
        if api is not None:
            api.close()
