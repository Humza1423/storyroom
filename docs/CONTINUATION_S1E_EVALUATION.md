# Activity continuation checkpoint — 2026-10-29

The badminton worker now reaches the available full activity, **frames 0–900**,
and selects **0–600** for a 20-second request. **S1 remains open.** The later
jumping-jack endpoint misses its frozen tolerance, and the historical push-up
answer key was found to cut off the movement. These findings do not establish
general search accuracy or close the four-case gate.

## Diagnosis and changes

- The historical badminton `boundary_conflict` cannot be reconstructed. A new
  unchanged request did not reproduce it: Gemini instead proposed a numerically
  valid but visibly early stop at source frame **715** (local **21.333s**).
  A one-off focused correction repeated that endpoint. Actual playback shows
  court activity continuing afterward; time-to-frame conversion was consistent.
- A short tail, source **685–900**, recognized the same activity through the
  source end. Its returned **7.167s** was rejected because the exact crop lasts
  **215/30 = 7.166666…s**, although the request itself displays **7.167s**.
  Validation now accepts only that exact displayed rounded endpoint; it never
  clamps times. Other out-of-range values and invalid cached frames still fail.
- The worker now rechecks an interior broad-activity stop once, with one second
  of established overlap and at most eight supplied seconds. It requires the
  existing same-activity evidence and connected interval. Specific moves and
  source-edge stops avoid this call. Uncertainty, failure or a further suspicious
  stop retains partial footage. Pending/verified probe state survives retries.

This is selective inspection using the existing worker and Gemini contract.
Retrieval, exact vector search, indexing, and database schema were not changed.
The worker identity is `activity-v5-short-stop-recheck`.

## Frozen evidence and live results

The original [four-case key](../tests/fixtures/continuation-cases-v1.json) and
[historical report](ACTIVITY_REVIEW_EVALUATION.md) remain unchanged. The new
[supplementary key](../tests/fixtures/continuation-extent-supplement-v1.json)
was independently reviewed before new calls. The separately labeled
[tail probe](../tests/fixtures/continuation-tail-probe-v1.json) is a development
diagnostic derived afterward, not held-out validation.

| Case | Evidence | Current conclusion |
| --- | --- | --- |
| Badminton | Long crop stopped at 715; short tail reached 900. Real worker retained 715 as partial during HTTP 503 failure, then resumed to 0–900, complete; requested cut 0–600. | Corrected on this prepared-copy development example. |
| Opening jumping jacks | Historical 0–80 before burpee. | Preserved control; no new live rerun. |
| Later jumping jacks | Continuation returned 330–395; worker preserves established start 319. Frozen expected end 398–404. | Same occurrence, but end is three frames early; fails this gate. |
| Pasta | Historical extension 120–610; available source extent 0–610. | Preserved control; no new live rerun. |
| Push-up | Dense independent review shows descent through 650, low position through 709, camera edit at 710, then rising in front view through roughly 750. | Historical target 681–696 omits the rise. Same physical repetition across the edit is uncertain. Do not optimize toward that target or score it as a pass. |

The planned 6fps push-up endpoint experiment was not integrated: the original
success criterion was disproven, and the authorized call allowance is exhausted.
A valid unambiguous complete-movement example is required before testing that
hypothesis. Historical failures remain visible rather than being relabeled.

## Usage, identity, and limits

Model: `gemini-3.5-flash-lite`, unpaid tier, 3fps extraction and API metadata.
New ledger: **8/8 generation attempts**, **97.83/180 supplied video seconds**,
including two HTTP 503 attempts. Recorded API estimate is $0. The exhausted
historical ledger was not reset. No embeddings or paid fallback were used.

The worker comparison used an exact copy of prepared `inputs/f02.mp4`, SHA-256
`743a8515fabecab16296a9cf1ea2fbac72de4d83d62db97fb71dfb295af9d2d3`, in the
isolated `s1e-cache` data directory. This is **not** the production session's
different proxy hash. The first long request was an exact legitimate cache hit;
the tail used the worker's actual prior evidence, not a transplanted evaluation
answer. Failed inspection retained frame 715 and incomplete status in the job.
Explicit resume made one successful new call, reached frame 900, and retained
the exact 600-frame cut. A direct tail probe had different prior evidence and
was not substituted into this worker cache.

Worker diagnostics across failure/resume: one cache hit, three generation
attempts (two 503s and one success), 21.5 supplied seconds, 17.98s total measured
inspection time, 1,927 input and 157 output tokens on the successful response.
Historical errors remain in diagnostics after recovery. This single run is not
a latency benchmark. The conditional probe can add up to eight video seconds per
activity/direction; a later unresolved stop remains partial instead of starting
another probe loop.

Local evidence and media stay ignored:

- `data/evaluation/gemini-fresh/s1e-ledger.json`
- `data/evaluation/gemini-fresh/s1e-cache/storyroom.sqlite`
- `data/evaluation/gemini-fresh/evidence/s1e-badminton-app.png`

## Product check and reproduction

The preserved app at `http://127.0.0.1:15176/`, project **Gemini fresh validation
v1**, still contains eight clips and five accepted cuts totaling 1,413 frames.
Actual source playback of **f02.mp4** from 23.8s reached 30s; the same court
activity is visible at 29s. This confirms the long response's early stop through
the app. It is a source-playback check, not a claim that the normal project's
Visual AI query has been rerun under the new worker. Its database quick check
passes; accepted cuts were not changed.

To review without more model calls: open that project, use Keyword mode, preview
f02.mp4, and scrub 23.8–30s. Existing activity-selection instructions in the
historical report demonstrate activity review, exact adjustment, save/reopen,
render and Resolve 21.1.2 handoff. That earlier handoff was not repeated here.
Current isolated browser regressions cover those controls and exact saved frames;
current generated-media regressions cover render/export correctness. The full
new search-result-to-Resolve demonstration remains part of the open gate.

`scripts/evaluate_continuation_s1e.py --replay badminton-tail-01` replays numeric
validation without network calls. The bounded runner requires a frozen source
hash and explicit access/playback flags for dispatch. Its ledger is exhausted;
do not create another ledger to bypass the cap.

## Next action

Keep S1 open. Freeze a clear push-up repetition whose preparation and finish are
visible in one shot; retain the edited source as an uncertainty case. Validate
the later-jacks finish and new worker behavior on the normal prepared proxies,
then run the required result-review/add/reopen/render/export demonstration.
Do not start S2 or claim all four original examples passed. S2 generalizes
complete movements after this gate; S3 addresses grouping/inspection reuse;
S4 is fresh release validation.
