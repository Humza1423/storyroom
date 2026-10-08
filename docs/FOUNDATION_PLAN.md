# Foundation completion: executable plan

Prepared 2026-10-07 from the current source. This is planned work, not completed
implementation. Read AGENTS.md, PRODUCT.md, STATUS.md, and ARCHITECTURE.md first.
Execute in the dedicated Storyroom repository. Preserve unrelated local changes.

## Outcome and scope

A contributor can install Storyroom, start it, run tests without touching personal
projects, change the frontend confidently, upgrade saved data, and recover from a
server or worker interruption. The manual import-to-export workflow works without
AI. Foundation completion does not establish model quality, market demand, or a
verified Resolve import. Those are separate gates.

The current code already implements import, normalization, manual descriptions,
sections, selection, trim/reorder, revisions/undo, preview/render, XML/OTIO export,
and optional AI adapters. Preserve these behaviors. Do not build a new framework,
replace SQLite, redesign the UI, add finishing tools, or train a model in this task.

Expect approximately 3–5 focused development days, depending on browser/setup
failures. Work as five reviewable checkpoints, not one large rewrite. If time is
short, report unfinished gates rather than describing the foundation as complete.

## 1. Isolate and own the browser test environment

Current problem: Playwright uses ports 5173/8765, a manually running application,
`data/fixtures/browser-test.mp4`, and a pre-seeded demo. It can write test projects
into the user's database. The mobile test assumes a particular demo already exists.

Inspect `playwright.config.ts`, `e2e/workspace.spec.ts`, `scripts/dev.py`,
`server/config.py`, `vite.config.ts`, and the API's explicit origin allowlist.

Implement:

- A test-owned temporary data root and generated H.264 fixtures. Every API/worker
  subprocess must receive the same explicit `STORYROOM_DATA`; no fallback to `data/`.
- Dedicated configurable loopback ports for tests. Pass the backend target to
  Vite's proxy and base URL to Playwright; update exact permitted origins as needed.
  Keep normal 5173/8765 defaults and localhost restrictions. Do not accept arbitrary
  browser origins or silently reuse an unknown server on the selected test port.
- A harness that starts API, worker, and frontend; waits for actual readiness with
  bounded timeouts; captures failure diagnostics; and stops only processes it owns,
  including on failed tests. Check for an occupied port and fail clearly.
- Explicitly disable cloud calls in every test process, even if the local `.env`
  contains a key. Set empty provider credentials, pricing confirmation false, and
  zero paid budget through environment overrides; never log keys.
- Independent tests: the mobile test creates its own project/board or uses a
  documented test-only fixture setup. No ordering dependency or developer demo.
- A three-clip manual path covering import, ready state, sections, repeated use of
  one moment, frame trim, reorder, save/reload, undo, playback, render, and export.
  Retain responsive checks. Use conditions/polling rather than arbitrary sleeps.

Accept when `npm run test:e2e` starts its own stack from a clean test root and
passes twice without changing the normal project's stored state or files. Demonstrate
isolation with a separate sentinel development root and/or harness assertions;
do not assert byte-identical files in a concurrently active user database. No orphan
test processes, paid calls, or cleanup outside the validated test-owned directory.

Learning checkpoint: explain how test isolation prevents a successful test from
corrupting a real project. Show the actual data root and server ownership boundary.

## 2. Introduce safe database upgrades

Current problem: `server/db.py:init()` creates tables and inserts version 1. It
does not apply versioned upgrades. API and worker both initialize the database.

Implement a small ordered SQLite migration runner with an exclusive write
transaction, version validation, and rollback. Adopt the existing version-1 schema
without resetting projects, revisions, assets, moments/FTS, jobs, cache, usage, or
feedback. Confirm schema changes and version updates commit together. SQLite
`executescript` can change transaction behavior; do not assume an outer transaction
makes all migration statements atomic. Reject newer unsupported schemas clearly.

Before an existing database needs an actual upgrade, create a consistent backup
using SQLite's backup mechanism; account for WAL rather than copying only a live
`.sqlite` file. Do not manufacture a production version-2 change just to demonstrate
the runner. Test subsequent migrations with controlled migration fixtures.

Accept with tests for a fresh database, existing v1 with representative saved data,
repeat initialization, competing startup initializations, failed migration rollback,
backup validity, and refusal of an unsupported future version. Reopen an existing
project and show its choices/revisions survive. Never test on the user's only copy.

Learning checkpoint: explain schema version versus migration, and why an application
upgrade must preserve stored decisions.

## 3. Refactor the frontend in small extractions

Current problem: `src/main.tsx` contains roughly 1,700 lines of types, request code,
board state, components, and dialogs. Separate boundaries before adding more UI.

Suggested destinations (adapt names to the actual code):

- `src/types.ts`: shared API shapes; keep aligned with backend contracts.
- `src/lib/api.ts`: requests, local header, structured errors, bounded timeouts.
- `src/lib/timecode.ts`: frame/timecode formatting.
- `src/features/board/`: pure board changes and section/selection presentation.
- `src/features/library/`: asset/moment/search presentation.
- `src/features/preview/`: source and assembly playback.
- `src/components/`: shared dialogs and processing/export controls.
- `src/App.tsx`: orchestration; `src/main.tsx`: mounting and styles.

Extract types/helpers first, then components, then only necessary state logic.
Avoid a global state library or a hook for every function. Keep stable backend
contracts, frame rules, duplicate placements, revision-conflict behavior, proposals,
and unsaved edit handling. Guard against late responses for a previously selected
project overwriting the active project; test observable race failures if found.

Accept with TypeScript/build and isolated browser tests after meaningful extractions.
Add focused tests for nontrivial board rules or races, not snapshots of every JSX
component. Reordering, trim, undo, save/reload, and accepted-edit preservation must
still work. Use this as a refactor; any functional bug fixes need explicit evidence.

Learning checkpoint: trace one UI action through component → request → API → saved
state, and explain which state belongs in SQLite versus a browser component.

## 4. Make startup and interruption behavior understandable

Current problem: the launcher starts processes without a readiness check and may
exit without identifying the child failure. The UI mostly exposes request errors.
Worker startup marks running jobs failed; process-level recovery is not yet proven.

Implement:

- Preflight checks for Python/Node expectations, installed dependencies, FFmpeg
  and ffprobe, the data directory's write access, and selected port availability.
  Print specific corrective actions. No cloud key is required for manual startup.
- Announce readiness only after the API responds and the frontend serves. Report
  which child failed, preserve relevant stderr, exit nonzero, and stop owned children.
- Distinct loading/connected/disconnected UI behavior with retry/reconnect. Preserve
  the current project and entered text during disconnection. Avoid silent failed
  saves; restore a correct connection indicator when the API returns.
- Process-level tests for restart after pending and interrupted normalization/render
  work. Completed assets and board revisions survive. Interrupted work is visibly
  retryable, with consistent job/asset status, no duplicated accepted selections,
  and no automatic replay of paid requests. Fix observed inconsistencies.
- Check that a second worker fails clearly without altering the first worker's jobs.

Accept with reproducible occupied-port, missing-tool, API-offline/reconnect, worker
restart/retry, and launcher-cleanup checks. Use isolated data/processes. Full media
stage resumability and automatic filesystem orphan deletion remain deferred; document
the remaining crash boundary and do not delete unreferenced files speculatively.

Learning checkpoint: explain persistent database state versus process memory, and
why retryability is different from resuming an encoding at the exact interruption.

## 5. Reproduce installation and checks for contributions

Current problem: JavaScript has a lockfile; Python dependency ranges are not locked;
there is no checked-in automated contribution pipeline.

Choose a single Python lock/install workflow, preferably `uv.lock` with documented
locked install commands, without breaking the current pip path before validating
the replacement. Include dev dependencies and document the supported Python version.
Keep FFmpeg an explicit system dependency. Use `npm ci` with package-lock.json.

Add a small GitHub Actions workflow for backend tests, TypeScript/build, and isolated
Playwright. Install FFmpeg and required browser dependencies. No provider credentials
or real online footage in CI. Keep the baseline targeted fatal-error lint; introducing
style rules should not trigger a repository-wide formatting rewrite in this task.
Ubuntu CI is automation coverage; keep the supported user platform explicitly macOS
until other environments have real installation evidence.

Accept from a fresh checkout with a new virtual environment and no local `data/`,
`.env`, demo, or existing servers. Follow README, generate fixtures, run all checks,
and launch the manual app. Record exact commands/results and setup limitations.
Adding a workflow file is not a remote CI pass; report remote results only if it ran.

Learning checkpoint: explain why declared dependency ranges and reproducible resolved
versions are different, and what CI can prove without Resolve or a provider account.

## Final foundation acceptance record

Record actual results in STATUS.md and a short evidence table in this document:

- Backend suite, frontend build, and full isolated browser suite pass.
- Browser suite also passes a second fresh run; tests create no personal projects.
- Existing database upgrades/reopens without losing editing choices.
- Three-clip workflow saves exact ranges/order, renders, and produces XML/OTIO.
- Startup failure and disconnect/reconnect behavior are actionable.
- Worker interruption is retryable and does not erase completed work or replay AI.
- New-checkout install follows README; dependency locks and CI are present.
- No cloud calls occurred during foundation tests.
- Real footage and a real Resolve import are explicitly still separate checks.

Update README, CONTRIBUTING, ARCHITECTURE, STATUS, and HANDOFF where behavior changed.
Finish with changed-file links, test evidence, unresolved limits, one user exercise,
and the next task. Use focused local commits on `codex/complete-foundation`; do not
rewrite published history. Do not claim completion if any required gate is open.

## Next task after these gates

Use [FOOTAGE_TEST_SET](FOOTAGE_TEST_SET.md) to prepare the small licensed exercise
set. Prove manual import → saved three-clip montage → rendered review → Resolve
import first. Then test one bounded real AI analysis with verified model/rates and
explicit cloud permission. Gather human timestamp judgments before measuring search.

## Prompt to give the executing Codex session

> Work in the Storyroom repository. Read AGENTS.md, docs/HANDOFF.md,
> docs/FOUNDATION_PLAN.md, and the linked product/status/architecture context. Implement
> the five foundation checkpoints in order on codex/complete-foundation, preserving
> unrelated changes and existing projects. Treat the plan's acceptance gates as the
> completion criteria; adapt routine details to the source and explain deviations.
> Explain the purpose, relevant code boundary, and one engineering concept during
> each checkpoint. Run the required checks, keep evidence/status/setup docs current,
> and finish with changed-file links, limitations, a hands-on exercise, and the next
> task. Use synthetic fixtures for automated tests. Do not make paid calls, train
> models, or download real footage during the foundation task. Execute the work,
> rather than returning only another plan.
