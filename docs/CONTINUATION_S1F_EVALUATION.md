# S1f continuation and specific-move endpoint check — 2026-11-05

This is a bounded **development comparison**, not a held-out search accuracy
result. The two frozen keys are
[`continuation-s1f-live-v1.json`](../tests/fixtures/continuation-s1f-live-v1.json)
and [`continuation-s1f-endpoint-v1.json`](../tests/fixtures/continuation-s1f-endpoint-v1.json).
They were independently reviewed from dense source frames; the football source
was also played before the endpoint request. Previous labels and results were not
changed. Source media and the numeric provider ledger remain ignored under
`data/evaluation/gemini-fresh/`.

## Results

| Case | Frozen expectation | Observed | Judgment |
| --- | --- | --- | --- |
| Later jumping jacks before burpees | End 398–404 | Same activity to frame 399, observed stop | Pass for this one occurrence; adjacent burpee excluded. |
| Football first kick, narrow before crop | Begin 52–58 | Crop edge claimed as stop, rejected | Safe rejection; 1.1-second context is insufficient. |
| Football first kick, narrow after crop | End 72–80 | Crop edge claimed as stop, rejected | Safe rejection; 1.33-second context is insufficient. |
| Football first kick, six-second/6fps endpoint crop | End 72–80 | Connected interval 50–90, observed stop | Complete move visible, but end is 10–18 frames beyond the strict key. Boundary gate fails. |

The endpoint inspector now extracts the actual six-frame-per-second video and
sends matching video sampling metadata. It only follows an established
`specific_move` in a bounded six-second neighborhood. Its cache key has a separate
contract version. The worker schedules at most one probe per direction after an
interior observed stop; completed probe evidence survives cancellation/resume.
The worker clips the overlap anchor to the actual probe crop. Invalid timestamps,
unsupported continuity and crop-edge stops still fail closed.

Unpaid Gemini `gemini-3.5-flash-lite`: **4/4** generation attempts, **16.43/60**
supplied video seconds, zero retries, estimated **$0**. The final six-second call
used 2,722 input and 162 output tokens and took 6.43 seconds. Its frame 50–90
interval contains the first kick and recovery; it is not evidence of frame-exact
movement completion across sports. The earlier S1e ledger was not reset.

## Product and release status

The canonical development app used
`data/evaluation/gemini-fresh/session/storyroom.sqlite`, project **Gemini fresh
validation v1**, eight prepared clips. Database quick check passed and a local
backup was made before opening it. The existing football placement was opened in
the player with exact saved frames **315–900**; the five accepted placements still
total **1,413 frames / 47.1 seconds**. The new evaluation answer was not copied
into the user's project. The already completed browser workflow covers activity
review, frame adjustment, save/reopen, render and export, but an updated Visual AI
search through this app and fresh Resolve import were not performed in S1f.

Verification: **402 backend tests passed** after the geometry fix, production
build passed, **39 isolated browser tests passed**, focused Ruff check passed.
One existing Starlette/httpx deprecation warning remains. Actual CI is recorded
after pushing the checkpoint.

**S1 stays open.** The previous strict four-case gate cannot be called passed:
the historical push-up label omitted the rise, and this football endpoint remains
outside its frozen ending. The next focused evidence step is S2's independently
labeled complete-move set across varied actions, including source/crop truncation,
before promoting 6fps endpoint inspection as a general accuracy improvement.
Keep the result editable and its timing approximate.
