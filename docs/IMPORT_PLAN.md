# Implementation plan: resilient multi-file import

Planned 2026-10-07 against foundation commit 7286856. Execution is authorized by
the creator after planning. This is Phase A1 of REAL_FOOTAGE_PLAN.md, not the entire
real-footage milestone. Implementation and verification are recorded in the execution evidence below.

## Outcome and boundaries

A batch containing valid A, corrupt B, and valid C registers A/C, explains B's
failure, and remains usable. The creator can tell uploaded files from playable
files and recover without duplicating assets. Preserve existing manual editing.

Keep the current API, SQLite worker, supported formats, project limits, hash
deduplication, and single expensive media worker. No cloud calls, training, footage
downloads, live computer-use walkthrough, codec expansion, publishing, or unrelated
media optimization. No new queue service or framework. No database migration is
expected; justify one before expanding scope.

## Current behavior and design

App.tsx awaits each import inside one shared task. The first thrown request ends
the loop. The API already atomically registers an asset and normalize job, but its
duplicate response contains no job ID and most failures are unstructured 400s.

Extract batch orchestration into src/features/library/imports/ (or a comparably
small focused module). Keep App.tsx responsible for project selection and refresh;
keep presentation separate from request/error decisions. Reuse src/lib/api.ts.

Use a batch ID, captured destination project ID, and stable per-file row ID (not
filename). Retain each File only in browser memory until retry is no longer needed.
Track upload outcome separately from asset preparation: a duplicate can point to
an asset that is still preparing or failed. Store returned asset/job IDs, not extra
copies of the whole project. Derive preparation state/counts from refreshed assets.

## Observable behavior and recovery

- Show filename, waiting/uploading state, registered/preparing/ready state, an
  already-imported badge, and actionable failures. Use text and accessible status
  announcements, not color alone. Do not invent upload percentages.
- Upload sequentially. Prevent overlapping batch dispatch within this browser.
  A file validation failure continues to the next file. A project limit, low disk,
  disconnection, unknown server failure, or missing project pauses queued requests.
- Expose resume for paused work and retry for eligible failed uploads. Do not
  silently auto-retry potentially committed uploads or loop indefinitely.
- Add stable import error codes and recovery scope to API error responses while
  preserving the existing detail string/status behavior for other callers.
  Distinguish file-invalid/file-too-large from project-capacity/disk/server issues.
  Do not classify errors by matching English message strings. Unknown errors pause
  conservatively. Browser checks are hints; backend probing/limits stay authoritative.
- Extend ApiError with optional structured fields without changing callers that
  only consume its message/status. Distinguish timeout/network uncertainty from a
  definite rejection. Refresh the destination project after every accepted request
  and after partial/uncertain outcomes without discarding unsaved board drafts.
- On timeout, say the upload may have reached the server. Reconcile known asset
  IDs; never identify success from filename alone. An explicit retry can reuse
  existing server hash deduplication. No automatic whole-batch re-upload.
- For failed preparation, use the existing job retry action, not import. Preserve
  association with the latest normalization job, including duplicate assets and
  retries. If current responses cannot supply it reliably, add a minimal read-only
  association to existing project/asset responses; do not rely on only the latest
  40 project jobs or expose arbitrary job payloads. Guard retries against duplicate
  in-flight preparation work and update the row to the returned replacement job.
- Capture destination before awaiting anything. Switching projects cannot redirect
  remaining uploads, apply old refreshes to the new board, or display another
  project's rows as its own. Keep batch state associated with its project; show its
  rows again on return. Check unmount/disposal before dispatching further requests.
- Browser reload preserves accepted assets/jobs, NOT unuploaded File objects.
  Explain that pending local files must be selected again. Do not claim resumable
  byte uploads or persistent browser queues. Existing saved board choices survive.
- Release retained File references when rows are cleared or no longer retryable.
  Clearing completed rows must never delete source media, assets, or board edits.

## Implementation order

1. Inspect current code/tests and explain this plan in the execution chat before
   runtime edits. Record any necessary adjustment here and its reason.
2. Add the narrow API error/retry-association contract and backend regression tests.
3. Implement the batch controller/state transitions, then its small status panel
   and App.tsx integration. Preserve existing refresh race protections.
4. Add isolated browser regression cases. Use real generated media for normal
   import paths; bounded request interception/fault injection is appropriate for
   network/timeouts. Label simulated evidence accurately.
5. Run verification, review the diff, update STATUS and architecture/code-map docs
   only where changed, and provide a local checkpoint with exact evidence.

## Acceptance tests

| Case | Required evidence |
| --- | --- |
| Valid A / corrupt B / valid C | A/C become playable; B has a named failure; no false all-success notice |
| Duplicate A, including identical names with different content | Hash identity governs deduplication; no extra asset/job for a true duplicate; distinct rows |
| Preparation fails then retries | Existing source reused; one eligible replacement job; no re-upload |
| Offline or ambiguous timeout | Remaining requests pause; accepted work remains; explicit recovery does not duplicate assets |
| Capacity / disk limit | Remaining files pause; backend guards unchanged; actionable reason |
| Project switch during delayed import/refresh | All uploads stay in original project; new project's board/assets untouched |
| Reload after acceptance | Accepted assets/jobs persist; no promise that waiting File objects survive |
| Mixed outcomes and empty library | Accurate derived counts; duplicate badge does not imply ready |
| Existing workflow | Saved choices, trimming, search, preview, export tests retain their behavior |

Run backend pytest, frontend build and lint, and the isolated browser suite. Test
data and processes must be harness-owned, never the creator's saved projects.
Report exact commands/results and any untested cases. Passing fixtures is not a
real-footage or Resolve import check. No paid calls or external publication.

## Learning and handoff

Explain browser upload -> API registration -> queued preparation -> asset refresh.
The key lesson: an accepted upload is not yet a playable clip; retries must respect
which stage failed. Link the changed controller, API handler and regression test.

Exercises follow milestone order but are optional, not delivery gates. The creator
has not reserved a code change in this task: implement a complete feature. Offer a
follow-along exercise to trace one row's state changes and predict what survives a
reload; leave a small test extension for independent practice. Respect any later
explicit claim of ownership before editing that portion.

## Confirmed execution design

Before runtime edits, the execution chat confirmed the ordered plan above. No
migration is needed. Add `preparation_job` (id/status/progress/message) to asset
responses using all normalization jobs for that project, not the 40-row activity
window. Duplicate import responses return that job's ID. An old failed-job retry
reuses a newer pending/completed normalization instead of re-encoding it again.
Import refreshes merge only assets/moments/jobs into the active project so board
revisions and draft text cannot be replaced by an import response.

A file-invalid/file-too-large row is terminal for those bytes and releases its File;
the user selects a corrected file. Recoverable/uncertain upload rows retain File
only in memory for explicit retry. Resume dispatches only waiting rows; failed rows
have their own Retry upload action. One controller per mounted app serializes all
upload dispatch across projects. Leaving a project keeps its batch attached there;
unmount stops further dispatch. Clearing local outcomes does not delete server data.


## Execution evidence — 2026-10-08

Phase A1 is implemented. The planning checkpoint (`ec03f3b`) preceded runtime
changes, followed by the API contract checkpoint (`0b57c55`) and frontend/tests (`cf810d0`).
No schema migration, dependency change, extra worker, or supported-format expansion
was needed. Existing limits and atomic source/asset/job registration are preserved.

| Check | Actual evidence |
| --- | --- |
| Backend | `.venv/bin/pytest -q`: 45 passed in 20.26s; one existing Starlette deprecation warning. |
| Frontend | `npm run build`: TypeScript and Vite passed. |
| Lint | `.venv/bin/ruff check server tests scripts --select E9,F63,F7,F82`: passed. |
| Full isolated Playwright | `npm run test:e2e`: 24 passed in 39.8s (12 browser scenarios and 12 controller/board checks). Earlier expanded run: 22 passed in 39.3s. |
| Mixed outcomes / identity | Real generated files: valid A, corrupt B, valid C; identical filenames with different bytes stay distinct; renamed identical bytes reuse an asset/job. |
| Uncertain response | Browser test registers a real upload, discards its response, verifies pause, then explicitly retries and receives the existing asset. Timeout classification is exercised with a controlled timer/fetch test. |
| Capacity / disk | Backend guards tested with reduced capacity/free-space fixtures; browser response interception verifies pause and explicit recovery. No disk was actually filled. |
| Preparation retry | Backend injects a normalization failure, hides its job behind 45 newer activity rows, then verifies source reuse, replacement-job association and stale-retry deduplication. Browser retry UI uses simulated failed/queued worker responses and asserts no upload request. |
| Ownership / saved edits | Delayed import stays with its captured project; the other project's board/assets and draft are untouched. Delayed import refresh cannot replace a concurrently saved section. |
| Reload / memory | Accepted assets persist; waiting Files do not resume after reload. Controller tests check terminal File release, local clearing, disposal and overlap refusal. |
| Documentation / cleanup | `git diff --check` passed; all 84 local Markdown links resolve; both browser-run temporary roots were removed. |
| External boundaries | Synthetic fixtures and harness-owned processes/data only. No footage downloads, paid calls, training, live computer-use demo or remote push. No real-footage/Resolve/provider validation claimed. |

One controller belongs to the mounted application. Uploads may finish for a project
while another is open; only its matching project displays the outcomes. Browser
refreshes merge media/job fields, preserving board and draft state. A row's upload
outcome is distinct from the asset's current preparation state. The footage summary
counts unique saved assets, so duplicate upload rows do not inflate ready counts.

Resume sends only waiting files. Retry upload sends only its selected eligible row.
Invalid bytes must be corrected and selected again. Explicit retry after an uncertain
response can resend the entire file; content hashing prevents duplicate registration,
not retransmission. Closing/reloading a tab loses waiting File objects. Clearing local
outcomes never deletes managed sources, registered assets, or accepted board choices.

Next scope is Phase A2 in REAL_FOOTAGE_PLAN: independent generated-media checks for
orientation, frame timing and audio. Performance measurement (A3), real-footage
acquisition/walkthrough, Resolve import and provider evaluation remain later gates.

### Independent review follow-up — 2026-10-08

Review reproduced and fixed the inverse editing/import race: an older board-save
response restored old asset/job state. Board saves now merge their own fields into
current state, matching the existing media-only import merge. Review also made
worker failure/cancellation job and asset updates atomic to prevent a retry from
interleaving between commits. See [STATUS](STATUS.md) for the red/green evidence:
47 backend tests, 25 Playwright checks, build and fatal-error lint passed after fixes.
These corrections preserve the A1 design; A2 remains the next validation task.
