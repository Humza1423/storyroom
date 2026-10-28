# Activity extent and editor-selected cuts — 2026-10-27

## Verdict

**The editor can choose and preserve a cut across an established activity. The
continuation ticket remains open: the model passed two of four reviewed cases.**
Do not start S2 or call search complete. A suggested cut is a starting point, not
an automatically proven good edit.

Two different things were tested:

1. **Model behavior:** can Gemini follow the activity already found, without
   jumping to another occurrence or claiming an unsupported ending?
2. **Product behavior:** can the editor preview an activity, choose exact frames,
   add them to a Storybin, reopen, render and import those cuts into Resolve?

Passing the second does not erase failures in the first.

## Controlled Gemini comparison

The [frozen four-case key](../tests/fixtures/continuation-cases-v1.json) records
the source links, authors, licenses, input hashes, anchors and reviewed acceptable
boundaries. These are development examples, not a new held-out accuracy study.
Existing dense-frame review was followed by actual playback review before live
dispatch. Historical labels and results were not rewritten.

The paired calls used identical source crops and 3fps sampling with
`gemini-3.5-flash-lite`. The baseline asked the general discovery question; the
candidate asked to continue the particular established activity. Models,
retrieval and acceptance tolerances were not changed between these calls.

| Case | General discovery | Anchored continuation | Verdict |
| --- | --- | --- | --- |
| Badminton with a pause | Proposed a later interval at crop-local 14.667–19.667s, rejected as `anchor_unrelated` | Rejected as `boundary_conflict` | Failed. The exact contradiction was not retained in this run; do not guess it. |
| Jumping jacks before burpees | Frames 0–80, within reviewed end tolerance 75–86 | Frames 0–80; observed stop | Passed this case; following burpee excluded by the returned range. |
| One push-up before a later repetition | Returned frames 710–790, disconnected from anchor 630–660 | Returned 630–710, connected but beyond reviewed end tolerance 681–696 | Still failed. Following the anchor improved; endpoint accuracy did not pass. |
| Continuous boiling pasta | Frames 120–610, reaching the source end | Frames 120–610, same activity reaching the source end | Passed the inspected extension. Source end means no more available footage, not that boiling naturally stopped. |

Frame ends are exclusive at 30fps. The push-up candidate's end, frame 710
(23.667s), is 14 frames past the latest reviewed acceptable end (23.2s). It
must not be relabeled a pass because its model-written explanation sounds good.
The worker retains previously established frames; these raw extension intervals
are not independently created final editing cuts.

The baseline had **two expected-boundary passes out of four**, but its semantic
continuity was not separately tested by that contract. The candidate had **two
continuity-plus-boundary passes out of four**. This does not establish an accuracy
improvement. There were no provider HTTP failures in these eight calls; each
variant had one validation rejection. The baseline push-up was a wrong occurrence
rather than a provider failure.

### Usage and elapsed time

| Measurement | General discovery | Anchored continuation |
| --- | ---: | ---: |
| Generation attempts | 4 | 4 |
| Supplied video seconds | 59.33 | 59.33 |
| Total elapsed seconds | 81.97 | 8.99 |
| Input tokens reported | 14,168 | 13,629 |
| Output tokens reported | 730 | 638 |

Per-case elapsed times, baseline → candidate: badminton **35.37 → 2.61s**;
jacks **12.82 → 1.75s**; push-up **31.02 → 2.04s**; pasta **2.76 → 2.58s**.
These are one sequential sample per case, including preparation/provider wait.
Provider variability and ordering were not isolated; do not claim the new prompt
caused a general speedup.

All eight allowed generation attempts were consumed: **118.67 of 240 supplied
video seconds**, no retries, no query-embedding calls and no cache hits. The
configured tier was unpaid with $0 recorded estimate; the local ledger is not a
provider-wide billing guarantee. The call allowance is exhausted even though
video seconds remain. No more calls belong to this comparison.

The local full report is
`data/evaluation/gemini-fresh/continuation-comparison-v1.json`; its SHA-256 is
`539e269f02df84026e87eca0c7edc79567a29187f3e6eeb902eee2a2e30c0898`.
The committed [compact evidence](evidence/continuation-v1.json) preserves runtime
source hashes, model, contracts, exact ranges, usage and limitations. Additional
safe contradiction snapshots added after this run cannot reconstruct the missing
badminton response. No silent rerun was made to manufacture that evidence.

## Actual Storyroom editing and handoff

Verified workspace:

- Browser: `http://127.0.0.1:15176/`; API: `http://127.0.0.1:18767/`.
- Project: **Gemini fresh validation v1**, ID
  `811ae3bc316b4cbcbe02020737df236e`.
- Database: `data/evaluation/gemini-fresh/session/storyroom.sqlite`.

The real UI demonstration used the **prior legitimate cached hand-sign result**
for f07, not transplanted or re-keyed outputs from this comparison. This is
important: it proves selection plumbing with real footage, not that the new
continuation model suddenly passed the failed cases.

The complete hand-sign activity is 79 frames (2.633s). The editor reviewed that
activity, selected its full range **0–79**, then made a second exact selection
**1–78**. Both saved into **Activity review checkpoint** and survived reopening.
The earlier cooking **10–610**, push-up **636–708** and football **315–900** cuts
remained unchanged. Full-source viewing remained viewing only.

The five-cut render `a42e47318e094e3f98713f08b74333df.mp4` has **1,413 video
frames at 30fps, or 47.1 seconds**; FFprobe reports 47.1s audio too. The exported
board `28120990d67946a580a920d0d9941a88.json` contains those exact source ranges.
Media, database, renders and screenshots stay ignored/local.

### Actual Resolve check

DaVinci Resolve **21.1.2** imported the FCP7 XML into the separate saved project
**Storyroom activity review 2026-10-27**. Initial import reported four missing
media items. Native **Import Media Folder** granted the macOS sandbox access to
the session's media directory; importing the XML again resolved those references.

The Edit Index confirmed all five source ranges:
**10–610, 636–708, 315–900, 0–79, 1–78**. The timeline showed five video cuts,
four audio clips (cooking is silent), and duration **00:00:47:03** at 30fps. The
last adjusted hand-sign cut played to the timeline end. No claim is made that
Storybin names survived as useful Resolve labels: the visible clips were named
`edit.mp4`.

Local screenshots:

- `data/evaluation/gemini-fresh/evidence/activity-review-frames.png`
- `data/evaluation/gemini-fresh/evidence/activity-review-assembly.png`
- `data/evaluation/gemini-fresh/evidence/resolve-activity-review.png`

## Reproduce the editor workflow without new model calls

1. Open the workspace above and select **Gemini fresh validation v1**. Do not
   substitute an isolated browser-test database or the old four-clip project.
2. Use Visual AI with the previously cached query:
   **I need 20 seconds of a person demonstrating a hand sign indoors.**
   If the UI proposes a new uncached inspection, stop; this comparison's call
   allowance is exhausted.
3. Open the result's review. Confirm **Complete**, established activity **0–79**
   frames, the suggested cut, and your independently selected cut. Complete means
   inspected available activity extent, not a promise of perfect choreography.
4. Play **Review activity**, then **View full source video**. Return to the cut;
   viewing must not change its selected frames. Select **Select full activity**.
5. Check start **0**, exclusive end **79**, and duration **79 frames**. Adjust
   numeric controls to **1–78** and check duration **77 frames**. One arrow step
   changes one frame; at 30fps that is one-thirtieth of a second.
6. Choose the intended Storybin and confirm **Add selected cut**. Opening review
   or dragging a result must not create a saved placement before confirmation.
   Reload and inspect the saved exact boundaries.
7. Play the assembly, render and export. Adding another placement changes the
   expected total: compute it from saved exclusive-end minus start frames, not
   from a rounded seconds label. The existing five-cut checkpoint totals 1,413.

The cached shortfall message says 2.63 seconds were found, not that a 20-second
cut was produced. Changing the editor's selection must update its selected
duration without rewriting the matching activity. Partially inspected results
must say **Still checking** only while a job runs, or **Inspection incomplete /
stopped** otherwise; they must not claim a confirmed shortfall.

## Remaining gate and next gap

The editor-selection, exact persistence, render and actual Resolve handoff have
real product evidence. Automated checks separately cover incomplete/failed states,
exact 600-frame requests, full-activity selection, keyboard/numeric controls,
destination-preserving drag review and updates that preserve manual choices.
Their coordinator-reported final test/CI results belong in STATUS, not inferred
from the live model report.

**Keep this ticket open.** Badminton still fails continuation validation; the
single-move endpoint is still outside the frozen tolerance. Preserve these
failures and diagnose the next boundary contradiction with the newly bounded safe
diagnostics before another explicitly bounded experiment. Do not loosen the
answer key or acceptance rules to improve the score, spend additional calls from
this exhausted allowance, or start S2 as though the dependency were closed.
