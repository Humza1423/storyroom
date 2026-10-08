# Project status and release checklist

Updated: 2026-10-07. Status: local development preview; release gates remain open.

## What exists

| Area | Implemented | Evidence and remaining work |
| --- | --- | --- |
| Manual assembly | Projects, import, proxies, descriptions, story sections, drag/reorder, frame trimming, save/reopen, undo | Backend tests cover persistence and frame rules. Browser workflow tests exist; a complete fresh browser run is still needed for this checkpoint. |
| Processing | One SQLite-backed worker, progress, cancel/retry, response caching | Tests cover job deduplication and cancel/retry. Full stop/restart and interrupted-media tests remain. |
| Output | MP4 render, FCP7 XML, OTIO, media manifest | Generated-media tests check render duration and XML round-trip through OTIO. No verified import in DaVinci Resolve yet. |
| AI adapter | Video chunks, validated observations, embeddings, story proposals, cost reservations | Fake-provider tests cover response validation, caching, budget, and failure. No real provider or quality benchmark has been verified. |
| Search | Keyword matching and optional description-embedding similarity | Manual keyword behavior tested. The 20-query real-footage benchmark has not been completed. |
| Training | Permission-aware judgments, grouped split, logistic-regression experiment, report export | Script and labeling interface exist. No trained or deployed custom model has been established. |
| Project access | Source opens in VS Code; onboarding, architecture, contribution and learning docs; private GitHub remote | Clean-machine installation and a deliberate public open-source release remain pending. |

The generated demo is a technical fixture. It is not real sports footage, a
trained model, or a demonstration of AI retrieval accuracy.

## Latest engineering checkpoint

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

### 1. Reliable and understandable local foundation — in progress

- [x] Open the source in a code editor and provide a file map.
- [x] Add an honest status record and saved release checklist.
- [x] Commit asset registration and its preparation job atomically.
- [x] Test queue-write failure followed by a successful import retry.
- [x] Record the initial local Git checkpoint with source, docs, and tests; no GitHub remote configured.
- [x] Create a private GitHub repository, configure `origin`, and push `main`.
- [ ] Isolate browser tests from personal projects and remove dependence on a pre-seeded demo.
- [ ] Add tested, versioned database upgrades before changing the stored schema.
- [ ] Split frontend types, API calls, board logic, and components into focused modules.
- [ ] Lock Python dependencies and add automated checks for contributions.
- [ ] Improve startup diagnostics and the disconnected-server experience.

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
- [ ] Test installation on a clean environment and review dependency/media licenses.
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

- `src/main.tsx` contains most frontend behavior in one large file. Refactoring is due before substantial UI expansion.
- `schema_versions` currently marks the initial schema; it is not a migration runner.
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
