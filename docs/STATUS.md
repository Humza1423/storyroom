# Project status and release checklist

Updated: 2026-10-12. Status: local development preview; release gates remain open.

## Online 4K footage check (2026-10-12) — Resolve gate still open

Six Pexels exercise clips were downloaded individually for a small demo/workflow
check, not AI training or a search benchmark. Original media and a per-file
rights/hash/stream manifest are kept only in ignored `data/evaluation/pexels/`.
Five downloaded files are actually 3840×2160; the page/filename for the
push-up clip suggested 4K but its downloaded stream is 2560×1440. Do not infer
media properties from the stock-site listing.

Storyroom now accepts SDR H.264 MP4 up to 3840×2160 in either orientation,
preserves 4K in its normalized editing copy, and still makes a 720p browser
proxy. Three real 4K clips imported in the normal local project named
`4K gym demo — Pexels`. Manual search found the entered exercise descriptions.
A three-section/four-placement board used one source twice at independent ranges.
After a full app restart it reopened with exact section order and frame bounds.
The review MP4 decoded to 330 frames/11.000 seconds at 30 fps, and sampled
frames showed the expected four-shot order. XML inspection found those same
four full-resolution source ranges. Original-file SHA-256 values were unchanged.
This proves the local import/assembly/export-file path, **not** AI retrieval.

The first actual Resolve 21 import attempt found the XML but showed 3/3 source
files as missing. Prior A2 testing showed Resolve can require explicit folder
access even for valid absolute paths. A folder-relink attempt was interrupted
by a macOS computer-control timeout; this 4K timeline has **not** yet been
visually verified in Resolve. The earlier 1080p mixed-profile Resolve import
remains verified. Do not call the 4K handoff complete until the media is visible
and ranges/cuts are checked in the actual editor.

On this 8 GB Mac, full-resolution editing-copy creation took 264.36, 514.08,
and 338.82 seconds for sources lasting about 15.3, 8.5, and 17.4 seconds.
The corresponding proxies took 66.04, 6.56, and 18.30 seconds; four 720p
render parts took 9.79 seconds and joining took 0.22 seconds. No stage failed.
The clear bottleneck is Storyroom's unconditional 4K software re-encode to
constant 30 fps, amplified by limited hardware. 4K is technically accepted but
is **not yet seamless** on this machine. Do not lower export resolution silently.
Next optimization experiment: compare current CPU encode with VideoToolbox on
the same short inputs, checking frame counts/timestamps, displayed geometry,
audio alignment, quality, output size, and Resolve import; retain CPU fallback.
Measure peak free space as well: the fixed 3 GB import guard and a 2 GB input
limit do not guarantee enough room for long 4K editing copies. Add an
output-aware disk budget before treating larger 4K projects as supported.
Use 1080p inputs for rapid iteration until that measured path passes.

For later AI-search evaluation, a 21-video subset of the CC BY 4.0 Mendeley
seven-exercise archive was selectively extracted into ignored storage without
downloading the whole 3.1 GB ZIP. It has source exercise labels but no reviewed
query judgments or search score yet. Qwen3-VL-Embedding-2B was researched, not
installed or benchmarked: its full weights and this Mac's 8 GB memory/limited
free disk make an unmeasured local deployment irresponsible. Search is still
manual description/keyword search, not visual natural-language retrieval.

Verification for this checkpoint: 77 backend tests passed (one existing
Starlette/httpx deprecation warning); TypeScript/production build passed; the
full isolated browser suite passed 25/25 on a clean rerun. An earlier concurrent
run timed out one UI readiness assertion at 24/25 while all corresponding worker
jobs completed; that case passed alone and in the clean full rerun. The 4K
geometry/frame-rate regression, prior audio/cut-order checks, immutable-source
hash comparison, and saved-project restart check passed. The remaining gate is
the visually confirmed 4K Resolve import, not another XML parser check.

## Mixed-profile Storyroom-to-Resolve check (2026-10-11)

One CC BY-SA 3.0 real running clip was transformed into four explicit technical
profiles: 1080p/24 fps with audio, portrait/60 fps silent, 720p variable-rate
silent, and 90° rotation metadata with audio. All four H.264 MP4s imported and
prepared in an isolated Storyroom project. A saved four-section board rendered
to exactly 360 frames/12.000 seconds; visual cut order and audio/silent regions
were checked independently. Original/source hashes remained unchanged. The
original WebM and an H.264 MOV were clearly rejected. An HEVC import was
inconclusive because the machine dropped below Storyroom's 3 GB free-space
minimum before codec validation; no user files were deleted to bypass it.

DaVinci Resolve 21.1.1 initially reported 4/4 missing clips from the XML. A
one-clip XML and a localhost-style file URL failed the same way. Direct MP4
import revealed Resolve's **Grant Access To Folder** prompt; after granting
the isolated Storyroom media folder and re-importing the unchanged XML, all
four distinct pictures appeared in the actual Resolve timeline at the intended
cuts, 30 fps/00:00:12:00, with source audio lanes on the first and fourth cuts
only. The compatibility project was saved. This is a folder-permission setup
gap; no media/export code change was warranted. The export-panel instruction,
README, and development guide now explain the handoff. The full source rights,
fixture settings, results, and untested boundaries are in
[MEDIA_COMPATIBILITY](MEDIA_COMPATIBILITY.md). About 2.6 GiB was free after the
run; further import tests require free space, not a relaxed safety guard.

Verification for this checkpoint: 74 backend tests passed, including explicit
low-disk behavior; the TypeScript/production build and fatal-error Ruff lint
passed; 12 isolated board/import-controller browser checks passed. The full
upload-to-export browser suite could not run meaningfully on this machine while
its real import preflight sees less than 3 GB free. The test-client fixture now
uses a controlled free-space result so backend behavior tests are not coupled to
host capacity, while production and explicit disk-error tests keep the guard.
The actual four-profile Storyroom and Resolve workflow above was exercised
separately. Both GitHub Actions checks for commit `84376d2` passed the full
isolated browser suite and other workflow steps: [push run](https://github.com/Humza1423/storyroom/actions/runs/38182532282),
[PR run](https://github.com/Humza1423/storyroom/actions/runs/38182534442).

## Real-footage Storyroom workflow (2026-10-11) — Resolve import verified

Four CC BY-SA 4.0 Cavemantraining exercise videos were downloaded from their
Commons originals, hashed, probed, and converted locally from WebM to supported
640×480 SDR H.264 MP4 inputs. Provenance (permanent page revisions, URLs, authors,
license, byte counts/hashes, stream properties, and exact FFmpeg conversion profile)
is in ignored `data/evaluation/cavemantraining/provenance.json`. Originals and
derived files stay out of Git. No cloud analysis or training ran.

In an isolated Storyroom data root, all four inputs imported and became ready. Manual
search found jumping jacks, burpees, kettlebell swing, double kettlebell clean and
jerk, and technique/detail framing. The saved three-section board was: Warm-up
(jumping jacks 0–120, burpee 240–360); Technique detail (wide swing 300–420, zoom
swing 120–240); Lift/finish (double clean-and-jerk 330–510, then the same wide-swing
source again at 1080–1200). Boundaries are 30-fps frames with exclusive out points;
the repeated source uses independent ranges. After stopping and restarting
Storyroom, exact section/clip order and boundaries reopened unchanged.

The rendered review decoded to exactly 780 frames / 26.000 seconds at 30 fps, in
the expected six-shot order. Source media hashes stayed unchanged. Audio was present
only on source-backed ranges; silent inputs/ranges remained silent with no invented
audio. FCP7 XML export contains the same six cuts, source ranges and section labels.
On 2026-10-11, DaVinci Resolve 21.1.1 imported the XML through File → Import →
Timeline at 30 fps / 1920×1080. The initial 4/4-missing warning was from an earlier
incomplete attempt; it was not reproduced during this completed import. In the
macOS file picker, selecting the XML by its full path enabled Import. Resolve loaded
the 26-second timeline, with real frames visible at 00:00:00, 00:00:08, 00:00:12,
00:00:16, and 00:00:22. The four distinct absolute `edit.mp4` references resolved;
the timeline has six ordered cuts and duration 00:00:26:00 (780 frames at 30 fps),
matching the saved assembly. The source repeated at sequence 00:00:22 uses a distinct
source range from its earlier placement at 00:00:08. Resolve showed audio on
audio-backed selections and no audio under the final silent selection, while that
video's duration remained intact. Storyroom section labels remain in Resolve clip
names, but FCP7 XML did not create Resolve bins. The project was saved after import.
No reproducible Storyroom defect was found; no product code changed.

Verification on 2026-10-11: `.venv/bin/pytest -q` **74 passed** (one existing
Starlette/httpx deprecation warning); isolated `npm run test:e2e` **25 passed**;
`npm run build` passed. The backend suite includes A2 geometry, frame-clock,
audio-sync and cut-order checks. The actual Resolve UI import was visually checked.
This validates these local H.264 files and cuts-only FCP7 interchange, not every
camera codec, storage location, Resolve version, or creator workflow.

## A3 performance measurement (2026-10-10)

Bounded optional stage diagnostics now live in existing media-job results; no
schema migration was needed. Editing-copy, proxy, thumbnail, render-part aggregate,
and final-join durations/output sizes are recorded. Render-part storage is capped;
terminal failure/cancellation preserves completed stages, and legacy results and
download URLs remain compatible. A monotonic clock keeps duration measurements
independent of wall-clock changes.

Generated-media baseline (one run; temporary media removed): macOS 26.5.1,
arm64 Mac14,2, 8 CPUs; FFmpeg 9.0.1. Fixture: generated 640x360, 30 fps,
2-second H.264 video with 880 Hz, 48 kHz AAC; render assembly used three
overlapping 30-frame placements. Editing copy: 0.2713 s / 286,385 bytes; proxy:
0.3659 s / 309,766 bytes; thumbnail: 0.1045 s / 13,094 bytes; render-parts
aggregate: 0.8569 s over 3 parts / 1,108,038 temporary bytes (slowest measured
stage; max part 0.3236 s); final join: 0.2099 s / 578,815 bytes. These are
technical-fixture measurements only, not a prediction for camera footage.
Reproduce with `python scripts/performance_baseline.py` after local setup.

Verification on this machine: backend suite **74 passed**; isolated browser
workflow **25 passed**; TypeScript/production build passed; fatal-error Ruff lint,
controlled-clock and bounded-diagnostics tests, generated-media output-size
comparison, and A2 geometry/frame-clock/audio-sync/cut-order regressions passed.
One existing Starlette/httpx deprecation warning remains. Remote CI is tracked in
PR #1 after this checkpoint is pushed. No encoder optimization was made.

## What exists

| Area | Implemented | Evidence and remaining work |
| --- | --- | --- |
| Manual assembly | Projects, import, proxies, descriptions, story sections, drag/reorder, frame trimming, save/reopen, undo | Automated suite covers generated fixtures; four licensed exercise videos completed manual import/search/board/restart/render and a visually checked Resolve 21.1.1 XML import. |
| Processing | One SQLite-backed worker, progress, cancel/retry, response caching | Real worker subprocess tests cover pending/interrupted normalization/render, second-worker refusal and explicit retry. Encoding restarts; it is not stage-resumable. |
| Output | MP4 render, FCP7 XML, OTIO, media manifest | Independent generated-media checks verify pixels, exact frame count/spacing, audio boundaries, and XML references/ranges/gaps. A 780-frame / 26-second licensed-footage timeline opened in Resolve 21.1.1 with footage visible and the repeated source range preserved. |
| AI adapter | Video chunks, validated observations, embeddings, story proposals, cost reservations | Fake-provider tests cover response validation, caching, budget, and failure. No real provider or quality benchmark has been verified. |
| Search | Keyword matching and optional description-embedding similarity | Manual keyword behavior tested. The 20-query real-footage benchmark has not been completed. |
| Training | Permission-aware judgments, grouped split, logistic-regression experiment, report export | Script and labeling interface exist. No trained or deployed custom model has been established. |
| Project access | Source opens in VS Code; onboarding, architecture, contribution and learning docs; public GitHub remote | Foundation and A2 commits are on `codex/media-correctness`; both Ubuntu checks passed at 3372a3a. PR #1 remains draft. |

The generated demo is a technical fixture. It is not real sports footage, a
trained model, or a demonstration of AI retrieval accuracy.

## Latest engineering checkpoint

2026-10-09: **Phase A2 media correctness and coordinated GitHub delivery**.
[MEDIA_CORRECTNESS_PLAN](MEDIA_CORRECTNESS_PLAN.md) was committed before runtime
edits. Separate agents owned media code, independent acceptance fixtures, and
README/development documentation; the coordinator reviewed and ran integration.
No additional product choice required an interview.

- Reproduced a 32:9 anamorphic image squeezed to 16:9, non-square proxy pixels,
  and an editing video starting at 0.2 seconds when audio preceded video. New
  normalization preserves displayed geometry and subtracts the first video
  timestamp from both streams, padding/trimming audio against that shared origin.
- Reproduced a QuickTime MOV renamed `.mp4` passing the codec/container guard.
  The `qt` container brand is now rejected; supported formats did not expand.
- A five-cut fixture with silent portrait footage, repeated ranges and a one-frame
  final-frame selection reproduced 123 ms excess decoded audio and an 8 ms video
  timestamp gap. Render parts now use exact-length PCM audio and frame-derived
  concat durations; AAC is encoded once in the final review MP4. Video remains
  sequentially encoded per part, then stream-copied at the join.
- Final independent media matrix: **19 passed (11.41s)**. Checks decode RGB pixels,
  frame counts/PTS and PCM audio rather than trusting production metadata alone.
  The 46-frame rendered fixture has exact cut order/count and continuous 30 fps
  timestamps; silent/audio boundaries are within one normalized frame. XML checks
  verify media references, ranges, order and silent gaps, not Resolve compatibility.
- Coordinator checks on macOS/Python 3.12.4/Node 22.4.1/FFmpeg 9.0.1:
  `.venv/bin/pytest -q` **66 passed (93.97s)**; isolated `npm run test:e2e`
  **25 passed (53.2s)**; TypeScript/production build, fatal-error Ruff lint and
  whitespace checks passed. One existing Starlette deprecation warning remains.
  All 105 local Markdown file links resolve. Runtime fixes and independent tests
  are recorded in commit `9d57a4b`.
- Existing editing copies and saved selections were not rewritten. New imports
  and renders use the fixes; older copies can retain historical errors. PCM adds
  approximately 192 KB of temporary audio per assembly second. This is not a
  speed benchmark. No schema, worker concurrency or dependencies changed.
- Rewrote README around the actual product/workflow, runnable branch setup,
  architecture and honest limits; moved deep operations into DEVELOPMENT and
  added a shared-clock learning exercise. Public repository access and the
  creator's standing checkpoint-push preference are documented.
- Foundation history and the plan are already on `codex/media-correctness` in
  [PR #1](https://github.com/Humza1423/storyroom/pull/1). Ubuntu push CI and PR CI
  both passed at 3372a3a ([push run](https://github.com/Humza1423/storyroom/actions/runs/38022060117),
  [PR run](https://github.com/Humza1423/storyroom/actions/runs/38022063786)). PR #1
  remains draft while A3 work is underway.

Next: evaluate retrieval quality on manually reviewed queries across multiple
permissioned footage sets before adding computer-vision complexity. Start with a
narrow pretrained-model slice and a baseline comparison; the verified manual,
persistence, render, and Resolve handoff flow is now a usable foundation. Provider
quality and custom training remain separate gates. Footage acquisition happened
after the A3 checkpoint; no paid request or training occurred.

2026-10-08: **independent A1 review and two consistency fixes**. Reviewed the four
import checkpoints after 7286856, including controller, UI integration, API errors,
preparation retry association and tests. The original suite independently passed:
45 backend tests (33.33s) and 24 Playwright checks (1.1m).

- Reproduced a delayed board save replacing newer imported assets in React with
  its pre-save project snapshot. The UI showed "No clips yet" despite a successful
  import. Fixed saveBoard to merge only board/revision into current state. Regression
  blocks later polls so they cannot hide the bug. This was UI state loss, not source
  or database deletion.
- Reproduced a worker commit where a normalize job was already failed while its
  asset still said processing. A retry could interleave before the worker's second
  write, allowing the old failure to overwrite the new retry state. Failure and
  cancellation now commit job/asset changes in one transaction. Independent reader
  checks cover both failure and cancellation at transaction boundaries.
- Both new failure reproductions failed against the reviewed code before fixes.
  Final checks: `.venv/bin/pytest -q` **47 passed (39.67s)**; `npm run test:e2e`
  **25 passed (56.8s)**, including 13 browser scenarios and 12 controller/board
  checks; `npm run build` and fatal-error Ruff lint passed. One existing Starlette
  deprecation warning remains. Tests used isolated generated fixtures and data.
- Review decision: proceed to A2 media correctness validation. The current local
  architecture is adequate for this scope; no new services or model layer are
  justified by these findings. Real-footage timing/audio, real Resolve import,
  provider quality and remote CI remain open gates. No paid calls or push occurred.

2026-10-08: **Phase A1 resilient multi-file import verified locally** on
`codex/complete-foundation`. The confirmed plan preceded runtime edits; see
[IMPORT_PLAN](IMPORT_PLAN.md) for the API contract, acceptance matrix and evidence.

- Each file has an independent upload outcome. Invalid files allow later files to
  continue; capacity, disk, network and unknown errors pause waiting requests.
- Duplicate badges use content identity. Upload acceptance is separate from current
  preparation/ready state; the footage summary derives counts from unique assets.
- Explicit upload retry handles uncertain responses through server deduplication;
  preparation retry reuses the stored source and current normalization job, even
  outside the activity panel's 40-job window. No schema migration was needed.
- Captured project ownership and media-only refreshes preserve other projects,
  saved boards and typed drafts. Reload keeps accepted assets/jobs but drops local
  waiting Files; clearing outcomes does not delete server data.
- Actual checks: full backend **45 passed (20.26s)**; TypeScript/build and fatal-error
  lint passed; isolated Playwright **24 passed (39.8s)**. The latter includes 12
  browser scenarios and 12 controller/board-rule checks. One existing Starlette
  deprecation warning remains. Documentation diff checks and all 84 local links
  passed; both browser-run temporary roots were removed. No remote CI run or
  source push was performed.
- Fault evidence is explicit: lost-response test commits a real upload then drops
  the response; disk/capacity use controlled guards/responses; preparation UI uses
  simulated failure states backed by a separate backend failure/retry test.

Next: Phase A2's generated-media orientation/timing/audio checks in
[REAL_FOOTAGE_PLAN](REAL_FOOTAGE_PLAN.md). Real footage, performance improvements,
Resolve compatibility and provider quality remain unverified. No footage downloads,
paid calls or training occurred in A1.


Prior planning checkpoint: [REAL_FOOTAGE_PLAN](REAL_FOOTAGE_PLAN.md) defines app
preparation, later visible testing, measured fixes, and subsequent AI evaluation.
Inspection found that one failed upload stops the current multi-file loop; Phase A1
addresses per-file outcomes and partial success. Timing/rotation/audio checks are
test gaps to investigate, not claimed failures. [LEARNING_PATH](LEARNING_PATH.md)
gives the creator an import-flow exercise and a small footage-summary contribution.
These are documentation changes only; no real footage or new runtime checks were
performed in this planning pass. A stale architecture paragraph was also corrected
to reflect the completed frontend extraction and database migration runner.

2026-10-07: **all five foundation checkpoints verified locally** on
`codex/complete-foundation`. Changes are in local commits; nothing was pushed.

| Final check | Actual result |
| --- | --- |
| Fresh checkout installation | Pinned uv bootstrap, `uv sync --locked --extra dev`, `npm ci`, Chromium install passed; no `.env`, demo or personal data required. |
| Backend | 38 passed in 20.87s in the fresh locked environment; one Starlette deprecation warning. |
| Fatal-error lint / TypeScript / production build | Passed. |
| Two consecutive fresh browser runs | 5 passed in 39.3s; 5 passed in 1.1m. Each owned a different temporary root and stopped its stack. |
| Persistence / migrations | Saved exact ranges/order and duplicate placements checked; all persisted tables preserved through controlled upgrade; valid WAL-aware backup, rollback and future-version refusal. |
| Recovery | Pending/interrupted normalization and rendering retried in real worker processes; second worker refused; completed sources/revisions retained; interrupted AI not replayed. |
| Startup / disconnect | Occupied ports, missing tools, readiness, failed-child diagnostics and cleanup passed; browser connection-refusal/reconnect preserves drafts and shows failed saves. |
| Manual clean-checkout launch | API/UI ready, empty project created, SIGTERM cleanup passed, ports and worker lock released; no checkout `data/` created. |
| Documentation | `git diff --check` and all 72 local Markdown links passed after final evidence updates. |
| Cloud / external validation | Zero paid calls; browser usage ledger asserted empty. CI file added, **remote CI not run**. Real footage/Resolve/provider gates remain open. |

An earlier clean browser run timed out at the old 30-second render deadline while
its job was still running. The precise timing cause was not isolated. Per-stage
render progress, failed-run job diagnostics and bounded 60-second media assertions
were added; the two final runs above passed. This does not establish a performance
benchmark. See [FOUNDATION_PLAN](FOUNDATION_PLAN.md) for commands, environment,
isolation boundaries and detailed evidence.

Next: the [licensed real-footage exercise](FOOTAGE_TEST_SET.md), followed by an
actual Resolve import check. The footage list has not been downloaded/evaluated.

2026-10-07: startup/recovery checkpoint verified. Full backend suite: 38 passed
(32.63s), one existing Starlette deprecation warning. Browser suite: 5 passed
(21.4s), including connection refusal/reconnect, visible failed-save errors and
preserved draft text. Build and fatal-error lint passed. Real process tests cover
pending/interrupted normalization and rendering, explicit retry, second-worker
rejection, preserved revisions/sources, and no replay of interrupted AI jobs.
Launcher tests verify prerequisites, occupied ports, HTTP readiness, child failure,
and owned stack cleanup. Browser offline simulation uses refused requests; it does
not claim a real browser test of physically terminating the API.

2026-10-07: frontend extraction verified. Types/helpers build passed, component
extraction build and 2-test browser suite passed, then the expanded 4-test suite
passed (20.4s), including delayed-project response and duplicate-placement rules.
Fatal-error lint passed. Stable API contracts and saved integer-frame boards remain.

2026-10-07: database migration runner verified: 5 migration tests passed, covering
competing initialization, existing saved choices/revisions, WAL-aware backup,
rollback (including refusal of implicit commits), repeat startup, and future-version
rejection. Tests use synthetic projects; the creator's database was not upgraded.

2026-10-07: isolated browser harness implemented. Two consecutive fresh runs:
2 passed (16.5s), 2 passed (12.1s); frontend build passed; import atomicity tests
2 passed. Dedicated temporary roots, zero AI budget/empty credentials, owned
process groups, and non-reused test ports replace the development-data dependency.
The mobile test exposed and fixed missing accessible labels on project icons.


2026-10-07: foundation planning and real-footage sourcing.

- Inspected test setup, launcher, SQLite initialization, frontend structure, local
  origin rules, and worker recovery. Added [FOUNDATION_PLAN](FOUNDATION_PLAN.md)
  with ordered implementation checkpoints and acceptance criteria.
- Added [FOOTAGE_TEST_SET](FOOTAGE_TEST_SET.md): four exercise-video source pages
  with author/license metadata, format conversion needs, and a manual test procedure.
  No footage was downloaded or evaluated and no cloud call was made.
- Foundation items below remain unfinished. This checkpoint changes documentation,
  not runtime behavior; historical test results are not a new test run.
- Documentation validation: `git diff --check` passed; all 63 relative links across
  15 Markdown files resolve.

2026-10-06: documentation continuity and GitHub inspection.

- Added PRODUCT, ROADMAP, HANDOFF, and WORKFLOW guides; linked them from AGENTS,
  START_HERE, and README. Product intent, planned work, and verified status now have
  separate sources of truth.
- Created the private
  [Humza1423/storyroom](https://github.com/Humza1423/storyroom) repository, added
  it as `origin`, and pushed `main`. GitHub reports `main` as the default branch.
- The remote is private. This is a source backup/collaboration checkpoint, not a
  public open-source launch or a hosted Storyroom application.
- No runtime code changed in this documentation checkpoint. The test results below
  are from the earlier implementation checkpoint, not a new run.
- Documentation checks: 56 relative links across 13 Markdown files resolve;
  `git diff --check` passed.

2026-10-06: source access, project documentation, and atomic import registration.

- Import now saves the asset and normalization job in the same SQLite transaction.
- A handled registration failure removes only that request's new managed copy.
- Failure-injection and duplicate-upload regression tests were added.
- The missing status document now exists; the README links to onboarding and contribution guidance.
- OS metadata and Ruff's cache are excluded from Git.
- Verification: `.venv/bin/pytest -q` — 27 passed; `npm run build` — passed; targeted fatal-error lint — passed.
- One existing Starlette test-client deprecation warning remains. Browser tests were not rerun in this checkpoint; earlier partial results are not a current full-suite pass.

No cloud credentials, footage, database, or generated exports belong in Git.
GitHub access was initially private. On 2026-10-09 the connected repository was
verified public; tracked source and documentation are published there. The creator
authorized routine feature-branch pushes for verified implementation checkpoints.

## Next milestones, in order

### 1. Reliable and understandable local foundation — verified locally

- [x] Open the source in a code editor and provide a file map.
- [x] Add an honest status record and saved release checklist.
- [x] Commit asset registration and its preparation job atomically.
- [x] Test queue-write failure followed by a successful import retry.
- [x] Record the initial local Git checkpoint with source, docs, and tests; no GitHub remote configured.
- [x] Create a private GitHub repository, configure `origin`, and push `main`.
- [x] Isolate browser tests from personal projects and remove dependence on a pre-seeded demo.
- [x] Add tested, versioned database upgrades before changing the stored schema.
- [x] Split frontend types, API calls, board logic, and components into focused modules.
- [x] Lock Python dependencies and add automated checks for contributions.
- [x] Improve startup diagnostics and the disconnected-server experience.

### 2. Prove the manual handoff — required for release

- [x] Phase A1: resilient multi-file imports with stage-specific recovery and isolated tests.
- [x] Phase A2: independently verify generated-media orientation, frame timing and audio.
- [x] Phase A3: measure media-stage performance before changing encoding.

- [x] Import four appropriately licensed real training clips (640×480 landscape SDR; see manifest).
- [x] Assemble/search/trim/repeat clips; restart and confirm exact saved section and clip order/boundaries.
- [x] Render and check expected order/duration and source-backed versus silent audio ranges. Portrait and VFR real-footage cases remain untested.
- [ ] Import XML in DaVinci Resolve and check cuts within one normalized frame, audio, order, and references.
- [ ] Record Resolve version, footage characteristics, test date, result, and any limitations.

### 3. Verify the cloud AI integration

- [ ] Verify current model identifiers, provider availability, request compatibility, and pricing.
- [ ] Configure a local key and permissions; run one bounded clip analysis.
- [ ] Compare returned timestamps and descriptions with the actual footage.
- [ ] Check provider billing against the local ledger.
- [ ] Verify story suggestions preserve accepted edits.
- [ ] Complete the section-specific reranking user interface; backend support alone is insufficient.

### 4. Evaluate usefulness and prepare a release

- [ ] Curate at least 20 human-reviewed queries across three separate footage sets.
- [ ] Measure relevant candidates in the first five; initial target is at least 16 of 20, with misses reported.
- [ ] Test unsupported queries, uncertainty, missing media, and stop/restart recovery.
- [x] Test installation from a fresh macOS checkout and locked environment.
- [ ] Review dependency/media licenses for the release and real-footage exercise.
- [ ] Demonstrate with real footage and clearly disclose remaining limitations.
- [x] Public source access verified on 2026-10-09; this is not a validated product release.
- [ ] Review release contents, keeping credentials and personal media excluded.

### 5. Learn a better ranker after labels exist

- [ ] Collect approximately 300–500 permitted, reviewed judgments from multiple shoots.
- [ ] Keep related footage in the same evaluation group.
- [ ] Compare the learned ranker against the existing retrieval baseline.
- [ ] Resolve missing semantic features and test inference integration before enabling a trained model.
- [ ] Publish the reproducible experiment, results, and limitations.

## Known limitations that shape the next design decisions

- Frontend boundaries are extracted; App still owns orchestration and draft dialogs to avoid unnecessary state abstractions.
- Ordered transactional migrations now preserve version-1 data; no production version-2 change was needed.
- Asset/job registration is atomic in SQLite. SQLite and the filesystem are not one transaction: a hard process kill may leave an unreferenced media directory. Automatic orphan reconciliation is not implemented.
- A retry reuses completed AI response caches, but normalization can redo completed encoding stages. This is retry support, not full resumability.
- Browser playback uses ordinary video events and is approximate. Rendered output and actual editor import remain the precision checks.
- Exports reference local normalized media, not camera originals; portable packaging and relinking remain unimplemented.
- The ranker uses capped clip duration, not requested-duration fit. It stores the brief with labels but does not directly encode that brief as a model input.
- The code records an uncertainty string; lack of that string is not a calibrated confidence estimate.
- Generated-cache removal, project deletion, and a user-facing backup/restore flow remain unfinished.
- The worker and launcher use Unix-specific APIs. Current setup instructions target macOS; Windows support is not established.

## Deferred validation tasks

Interviews are deferred at the creator's request. Keep this checklist for later;
it is not a scheduled reminder.

- Observe how montage creators currently search and select footage.
- Test whether story sections speed up decisions or add unnecessary organization work.
- Compare the complete import-to-editor workflow with their existing process.
- Measure time saved, repeated use, retrieval misses, and handoff failures on their footage.
- Test willingness to adopt or pay only after showing a working workflow.
- Choose the next niche or feature from those failures and repeated needs.
