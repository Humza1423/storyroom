"""Cloud boundary. No request is made without key, confirmed pricing, and a reservation."""

import hashlib
import math
import os
from . import config, db


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
