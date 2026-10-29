"""Query-aware activity inspection, separate from accepted board selections.

Embeddings find anchors. Grounded video evidence supplies activity intervals.
Continuation is resumable worker work; incomplete bounds remain explicit.
"""

import copy
import hashlib
import json

from . import config, db, grounding, media
from .localization import candidate_context

VERSION = "activity-v5-short-stop-recheck"
CHUNK = 30 * config.FPS
OVERLAP = 4 * config.FPS


def _merge_diagnostics(totals, current):
    """Keep usage totals, but only the five most recent inspection details."""
    for key in (
        "cache_hits",
        "request_attempts",
        "retries",
        "submitted_video_seconds",
        "elapsed_seconds",
        "input_tokens",
        "output_tokens",
        "thinking_tokens",
        "estimated_usd",
        "error_count",
    ):
        totals[key] = totals.get(key, 0) + current.get(key, 0)
    for key in ("candidates", "errors"):
        totals[key] = (totals.get(key, []) + current.get(key, []))[-5:]
    for key in (
        "error_code",
        "contract_version",
        "model",
        "returned_model_version",
        "batch_fingerprint",
    ):
        if current.get(key) is not None:
            totals[key] = current[key]
    totals["usage_available"] = totals.get("usage_available", False) or current.get(
        "usage_available", False
    )


def suggested_cut(interval, intent, requested=None):
    left, right = interval["start_frame"], interval["end_frame"]
    if intent == "specific_move" and requested is None:
        return left, right
    if requested is None:
        return (
            max(left, interval.get("suggested_start_frame", left)),
            min(right, interval.get("suggested_end_frame", min(right, left + 150))),
        )
    length = requested or 5 * config.FPS
    start = max(
        left,
        min(
            interval.get("suggested_start_frame", left),
            right - min(length, right - left),
        ),
    )
    return start, min(right, start + length)


def _refresh(candidate):
    activity = candidate["activity"]
    activity["complete"] = not (
        activity["continues_before"]
        or activity["continues_after"]
        or activity.get("boundary_conflict_before", False)
        or activity.get("boundary_conflict_after", False)
    )
    start, end = suggested_cut(
        activity, activity["intent"], activity["requested_frames"]
    )
    candidate.update(start_frame=start, end_frame=end)
    activity["duration_fulfilled"] = (
        activity["requested_frames"] is None
        or end - start == activity["requested_frames"]
    )
    return candidate


def distinct_activities(candidates):
    """Suppress duplicate grounded views, never union uninspected gaps."""
    kept = []
    for candidate in candidates:
        a = candidate["activity"]
        duplicate = None
        for prior in kept:
            b = prior["activity"]
            overlap = min(a["end_frame"], b["end_frame"]) - max(
                a["start_frame"], b["start_frame"]
            )
            shorter = min(
                a["end_frame"] - a["start_frame"], b["end_frame"] - b["start_frame"]
            )
            if (
                candidate["asset_id"] == prior["asset_id"]
                and overlap / max(1, shorter) >= 0.8
            ):
                duplicate = prior
                break
        if duplicate is None:
            kept.append(candidate)
        elif a["complete"] and not duplicate["activity"]["complete"]:
            # Replace a partial view, rather than stretching two ranges together.
            index = kept.index(duplicate)
            candidate["id"] = duplicate["id"]
            candidate["activity"]["id"] = duplicate["activity"]["id"]
            kept[index] = candidate
    for rank, candidate in enumerate(kept, 1):
        candidate["rank"] = rank
    return kept


def _result(query, candidate, interval, verdict, occurrence):
    # The combined inspection interprets the query once. A numeric phrase may
    # describe the action itself; a regex must not override its explicit null.
    seconds = verdict["requested_duration_seconds"]
    requested = max(1, round(seconds * config.FPS)) if seconds is not None else None
    intent = verdict["intent"]
    ident = hashlib.sha256(
        f"{VERSION}:{query}:{candidate['asset_id']}:{interval['start_frame']}:{occurrence}".encode()
    ).hexdigest()[:24]
    activity = {
        **interval,
        "id": ident,
        "intent": intent,
        "requested_frames": requested,
    }
    return _refresh(
        {
            **candidate,
            "id": "activity-" + ident,
            "kind": "visual",
            "media_url": f"/api/assets/{candidate['asset_id']}/proxy",
            "activity": activity,
        }
    )


def inspect_candidates(project_id, query, shortlist, frames, hashes, status):
    specs = []
    for index, hit in enumerate(shortlist):
        context = candidate_context(
            f"c{index}",
            config.asset_dir(hit["asset_id"]) / "proxy.mp4",
            hashes[hit["asset_id"]],
            hit["start_frame"],
            hit["end_frame"],
            frames[hit["asset_id"]],
        )
        specs.append(
            (
                context.candidate_id,
                context.proxy,
                context.proxy_hash,
                context.anchor_start,
                context.anchor_end,
                context.asset_frames,
                context.context_start,
                context.context_end,
            )
        )
    diagnostics = {}
    verdicts, error = grounding.inspect_ranges(query, specs, diagnostics=diagnostics)
    status["inspection_diagnostics"] = diagnostics
    candidates = []
    for spec, hit in zip(specs, shortlist, strict=True):
        verdict = verdicts.get(spec[0])
        if verdict and verdict["decision"] == "match":
            for index, interval in enumerate(verdict["intervals"]):
                result = _result(query, hit, interval, verdict, index)
                result.pop("score", None)
                candidates.append(result)
    candidates = distinct_activities(candidates)[:5]
    status["checked_candidates"] = len(verdicts)
    status["pipeline"] = VERSION
    status["incomplete"] = bool(error) or len(verdicts) < len(specs)
    if error:
        status["warning"] = "Inspection incomplete: " + getattr(
            error, "safe_message", "Video inspection failed; retry later."
        )
    if status.get("has_more"):
        status["incomplete"] = True
        status["warning"] = " ".join(
            filter(
                None,
                [
                    status.get("warning"),
                    "Only the first five candidate locations on this page were checked. Check more moments if needed.",
                ],
            )
        )
    if any(not c["activity"]["complete"] for c in candidates):
        # Snapshot proposals only. Continuation never edits an accepted cut.
        payload = {
            "query": query,
            "candidates": candidates,
            "contract_version": grounding.VERSION,
            "continuation_contract_version": grounding.CONTINUATION_VERSION,
        }
        previous = db.one(
            "SELECT id,status,result FROM jobs WHERE project_id=? AND kind='activity_inspect' "
            "AND payload=? AND status IN ('done','failed','cancelled') ORDER BY created DESC LIMIT 1",
            (project_id, json.dumps(payload, sort_keys=True)),
        )
        if previous and previous["result"]:
            retained = json.loads(previous["result"])["visual_results"]
            partial = any(not c["activity"]["complete"] for c in retained)
            status["incomplete"] = (
                bool(error) or bool(status.get("has_more")) or partial
            )
            if partial:
                status["activity_job_id"] = previous["id"]
                for candidate in retained:
                    if not candidate["activity"]["complete"]:
                        candidate["activity"]["inspection_job_id"] = previous["id"]
                if previous["status"] in ("failed", "cancelled"):
                    status["warning"] = " ".join(
                        filter(
                            None,
                            [
                                status.get("warning"),
                                "Previous activity inspection stopped. Confirmed footage remains available; open Activity to retry.",
                            ],
                        )
                    )
            return retained
        job_id = db.enqueue(project_id, "activity_inspect", payload)
        status["activity_job_id"] = job_id
        status["incomplete"] = True
        for candidate in candidates:
            if not candidate["activity"]["complete"]:
                candidate["activity"]["inspection_job_id"] = job_id
    return candidates


def continue_inspection(job, cancelled, progress):
    """Inspect adjacent chunks serially; persist after every completed request."""
    payload = json.loads(job["payload"])
    saved = json.loads(job["result"]) if job.get("result") else {}
    candidates = copy.deepcopy(saved.get("visual_results", payload["candidates"]))
    totals = saved.get("inspection_diagnostics", {})
    # At most one accepted probe per candidate/direction, including after resume.
    # Later suspicious stops stay partial. Completed evidence is
    # saved before applying it so cancellation/retry cannot repeat an accepted call.
    rechecks = saved.get("stop_rechecks", {})

    def persist():
        result = {
            "visual_results": distinct_activities(candidates),
            "query": payload["query"],
            "inspection_diagnostics": totals,
            "stop_rechecks": rechecks,
        }
        db.execute(
            "UPDATE jobs SET result=? WHERE id=?", (json.dumps(result), job["id"])
        )
        return result

    def stop(code, message, *, cancelled=False):
        _merge_diagnostics(
            totals,
            {
                "error_code": code,
                "error_count": 1,
                "errors": [{"stage": "continuation", "code": code}],
            },
        )
        persist()
        if cancelled:
            raise media.Cancelled()
        raise ValueError(message)

    persist()
    if (
        payload.get("contract_version") != grounding.VERSION
        or payload.get("continuation_contract_version")
        != grounding.CONTINUATION_VERSION
    ):
        stop(
            "contract_changed",
            "Inspection rules changed. Retained footage is available; run this search again to inspect more.",
        )
    for candidate in candidates:
        asset = db.one(
            "SELECT * FROM assets WHERE id=? AND project_id=?",
            (candidate["asset_id"], job["project_id"]),
        )
        if (
            not asset
            or asset["status"] != "ready"
            or not json.loads(asset["provenance"]).get("cloud_analysis")
        ):
            raise ValueError(
                "Activity clip is unavailable or cloud permission was removed."
            )
        proxy = config.asset_dir(asset["id"]) / "proxy.mp4"
        proxy_hash = media.sha256_file(proxy)
        if proxy_hash != asset["visual_proxy_hash"]:
            raise ValueError("Playback proxy changed; reindex this clip.")
        a = candidate["activity"]
        while not a["complete"]:
            scheduled_recheck = False
            if cancelled():
                stop("cancelled", "Activity inspection cancelled.", cancelled=True)
            progress(
                0,
                f"Inspecting activity around {a['start_frame'] / 30:.1f}–{a['end_frame'] / 30:.1f}s",
            )
            probe_key = next(
                (
                    key
                    for key in (a["id"] + ":before", a["id"] + ":after")
                    if rechecks.get(key, {}).get("status")
                    in ("pending", "verified", "uncertain", "exhausted")
                ),
                None,
            )
            probe = rechecks.get(probe_key) if probe_key else None
            if probe and probe["status"] == "exhausted":
                stop(
                    "boundary_uncertain",
                    "This activity direction used its one short stop recheck; retained partial footage.",
                )
            if probe and probe["status"] == "uncertain":
                stop(
                    "boundary_uncertain",
                    "Activity stop remains uncertain after its short recheck; retained partial footage.",
                )
            before = probe["direction"] == "before" if probe else a["continues_before"]
            if probe:
                left, right, anchor_left, anchor_right = probe["frames"]
            elif before:
                right = min(asset["frames"], a["start_frame"] + OVERLAP)
                left = max(0, right - CHUNK)
                anchor_left, anchor_right = a["start_frame"], min(a["end_frame"], right)
            else:
                left = max(0, a["end_frame"] - OVERLAP)
                right = min(asset["frames"], left + CHUNK)
                anchor_left, anchor_right = max(a["start_frame"], left), a["end_frame"]
            spec = (
                "c0",
                proxy,
                proxy_hash,
                anchor_left,
                anchor_right,
                asset["frames"],
                left,
                right,
            )
            diagnostics = {}
            if probe and probe["status"] == "verified":
                verdicts, error = {"c0": probe["verdict"]}, None
            else:
                verdicts, error = grounding.inspect_continuation(
                    payload["query"],
                    spec,
                    established_activity=a,
                    direction="before" if before else "after",
                    job_id=job["id"],
                    cancelled=cancelled,
                    diagnostics=diagnostics,
                )
            _merge_diagnostics(totals, diagnostics)
            persist()
            verdict = verdicts.get("c0")
            if not verdict or verdict["decision"] != "match":
                persist()
                if error:
                    raise ValueError(
                        getattr(error, "safe_message", "Activity inspection failed.")
                    )
                stop(
                    "boundary_uncertain",
                    "Activity boundary remains uncertain; completed inspections were retained.",
                )
            if (
                verdict.get("continuity") != "same_activity"
                or not isinstance(verdict.get("continuity_evidence"), str)
                or not verdict["continuity_evidence"].strip()
                or len(verdict["intervals"]) != 1
            ):
                stop(
                    "continuity_unsupported",
                    "No visible evidence connects this extension to the same activity.",
                )
            # Require actual semantic overlap with the already inspected action.
            overlaps = [
                i
                for i in verdict["intervals"]
                if max(i["start_frame"], anchor_left)
                < min(i["end_frame"], anchor_right)
            ]
            if not overlaps:
                stop(
                    "continuity_unsupported",
                    "No verified continuity across this activity boundary.",
                )
            interval = max(
                overlaps,
                key=lambda i: (
                    min(i["end_frame"], anchor_right)
                    - max(i["start_frame"], anchor_left)
                ),
            )
            if probe:
                probe.update(status="verified", verdict=verdict)
                persist()
                if cancelled() or isinstance(error, InterruptedError):
                    stop("cancelled", "Activity inspection cancelled.", cancelled=True)
                if error:
                    raise ValueError(
                        getattr(
                            error, "safe_message", "Activity inspection incomplete."
                        )
                    )
            old = (a["start_frame"], a["end_frame"])
            if before:
                a["start_frame"] = min(a["start_frame"], interval["start_frame"])
                a["continues_before"] = interval["continues_before"]
                a["boundary_conflict_before"] = interval.get(
                    "boundary_conflict_before", False
                )
            else:
                a["end_frame"] = max(a["end_frame"], interval["end_frame"])
                a["continues_after"] = interval["continues_after"]
                a["boundary_conflict_after"] = interval.get(
                    "boundary_conflict_after", False
                )
            if probe:
                probe["status"] = "complete"
            elif (
                a["intent"] == "broad_activity"
                and verdict.get("boundary_outcome") == "observed_stop"
            ):
                direction = "before" if before else "after"
                edge = a["start_frame"] if before else a["end_frame"]
                if 0 < edge < asset["frames"]:
                    key = a["id"] + ":" + direction
                    previous = rechecks.get(key)
                    a["continues_" + direction] = True
                    _refresh(candidate)
                    if previous:
                        previous.update(status="exhausted", blocked_edge=edge)
                        stop(
                            "boundary_uncertain",
                            "This activity direction used its one short stop recheck; retained partial footage.",
                        )
                    if before:
                        probe_right = min(a["end_frame"], edge + config.FPS)
                        probe_left = max(0, probe_right - 8 * config.FPS)
                        anchors = (edge, probe_right)
                    else:
                        probe_left = max(a["start_frame"], edge - config.FPS)
                        probe_right = min(asset["frames"], probe_left + 8 * config.FPS)
                        anchors = (probe_left, edge)
                    rechecks[key] = {
                        "direction": direction,
                        "edge": edge,
                        "status": "pending",
                        "frames": [probe_left, probe_right, *anchors],
                    }
                    scheduled_recheck = True
            _refresh(candidate)
            persist()
            if probe and (
                verdict.get("boundary_outcome") == "uncertain"
                or a.get(
                    "boundary_conflict_before" if before else "boundary_conflict_after"
                )
            ):
                probe["status"] = "uncertain"
                stop(
                    "boundary_uncertain",
                    "Activity stop remains uncertain after its short recheck; retained partial footage.",
                )
            if cancelled() or isinstance(error, InterruptedError):
                stop("cancelled", "Activity inspection cancelled.", cancelled=True)
            if error:
                raise ValueError(
                    getattr(error, "safe_message", "Activity inspection incomplete.")
                )
            if (
                old == (a["start_frame"], a["end_frame"])
                and not scheduled_recheck
                and not a["complete"]
                and (a["continues_before"] if before else a["continues_after"])
            ):
                stop(
                    "no_progress",
                    "Activity inspection made no progress; retained partial activity.",
                )
    return persist()
