# Project status and release checklist

Updated: 2026-10-07. Status: local development preview; release gates remain open.

## What exists

| Area | Implemented | Evidence and remaining work |
| --- | --- | --- |
| Manual assembly | Projects, import, proxies, descriptions, story sections, drag/reorder, frame trimming, save/reopen, undo | Backend tests cover persistence and frame rules. Isolated browser tests cover three generated inputs, repeated placement, exact saved ranges/order, undo, playback and outputs. Real footage remains separate. |
| Processing | One SQLite-backed worker, progress, cancel/retry, response caching | Real worker subprocess tests cover pending/interrupted normalization/render, second-worker refusal and explicit retry. Encoding restarts; it is not stage-resumable. |
| Output | MP4 render, FCP7 XML, OTIO, media manifest | Generated-media tests check render duration and XML round-trip through OTIO. No verified import in DaVinci Resolve yet. |
| AI adapter | Video chunks, validated observations, embeddings, story proposals, cost reservations | Fake-provider tests cover response validation, caching, budget, and failure. No real provider or quality benchmark has been verified. |
| Search | Keyword matching and optional description-embedding similarity | Manual keyword behavior tested. The 20-query real-footage benchmark has not been completed. |
| Training | Permission-aware judgments, grouped split, logistic-regression experiment, report export | Script and labeling interface exist. No trained or deployed custom model has been established. |
| Project access | Source opens in VS Code; onboarding, architecture, contribution and learning docs; private GitHub remote | Fresh macOS checkout/virtual environment installation is verified below. Public release and remote CI remain separate. |

The generated demo is a technical fixture. It is not real sports footage, a
trained model, or a demonstration of AI retrieval accuracy.

## Latest engineering checkpoint

Next-milestone planning: [REAL_FOOTAGE_PLAN](REAL_FOOTAGE_PLAN.md) defines app
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
The private GitHub remote contains tracked source and documentation. Making the
repository public remains a separate, explicit release decision.

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

- [ ] Import a coherent set of owned or appropriately licensed real training clips.
- [ ] Assemble three clips; reopen the project and confirm the exact saved order and boundaries.
- [ ] Render and check mixed silent/audio, portrait/landscape, and variable-frame-rate inputs.
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
- [ ] Review release contents and explicitly make the repository public when ready;
  keep credentials and personal media excluded.

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
