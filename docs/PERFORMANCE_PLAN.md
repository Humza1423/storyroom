# A3: measure the media pipeline before optimizing

Planned 2026-10-09 after local A2 acceptance and implemented on 2026-10-10.
This document preserves the original scope and acceptance intent; actual evidence
and the measured baseline are in [STATUS](STATUS.md).

## Outcome and choice

Explain where one import/normalization/render attempt spends time, retain useful
failure evidence, and collect a reproducible generated-media baseline. Preserve
the A2 geometry, frame-clock, audio and saved-project contracts.

Choose a compact optional `diagnostics` object in existing `jobs.result`, plus
concise local log summaries for import attempts that never create a job. Logs
alone disappear with the launch terminal; adding a log service or database is
unnecessary. Existing SQLite JSON and API polling suffice. No schema migration,
extra worker concurrency, cloud request or encoder change is planned.

## Measurements and labels

| Boundary | Record |
| --- | --- |
| Import handler | Local copy/hash, inspection/validation, managed-source registration |
| Normalization | Editing encode, proxy encode, thumbnail, final editing inspection |
| Render | Part-encoding rollup, slowest few parts, final concat/audio encode |
| Job attempt | Queue wait and total attempt time, outcome, interruption state |

FastAPI has already received/spooled `UploadFile` before the import handler reads
it. Its copy/hash timer is **server ingest**, not full browser/network upload time.
Full upload timing belongs to a separate request/browser measurement. Do not
double-count `encode`'s inspection: expose it separately or label stage timing as
inclusive, documenting which totals are comparable.

Context includes source duration/dimensions/frame-rate metadata/audio presence,
selection count/selected frames, output bytes, FFmpeg version and relevant encode
settings. Stage elapsed times use a monotonic clock; queue timestamps already use
wall time, so report queue wait separately. Record concise outcome/error classes,
not raw commands, absolute paths, credentials, prompts or full exception text.

## Implementation boundaries

1. Add a small recorder with an injectable clock and persistence callback. Keep
   measurement arithmetic independent of SQLite and FFmpeg.
2. Media functions accept an optional recorder; existing callers keep working.
   They report stages but never issue database writes themselves.
3. The import path may seed diagnostics on a newly registered normalization job
   inside the existing registration transaction. Preserve duplicate behavior;
   duplicate requests must not replace that job's earlier measurements.
4. The worker loads seeded diagnostics and persists stage snapshots. Successful
   result merging preserves `asset_id`/`url`; failure/cancel snapshots are committed
   with terminal job/asset updates in the existing atomic transaction.
5. Persist the active stage before work. Startup can label an incomplete attempt
   interrupted, but cannot know its finished duration after a hard kill. Keep that
   duration unknown; do not pretend every encoding stage is resumable.
6. Limit storage and write frequency. Boards permit 30 sections × 100 placements,
   not merely 30 source files. Aggregate counts/totals/maxima and keep at most five
   slowest part records plus the current/failing stage. Expose omitted counts and
   set an explicit serialized-size cap. Do not persist an unbounded event per part
   or per frame. Batch intermediate render snapshots with a documented bound;
   distinguish last durable evidence from work that may have occurred since it.
7. Report the baseline and identify its slowest measured stage in STATUS. Do not
   build a dashboard or separate reporting tool for this experiment.

Execution approach: keep this as one coordinated Codex task. Use another agent only
if a specific independent subtask justifies its context and coordination cost.

## Acceptance and baseline

- Controlled clocks prove exact elapsed arithmetic without machine-speed thresholds.
- A tiny generated real normalization/render reports expected stage order and byte
  counts matching the filesystem. Do not make the whole integration suite slower
  by repeating full-resolution fixtures for every unit case.
- Failing proxy work preserves editing-stage evidence; thumbnail is not completed.
- Cancellation retains completed stages and marks unfinished output appropriately.
- Hard interruption remains explicitly incomplete; explicit retry gets a new
  attempt and preserves historical diagnostics and saved edits.
- Old results without diagnostics still load; download URLs remain usable.
- Simulated 3,000-part work proves bounded serialization and persistence frequency.
- Existing atomic failure/retry and all A2 regressions remain green.

Run a bounded generated 720p/1080p sample and a short repeated-source assembly in
isolated storage. Record fixture specification, environment, stage durations and
output sizes; distinguish first and subsequent runs without claiming controlled
OS-cache conditions. No personal projects, online downloads or paid calls are needed.
Record the sanitized measurements in STATUS, not the generated media or private
paths. Generated timing is a technical baseline, not evidence of performance on
unfamiliar camera footage.

Only optimize after a measured bottleneck: compare one candidate change against
the same inputs, retain A2 correctness, and report measured gain and resource cost.
If no meaningful improvement is demonstrated, retain the baseline implementation.
Finish backend/build/lint/isolated browser checks and remote CI, update STATUS and
the PR, then proceed to the separately authorized real-footage/Resolve walkthrough.
