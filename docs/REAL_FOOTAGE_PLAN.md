# Next milestone: reliable real-footage assembly

Status: Phase A1 verified on 2026-10-08 and A2's generated-media regressions and fixes
verified on 2026-10-09. A3 and later phases remain planned. The foundation history
and current work are pushed on `codex/media-correctness`, under
[PR #1](https://github.com/Humza1423/storyroom/pull/1). Read STATUS.md for exact
local/remote verification. This task is about the existing app.
The guided computer-use test, footage acquisition, and provider evaluation happen
in subsequent phases below. No runtime changes or new test runs occurred during the original planning pass;
see IMPORT_PLAN for subsequent A1 implementation evidence.

## Outcome

Import a small collection of supported real exercise clips, understand which files
are ready or failed, make a 20–30 second assembly, reopen it with exact choices,
render it with correct orientation/timing/audio, and hand it into Resolve.
Keep completion evidence separate for application correctness, editor compatibility,
retrieval quality, and usefulness to a creator.

## Phase A: app preparation, before the live walkthrough

### A1. Make multi-file import resilient — first coding task

Execution specification: [IMPORT_PLAN](IMPORT_PLAN.md). The creator authorized
planning followed by implementation on 2026-10-07; implementation evidence is recorded in IMPORT_PLAN and STATUS. This scope excludes the later visible real-footage walkthrough.

Pre-implementation observation in src/App.tsx: one task loops over files with an awaited request. A thrown
request ends the loop, so one invalid file prevents later files being attempted.
The UI has no per-file upload outcomes, and ignores the API's duplicate flag.

Move this flow into a focused library/import module. Capture the destination project
ID at batch start. Show per-file waiting, uploading, preparing, ready, duplicate,
and failure outcomes. Distinguish upload/registration from worker preparation. Keep
uploads sequential and one expensive encoder job active on the 8 GB development Mac.
Continue past a file-specific validation error, but pause remaining requests on
server disconnection or a project-wide capacity limit instead of producing a flood
of identical errors. Preserve successful imports; never report the whole batch as
successful when only some succeeded. Refresh visible assets even after partial failure.

Use the existing API's returned asset/job IDs and duplicate flag. Retry a failed
normalization through its existing job endpoint, without uploading the original again.
For ambiguous upload timeout, refresh/reconcile saved state first; the current hash
deduplication supports a safe explicit re-upload if necessary. Never invent success.
Limit filename/size checks in the browser to hints; ffprobe/backend validation remain
authoritative. Keep existing 30-file, 15-minute, 2-GB project limits.

Acceptance: a batch of valid A, corrupt B, valid C imports A/C and names B's error;
duplicate A produces one asset/preparation job; a normalization failure retries only
that job; a network failure remains recoverable. Test batch ownership when changing
projects, plus correct per-file counts. Use synthetic fixtures in isolated tests.

Creator contribution: reserve the visible ready/processing/failed count and its
small summary helper for the creator if they choose the learning exercise in
LEARNING_PATH.md. Implement the remaining import flow independently. Do not leave
the overall feature indefinitely blocked on an exercise; clarify who owns it before
handing off an implementation task.

### A2. Verify media properties and timing

Inspect server/media.py, server/worker.py, server/exporter.py, and the current
media tests. At planning time, probe derived frames by rounding duration × 30. That estimate
is not independent evidence of the decoded frame count. Rotation/display metadata,
stream start times, and sample aspect ratio are not exposed by the probe result.
These were test gaps and possible failure paths, not yet confirmed corruption bugs.
Subsequent A2 tests reproduced display-aspect and shared-clock errors, a renamed
MOV rejection gap, and audio/video timing errors across short rendered cuts.
The fixes and independent acceptance evidence are in
[MEDIA_CORRECTNESS_PLAN](MEDIA_CORRECTNESS_PLAN.md) and [STATUS](STATUS.md).
Production metadata still derives normalized frames from duration; decoded count
is independently checked in the generated regression matrix, not on every import.

Add targeted generated fixtures and independent assertions for:

| Case | Expected behavior |
| --- | --- |
| Landscape and portrait SDR H.264 MP4 | Upright preview/render, preserved aspect, documented letterboxing |
| Rotation metadata | Normalized visual orientation agrees with reported dimensions |
| Variable-rate input and 24/30/60 fps | Elapsed time preserved in a 30-fps editing copy |
| Audio and silent clips in one board | Audio remains aligned; silent selections retain their timeline duration |
| Nonzero timestamps / delayed audio | A documented time-zero mapping, without unexplained drift |
| Repeated source, distinct ranges, final-frame trims | Independent placements and exact valid frame ranges |
| Corrupt file, unsupported codec/container/HDR | Specific rejection while other valid imports remain usable |
| Missing editing copy | Actionable render/export failure identifying the asset |

Use decoded video frame counts or timestamps from an independent ffprobe check for
assertions. Do not compare only two calls to the same rounding helper. Use a known
visual marker and audio cue to check relative A/V timing; record the method/tolerance.
Fix only demonstrated failures, with a regression fixture. Keep WebM/HEVC/HDR/MOV
outside initial supported imports; document conversion requirements. Do not silently
tone-map HDR or claim all phone footage is supported.

### A3. Measure performance before changing encoding

Execution specification: [PERFORMANCE_PLAN](PERFORMANCE_PLAN.md), prepared from
parallel read-only inspection after A2. No A3 runtime changes or benchmark yet.

The foundation record contains an earlier render timeout whose cause was not
isolated. It increased the bounded browser deadline and added render-stage messages;
that is not evidence of a speed improvement.

Add bounded local diagnostic reporting for inspect/upload, editing-copy encode,
proxy encode, thumbnail, render parts, and final concat. Record source duration,
resolution, frame rate, output sizes, elapsed time, and errors. Reuse existing jobs
and local logs; add a database migration only if durable fields are actually needed.
Separate a project's upload status from media-processing progress. Do not show
invented percentage precision when only stage progress is known.

Keep the 30-fps editing copy for export. Compare one change at a time only if a
measurement points to it: proxy dimensions/quality, FFmpeg preset, redundant work,
or preview buffering. Require preserved output correctness and a useful measured
gain. No queue replacement, extra worker concurrency, new database, or model swap
without a demonstrated bottleneck. Record measured speed rather than promising an
arbitrary seconds-per-clip target before the first real-media baseline exists.

App-preparation gate: relevant backend tests, build/lint, and isolated browser suite
pass; batch failures are recoverable; the generated media matrix has reported
results; diagnostics identify where time goes. At this point the app is ready for
real-footage testing, not already validated on real footage.

## Phase B: actual footage and guided computer-use session — later

Use the four sources already researched in FOOTAGE_TEST_SET.md. Recheck source
pages at acquisition, download originals, preserve provenance, and make separate
supported H.264 MP4 inputs. The WebM-to-MP4 conversion is external preparation;
record it so this test does not imply native WebM support. Keep media under the
ignored data/evaluation directory and out of Git. Initial cloud/training flags stay off.

Before using the app, the creator watches the clips and writes a brief plus three
or more useful ranges. These independent expectations let us judge the application.
Do not copy AI answers into the expected results. The four related demonstrations
are a smoke test; they are not three independent evaluation footage sets.

In the later visible browser session:

1. Verify the running app uses the intended code and evaluation data root; restart
   stale API/worker processes cleanly if needed. Open a dedicated evaluation project.
2. Import the prepared inputs and inspect per-file outcomes/proxies. Demonstrate
   one duplicate and one invalid file without harming the valid imports.
3. Create custom sections, select at least three sources, use one source twice,
   trim to recorded integer ranges, and reorder. Add manual descriptions/search.
4. Save and restart/reopen; compare exact section/selection IDs, order and ranges.
5. Play the assembly, render it, and inspect orientation, cuts and sound. Check
   decoded frame count against the sum of exclusive-out minus in-frame boundaries.
6. Export and import XML in the actual Resolve application. Record version,
   references, order, cut points within one normalized frame, and audio alignment.

Show the creator what each action is testing. Retain screenshots and a concise
pass/fail evidence record. If Resolve is unavailable, report that specific gate as
pending; XML validity cannot substitute for it. Downloads, rendered files, and local
media references must be distinguishable in the explanation.

## Phase C: fix measured real-media failures, then evaluate AI

For each failure: record source hash/properties, reproduction, expected/actual,
affected stage, and evidence. Prioritize data loss/wrong output, blocked valid imports,
unusable waiting time, then polish. Reproduce with a minimal generated fixture where
possible so CI does not depend on online files. Run the relevant regression checks
and repeat the affected real clip. Do not repeatedly run every expensive test without
a change or unresolved concern.

Only after the manual path works, verify provider model IDs/rates and run one bounded
authorized analysis. Compare descriptions and ranges with human-reviewed footage.
Test absent queries and proposals that must leave accepted edits untouched. Build
toward 20 reviewed queries over three independent sets, reporting relevant results
in the first five (initial target 16/20). Diagnose misses as observation, retrieval,
ranking, or UI errors before choosing an optimization. Training remains deferred
until there are enough permitted labels and a measured ranking problem.

## Who does what

The creator owns the intended result, initial judgments, one small code change per
milestone, and an explanation of the request flow. Codex owns implementation support,
repetitive fixture generation, focused tests, and evidence-backed review. Use the
[learning path](LEARNING_PATH.md) to turn that division into concrete practice.

## Next implementation prompt

> Read AGENTS.md, docs/STATUS.md and this plan. A1/A2 are verified; plan Phase A3
> media-stage diagnostics before coding. Inspect the current pipeline and split
> implementation, independent tests and documentation among non-overlapping agents.
> Measure inspect, editing-copy/proxy encode, thumbnail, render parts and final join.
> Prefer bounded local reporting over new infrastructure. Optimize only a measured
> bottleneck while retaining A2 correctness. Preserve saved frames and immutable
> sources; push verified checkpoints as authorized. Real downloads, a live walkthrough,
> Resolve import, paid AI and training remain separate tasks.
