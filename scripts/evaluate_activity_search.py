"""Run frozen Gemini activity queries through the real API and worker, unpaid only."""

import argparse
import fcntl
import hashlib
import json
import math
import os
import statistics
import subprocess
import sys
import tempfile
import time
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace


class EvaluationLimitReached(RuntimeError):
    """A dispatch was prevented; completed model work remains usable."""


def save_report(output, report):
    """Replace atomically so interruption cannot erase reserved dispatches."""
    with tempfile.NamedTemporaryFile(
        mode="w", dir=output.parent, prefix=output.name + ".", delete=False
    ) as stream:
        temporary = Path(stream.name)
        try:
            stream.write(json.dumps(report, indent=2) + "\n")
            stream.flush()
            os.fsync(stream.fileno())
        except BaseException:
            temporary.unlink(missing_ok=True)
            raise
    try:
        os.replace(temporary, output)
        directory = os.open(output.parent, os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        temporary.unlink(missing_ok=True)


class EvaluationBudget:
    def __init__(self, output, report, max_attempts, max_seconds):
        if type(max_attempts) is not int or max_attempts < 0:
            raise ValueError("Generation-attempt limit must be a nonnegative integer")
        if not math.isfinite(max_seconds) or max_seconds < 0:
            raise ValueError("Video-second limit must be finite and nonnegative")
        self.output, self.report = output, report
        limits = {
            "max_generation_attempts": max_attempts,
            "max_video_seconds": max_seconds,
        }
        state = report.get("evaluation_budget")
        if state is None:
            if output.exists():
                raise ValueError("Historical report has no dispatch ledger; choose a new output file")
            state = report["evaluation_budget"] = {
                **limits, "generation_attempts": 0, "supplied_video_seconds": 0.0,
            }
        if any(state.get(k) != value for k, value in limits.items()):
            raise ValueError("Evaluation limits changed; choose a new output file")
        attempts, seconds = state.get("generation_attempts"), state.get("supplied_video_seconds")
        if (
            type(attempts) is not int or attempts < 0 or attempts > max_attempts
            or type(seconds) not in (int, float) or not math.isfinite(seconds)
            or seconds < 0 or seconds > max_seconds
        ):
            raise ValueError("Invalid persisted dispatch ledger; choose a new output file")
        self.state = state
        self.stopped = None

    def reserve(self, seconds):
        """Persist before SDK entry, including failed calls and application retries.

        A crash between this write and SDK entry conservatively consumes a slot.
        The configured SDK disables its internal retries; this counts SDK calls.
        """
        if not math.isfinite(seconds) or seconds < 0:
            raise ValueError("Cannot account for supplied video")
        if self.state["generation_attempts"] >= self.state["max_generation_attempts"]:
            self.stopped = "max_generation_attempts"
        elif self.state["supplied_video_seconds"] + seconds > self.state["max_video_seconds"]:
            self.stopped = "max_video_seconds"
        if self.stopped:
            self.report["evaluation_stop"] = {
                "reason": self.stopped,
                "blocked_request_video_seconds": seconds,
            }
            save_report(self.output, self.report)
            raise EvaluationLimitReached(self.stopped)
        self.state["generation_attempts"] += 1
        self.state["supplied_video_seconds"] += seconds
        save_report(self.output, self.report)


@contextmanager
def observe_dispatches(ai, grounding, budget, counts, fps):
    """Observe this runner only; never mutate provider/product behavior on disk."""
    original_client, original_clip = ai.embedding_client, grounding.verification_clip
    durations = {}

    def observed_clip(proxy, start, end):
        video = original_clip(proxy, start, end)
        digest = hashlib.sha256(video).digest()
        durations[digest] = max(durations.get(digest, 0), (end - start) / fps)
        return video

    def video_seconds(contents):
        total = 0
        for part in contents:
            if isinstance(part, str):
                continue
            nested = getattr(part, "parts", None)
            if nested is not None:
                total += video_seconds(nested)
                continue
            blob = getattr(part, "inline_data", None)
            if blob and str(getattr(blob, "mime_type", "")).startswith("video/"):
                digest = hashlib.sha256(blob.data).digest()
                if digest not in durations:
                    raise ValueError("Unaccounted video part; evaluation dispatch refused")
                total += durations[digest]
            elif getattr(part, "file_data", None):
                raise ValueError("Unaccounted file part; evaluation dispatch refused")
            elif blob or not isinstance(getattr(part, "text", None), str):
                raise ValueError("Unaccounted content part; evaluation dispatch refused")
        return total

    def observed_client():
        client = original_client()
        # Capture bound SDK methods once: wrappers must never invoke themselves.
        embed_content, generate_content = client.models.embed_content, client.models.generate_content

        def embed(**kwargs):
            counts["embedding_requests"] += 1
            return embed_content(**kwargs)

        def generate(**kwargs):
            budget.reserve(video_seconds(kwargs.get("contents", [])))
            counts["video_requests"] += 1
            return generate_content(**kwargs)

        return SimpleNamespace(
            models=SimpleNamespace(embed_content=embed, generate_content=generate),
            close=client.close,
        )

    grounding.verification_clip, ai.embedding_client = observed_clip, observed_client
    try:
        yield
    finally:
        grounding.verification_clip, ai.embedding_client = original_clip, original_client


def hit(candidate, target):
    if candidate["asset_id"] != target["asset_id"]:
        return False
    left, right = candidate["start_frame"] / 30, candidate["end_frame"] / 30
    start, end = target["start_sec"], target["end_sec"]
    overlap = max(0, min(right, end) - max(left, start))
    if target.get("label_type") == "presence":
        return overlap / max(1 / 30, right - left) >= 0.9
    return overlap / max(1 / 30, max(right, end) - min(left, start)) >= 0.5


def score(rows, key):
    expected = {row["id"]: row for row in key["queries"]}
    positive = [r for r in rows if expected[r["id"]]["kind"] != "negative"]
    negative = [r for r in rows if expected[r["id"]]["kind"] == "negative"]

    def matches(row, first=False):
        results = row.get("results", [])[: 1 if first else 5]
        return any(hit(c, t) for c in results for t in expected[row["id"]]["relevant"])

    returned = [r for r in rows if r.get("results")]
    durations = [r for r in positive if expected[r["id"]].get("requested_duration_sec")]
    boundaries = []
    for r in positive:
        for c in r.get("results", [])[:1]:
            for t in expected[r["id"]]["relevant"]:
                if t.get("activity_kind") == "discrete" and hit(c, t):
                    boundaries.append(
                        max(
                            abs(c["start_frame"] / 30 - t["start_sec"]),
                            abs(c["end_frame"] / 30 - t["end_sec"]),
                        )
                    )
                    break
    return {
        "queries_completed": len(rows),
        "positive_queries": len(positive),
        "negative_queries": len(negative),
        "top5_relevant": sum(matches(r) for r in positive),
        "top1_relevant": sum(matches(r, True) for r in positive),
        "returned_first_precision": {
            "correct": sum(matches(r, True) for r in returned),
            "returned": len(returned),
        },
        "negative_false_returns": sum(bool(r.get("results")) for r in negative),
        "provider_or_validation_errors": sum(
            bool(r.get("error"))
            or r.get("inspection_status") in ("failed", "cancelled")
            or r.get("status", {}).get("checked_candidates", 5) < 5
            for r in rows
        ),
        "duration_queries": len(durations),
        "duration_fulfilled_with_relevant_cut": sum(
            any(
                hit(c, t)
                and c["end_frame"] - c["start_frame"]
                == round(expected[r["id"]]["requested_duration_sec"] * 30)
                for c in r.get("results", [])
                for t in expected[r["id"]]["relevant"]
            )
            for r in durations
        ),
        "median_discrete_boundary_error_sec": statistics.median(boundaries)
        if boundaries
        else None,
        "boundary_labels_matched": len(boundaries),
        "p50_total_seconds": statistics.median(r["total_seconds"] for r in rows)
        if rows
        else None,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root", type=Path, default=Path("data/evaluation/gemini-fresh")
    )
    parser.add_argument("--output", type=Path)
    parser.add_argument("--ids", help="Optional development subset, comma separated")
    parser.add_argument("--allow-free-gemini", action="store_true")
    parser.add_argument("--max-generation-attempts", type=int, default=40)
    parser.add_argument("--max-video-seconds", type=float, default=1500)
    args = parser.parse_args()
    if not args.allow_free_gemini:
        parser.error("Explicit --allow-free-gemini is required")
    root = args.root.resolve()
    key_bytes = (root / "answer-key-frozen-v1.json").read_bytes()
    key = json.loads((root / "answer-key-mapped-v1.json").read_text())
    os.environ["STORYROOM_DATA"] = str(root / "session")
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from fastapi.testclient import TestClient

    from server import ai, config, db, grounding, worker
    from server.app import app

    if config.VISUAL_TIER != "unpaid" or not config.visual_ai_ready():
        parser.error(
            "Configure existing unpaid Gemini access; this runner never enables paid access"
        )
    output = args.output or root / "activity-validation.json"
    identity = {
        "code_revision": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], text=True
        ).strip(),
        "embedding_model": config.EMBED_MODEL,
        "verifier_model": config.VISUAL_VERIFIER_MODEL,
        "frozen_key_sha256": hashlib.sha256(key_bytes).hexdigest(),
        "data_dir": str(config.DATA),
    }
    selected = set(args.ids.split(",")) if args.ids else None
    counts = {}
    # One isolated runner owns this report; a second process must not race its ledger.
    with output.with_name(output.name + ".lock").open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            parser.error("Another evaluation owns this output file")
        report = {**identity, "queries": []}
        if output.exists():
            report = json.loads(output.read_text())
            if any(report.get(k) != value for k, value in identity.items()):
                parser.error("Evidence identity changed; choose a new output file")
        try:
            budget = EvaluationBudget(
                output, report, args.max_generation_attempts, args.max_video_seconds
            )
        except ValueError as exc:
            parser.error(str(exc))
        done = {q["id"] for q in report["queries"]}
        run_queries(app, TestClient, ai, config, db, grounding, worker,
                    output, report, budget, counts, done, selected, key)


def run_queries(app, TestClient, ai, config, db, grounding, worker,
                output, report, budget, counts, done, selected, key):
    if prior := report.pop("in_progress_query", None):
        report.setdefault("interrupted_queries", []).append(prior)
    report.pop("evaluation_stop", None)
    intended = [row["id"] for row in key["queries"] if selected is None or row["id"] in selected]
    with observe_dispatches(ai, grounding, budget, counts, config.FPS), TestClient(
        app, headers={"X-Storyroom": "local"}
    ) as client:
        for row in key["queries"]:
            if row["id"] in done or selected is not None and row["id"] not in selected:
                continue
            counts.update(embedding_requests=0, video_requests=0)
            started = time.perf_counter()
            item = {"id": row["id"], "query": row["query"], "results": []}
            report["in_progress_query"] = item
            save_report(output, report)
            try:
                response = client.post(
                    f"/api/projects/{row['project_id']}/search",
                    json={"query": row["query"], "mode": "visual", "grounded": True},
                )
                response.raise_for_status()
                body = response.json()
                item.update(
                    results=body.pop("results"),
                    status=body,
                    initial_seconds=time.perf_counter() - started,
                )
                save_report(output, report)
                if job_id := body.get("activity_job_id"):
                    # This isolated runner owns its worker; the interactive app
                    # must not use the same evaluation data directory concurrently.
                    while (
                        db.one("SELECT status FROM jobs WHERE id=?", (job_id,))[
                            "status"
                        ]
                        == "queued"
                    ):
                        if not worker.once():
                            break
                    job = db.one("SELECT * FROM jobs WHERE id=?", (job_id,))
                    saved = json.loads(job["result"] or "{}")
                    item.update(
                        results=saved.get("visual_results", item["results"]),
                        inspection_status=job["status"],
                        inspection_message=job["message"],
                        continuation_diagnostics=saved.get(
                            "inspection_diagnostics", {}
                        ),
                    )
            except Exception as exc:  # noqa: BLE001 - retain every failed query in evaluation
                item["error"] = type(exc).__name__
            item.update(counts, total_seconds=time.perf_counter() - started)
            if budget.stopped:
                item["evaluation_stopped"] = budget.stopped
            report["queries"].append(item)
            report.pop("in_progress_query", None)
            finished = {q["id"] for q in report["queries"] if not q.get("evaluation_stopped")}
            report["unfinished_query_ids"] = [ident for ident in intended if ident not in finished]
            report["evaluation_complete"] = not report["unfinished_query_ids"]
            report["summary"] = score(report["queries"], key)
            save_report(output, report)
            print(
                json.dumps(
                    {k: v for k, v in item.items() if k not in ("results", "status")}
                ),
                flush=True,
            )
            if budget.stopped:
                break
    print(json.dumps(report.get("summary", score(report["queries"], key)), indent=2))


if __name__ == "__main__":
    main()
