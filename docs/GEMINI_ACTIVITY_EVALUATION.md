# Gemini activity-search checkpoint — 2026-10-25

## Decision

Keep **Activity search (preview)** opt-in. The new path is implemented and the
editor handoff works, but the frozen live test **misses the release targets**.
Do not promote it to the default or describe all three tickets as complete.
Continue with one narrow duration/context fix, not another model integration.

## What changed

Embedding 2 still finds candidate locations using exact cosine search. In the
experimental path, one Gemini request inspects up to five short videos for both
visible relevance and timestamps. It distinguishes broad activities, discrete
moves and explicit durations. Source names/captions are not semantic evidence.

An initial inspection is at most eight seconds per location. If an action reaches
an interior crop edge, the range stays **partial**. The persistent worker can
inspect adjacent video in 30-second chunks with four seconds of overlap, saving
completed work. Only grounded overlapping activity can extend a range; unrelated
actions and uninspected gaps are not joined. Invalid timestamps remain rejected.

The card distinguishes its suggested cut from the identified activity. The player
can review the cut, activity or full source. Quick add/drag use the suggested cut;
adjusted add uses chosen integer frames. Worker updates replace proposals, never
accepted Storybin selections. A real-use duplicate-card bug was fixed: completed
job snapshots must replace the original proposal batch even when a proposal lacks
the job marker. A browser regression covers this case and stale-query isolation.

## Frozen experiment

- Product code: `2ee6d641887a3ff3cc338cbde263b237bdc473d5`. Later `b94dcd1`
  fixes frontend replacement and portable test imports, without changing the
  evaluated search algorithm/model/prompt.
- Models: `gemini-embedding-2`, `gemini-3.5-flash-lite`; configured unpaid tier.
  No billing change or paid fallback. Application counters cannot verify Google's
  billing configuration or SDK-internal HTTP retries.
- Eight new licensed source items, three collections: Commons, DVIDS, NASA.
  [Sources, credits and preparation](GEMINI_VALIDATION_SOURCES.md).
- Local database: `data/evaluation/gemini-fresh/session/storyroom.sqlite`;
  project **Gemini fresh validation v1**, eight clips, 135 indexed segments.
- 24 frozen queries: 16 positives and eight hard negatives, written after viewing
  contact sheets and before any search. Opaque f01–f08 filenames.
- Frozen key SHA-256:
  `28d46f70d6c21d56aaa95d469616136f8c2d883c9e05aeb1d1b78f65d4ad10b3`.
  The [unaltered key](../tests/fixtures/gemini-fresh-answer-key-v1.json) is committed;
  the original labels and results were not retuned after this run.
- [Compact per-query evidence](evidence/gemini-activity-v1.json) includes actual
  returned frames, inspected activity bounds, failures, latency and API counters.
  Media, database, credentials and full local manifests remain ignored.

## Results — not a production-accuracy claim

| Measure | Observed | Gate |
|---|---:|---|
| Positive top-five labeled moment recall | 12/16 (75%) | Fail: target ≥90% |
| Returned-first labeled moment precision | 12/13 (92.3%) | Fail: target ≥95% |
| Fixed absent-action false returns | 0/8 | Pass for these eight queries only |
| Relevant cut with explicitly requested duration | 1/5 | Inadequate |
| Median discrete boundary error | 0.70s, **one matched label** | Too little evidence to generalize |
| Searches with incomplete/failed continuation | 4/24 | Reliability gap |

The scoring rule for continuous presence requires at least 90% of the suggested
cut inside a labeled relevant interval; discrete moves require temporal IoU ≥0.5.
These metrics do not establish that every move has a comfortable editorial
lead-in. The push-up passes overlap scoring but begins about 0.7s after its reviewed
start. The football first result is outside the frozen labeled intervals; another
returned range overlaps a labeled kick but extends too far. Other unlabeled
occurrences may exist; do not silently rewrite the key to improve the score.

| Query/example | Actual returned range | Interpretation |
|---|---|---|
| Outdoor football practice | f01 15.23–17.90s; 19.70–26.03s | Relevant source; second activity remains partial |
| Blue player: complete kick | f01 21.40–24.60s; 9.80–13.60s | Misses frozen complete-move labels; needs playback adjudication, not a claimed pass |
| 20 seconds of football | f01 16.23–19.70s | Honest shortfall/partial, not duration fulfillment |
| Indoor badminton doubles | f02 15.30–20.30s | Relevant short cut; activity only inspected through 21.30s |
| 20 seconds of badminton | None | False negative |
| Push-up demonstration | f03 22.70–27.70s | Relevant cut; continuation failed |
| One complete push-up | f03 21.20–23.60s | Labeled overlap passes; visible lead-in still too tight |
| Standing fitness instructors | f03 5.70–8.03s | Relevant instructional shot |
| Horses moving in pasture | f05 13.50–19.70s | Activity 0–30s established |
| 20-second horses cutaway | None | False negative despite the broad-query success |
| Noodles boiling | f06 15.70–20.33s | Activity 0–20.33s established |
| 20 seconds of pasta cooking | f06 0.33–20.33s | Exactly 600 frames, relevant |
| Hand sign / hand beside face | f07 0–2.63s | Both queries find the short gesture |
| Rotating Earth | f08 19.30–24.30s | Activity 0–30s established |
| 20 seconds of Earth | None | False negative |

All eight negatives returned no candidate: volleyball play despite a tournament
slate; stirring despite boiling noodles; heavy-bag kicking; bicep curls; dog chasing
a ball; astronaut treadmill; basketball scoring; knitting. This only checks the
first five candidate locations per query, not an exhaustive library rejection.

Cache-only tracing (network disabled) confirmed the earliest failing stage for
the three empty duration queries: the correct source occupies the first two
retrieved anchors, but Gemini's cached duration verdict is `no_match` on both.
Badminton received 0–6.5s and 2.6–10.6s contexts; horses 0.7–7.5s and 2.5–10.3s;
Earth 19.3–26.5s and 11.5–18.5s. Thus those misses occur at short-context semantic
inspection, **not missing raw retrieval or frame conversion**. The saved verdicts
do not explain their reasoning, so duration/context interpretation is the next
controlled hypothesis, not a proven account of the model's internal reasoning.

## Requests and speed

Indexing made 37 SDK embedding calls. The frozen search run made 24 text-embedding
calls and 43 video-inspection SDK calls, including continuation, supplying 1,065.8
video seconds across repeated candidate contexts. Returned usage: 228,751 input
tokens, 12,359 output tokens. Application retry counters were zero; SDK-internal
transport retries are not exposed. Configured free API price was $0, not a billing
guarantee. The existing app budget meter records conservative rate-based usage and
must not be interpreted as an actual Google charge.

Initial-search median was 8.61s; median including continuation was 10.94s.
See per-query evidence rather than subtracting those medians. A cached push-up
replay took 58ms HTTP total, five inspection-cache
hits and zero inspection requests. This is one cached example, not a cached p95.
Long-activity inspection adds real work; no claim of unchanged cold performance.

The corrected older [development baseline](GEMINI_SEARCH_BASELINE.md) used different
footage/queries. Its 24/27 moment recall and 24/29 precision are **not** a controlled
before/after comparison with this fresh sample. Development trials also found
under/over-log semantic confusion and a 3.8 Flash deadline/availability problem.
No stronger-model superiority is claimed.

## Actual app and Resolve evidence

In the existing 12-clip development library, searched
`a boxer shadowboxing and practicing punches`. After continuation it produced one
activity 0–20s with a suggested cut 3.5–10.7s. Watched the suggested cut, expanded
to activity and full source, adjusted to frames **106–300**, and added it to a new
**Activity search demo** Storybin without changing the earlier four selections.
Reload preserved those exact frames. Assembly reached clip 5 of 5.

Rendered review MP4 `172a510e…` measured **20.233333s**. Export `11d8e498…` imported
into the actual Resolve 21 application in **Storyroom activity search 2026-10-25**.
Native folder import first granted access to the isolated media directory after
Resolve reported four missing sources. Reimport then resolved the footage.
The Edit Index showed all five video/audio source ranges:
`6:00–7:29`, `12:00–16:06`, `5:00–10:18`, `1:00–3:00`, `3:16–10:00`
(seconds:frames at 30fps); total **00:00:20:07** matches 607 selected frames.
Screenshot: ignored `data/evaluation/gemini-fresh/evidence/resolve-five-cuts.png`.
This confirms the changed selection handoff, not a fresh exhaustive codec/audio
suite or every search result's semantic correctness. Resolve displayed source
filenames; section-name presentation was not re-established in this import.

Also opened the new eight-clip library in the real app and played the push-up
query's 21.2–23.6s result. It shows a push-up, but the start is already descending:
the complete-move UX is not yet good enough to claim precise localization.
In that fresh library, Quick add saved the cooking cut at frames 10–610 and the
push-up at 636–708 in **Fresh footage handoff**. Its rendered MP4 `a4e62ce3…`
contains exactly 672 video frames / 22.4s; audio also lasts 22.4s and the first
19.9s cooking portion is silent (16-bit volume floor −91dB). This fresh two-cut
export was generated, but the actual Resolve import above uses the separate
five-cut development assembly; do not conflate those checks.

## Reproduce

```sh
.venv/bin/python scripts/prepare_gemini_validation.py
.venv/bin/python scripts/run_gemini_validation.py
.venv/bin/python scripts/evaluate_activity_search.py --allow-free-gemini
```

Indexing/search commands send these rights-checked proxies to the configured
unpaid Gemini project; do not run them without suitable credentials and quota.
Stop the interactive worker for this data directory while running the isolated
evaluation. Conversion output hashes can differ across FFmpeg builds; review that
change explicitly, rather than overwriting the frozen historical key.
Existing reports refuse to mix code/model/key/database identities; use `--output`
for a new report. Do not repeatedly rerun an unchanged failing configuration.

For the prepared local demo:

```sh
STORYROOM_DATA="$PWD/data/evaluation/gemini-fresh/session" STORYROOM_UI_PORT=15176 STORYROOM_API_PORT=18767 .venv/bin/python scripts/dev.py
```

Open `http://127.0.0.1:15176/` → **Gemini fresh validation v1** → **Visual AI** →
check **Activity search (preview)**. Search the exact push-up query above, click
**Preview suggested cut**, then **Review activity** or **View full source video**.
Try `Give me 20 seconds of pasta cooking in boiling water.` for the successful
duration example and `I need a 20 second horses-in-a-field cutaway.` for a miss.
Use the in/out sliders and add to a Storybin; refresh and inspect the saved range.

## Historical next bounded fix (superseded by the follow-up below)

1. Separate **find this activity** from **choose its requested duration** in the
   existing combined request. An eight-second crop cannot prove absence of a
   20-second activity. Retrieve/verify the action first, retain duration as output
   policy, then expand a positive partial range. No extra classifier request.
2. Preserve the specific sanitized validation reason for failed continuation;
   current generic failure text prevents distinguishing invalid ranges from
   uncertain continuation without a new call. Keep invalid-timestamp rejection.
3. Use these now-development failures for a bounded comparison, then freeze a
   fresh small test. Do not lower acceptance thresholds, add Qwen/ANN, or call
   this production-ready. Discrete-move lead-in remains a separate acceptance gate.

## S1b/S1c follow-up — 2026-10-27

### What was changed and compared

S1a first preserved safe reasons without changing decisions. S1b (`2bd9876`)
separated action recognition from requested edit length in the combined response;
removed the local numeric regex override; and added honest UI duration/inspection
states without resetting chosen cuts. Same model, 3-fps crops, initial eight-second
limit, shortlist and exact retrieval. The historical key stayed byte-for-byte
unchanged. This is now development evidence, not a fresh held-out validation.

| Measure | Historical v1 | S1b full 24-query run |
|---|---:|---:|
| Positive top-five labeled moment recall | 12/16 | 7/16 |
| Returned-first labeled moment precision | 12/13 | 7/8 |
| Correct requested edit duration | 1/5 | 3/5 |
| False negative-query clips returned | 0/8 | 0 returned; only 6/8 verified |
| Video dispatches / supplied seconds | 43 / 1,065.8 | 39 / 979.63 |
| Initial / total median wait | 8.61 / 10.94s | 42.32 / 48.62s |

Nine queries encountered provider failures (p06, p08, p09, p11, p14, p15, p16,
n01, n03); three more had validation failures (p01, p04, p05). Provider failure
includes continuation failures retaining a result. HTTP 500/timeout are **not**
confirmed negative rejections. Fewer calls under failures is not an efficiency win.
Returned token usage was 164,055 input / 9,144 output; failed requests can lack
usage. Existing query embeddings were reused (zero new text-embedding calls).
The hard runner cap was 40 actual generation dispatches / 1,500 video seconds,
including retries, atomically reserved before dispatch. No paid fallback.
[Per-query v3 evidence](evidence/gemini-duration-v3.json).

Football, horses and cooking fulfilled 600-frame duration requests. Complete-kick
ranges remained 21.4–24.6s and 9.8–13.6s; push-up remained 21.2–23.6s, beginning
during descent. The single matched discrete label still yields a 0.70s median,
which cannot certify movement completeness. Do not claim these are solved.

S1b also exposed a concrete validation distinction: p01/p05 had valid local match
spans vetoed by inconsistent continuation flags, whereas p04 had out-of-crop
timestamps. S1c (`2b2e34f`) keeps only the former as explicitly partial evidence;
the latter remains invalid. Cache versions changed, old results remain readable.
The runner now fingerprints actual source files as well as HEAD before resuming.

### Bounded S1c follow-up and its limits

Selected p01 football, p05 20-second badminton and n04 absent curls before the
follow-up. Added one separately recorded shortfall probe, not another scored
benchmark query. Total six generation dispatches / 180.9 supplied seconds within
eight / 300 limits, including a single 503 retry. The three fixed searches used
cached query embeddings; the new manual probe used one text-embedding call.
[V4 ranges, diagnostics, contract and source fingerprints](evidence/gemini-boundary-v4.json).

- Football returned relevant **16.233–17.567s** and **21.033–22.033s** fragments.
  It still does not provide one useful broad activity card. Initial wait 12.67s.
- Badminton returned **0–6.5s** and **2.6–10.6s**, still partial, not 20 seconds.
  Initial wait 16.83s; 57.79s including failed continuation. The next inspection
  selected a later local **14.333–19.667s** interval in a 27.5s context rather than
  extending the original anchor. It was rejected; the original ranges survived.
- Absent bicep curls returned no match after all five candidate checks (10.03s).
- New initial provider replies contained **no boundary-conflict flags**. Therefore
  this live change cannot be attributed to the new conflict policy; provider output
  varied. Deterministic regressions prove the policy, not a live accuracy gain.
- `I need 20 seconds of a person demonstrating a hand sign indoors.` returned
  f07 **0–79 frames**, complete available extent, requested 600. It selected all
  **2.633s**, with friendly shortfall feedback; 8.69s HTTP wait, one video request.
  This establishes one shortfall example, not continuous-action generalization.

### Product playback, persistence, render and Resolve

In **Gemini fresh validation v1**, searched the cached football duration prompt,
watched its 10–30s selected cut reach 20.0/20, reviewed activity and full source,
then moved In from frame 300 to **315**, retaining Out **900**. Added to
**Duration checkpoint demo** and reloaded: those frames survived. The existing
**Fresh footage handoff** selections remained f06 **10–610**, f03 **636–708**.
An initial title click opened renaming rather than selecting the target bin and
the add did not persist. Actual reload caught it; separate title-select/pencil-edit
controls and a browser regression fixed the ambiguity. New add then persisted.

Played the shortfall clip to its 2.633s end and a retained badminton partial range.
Repeated stopped badminton search reused the terminal snapshot: usage rows stayed
at 150 and no new inspection job was queued. Explicit Activity-panel Retry is still
available. The message says the next inspection found a different moment, rather
than exposing “retrieved anchor” jargon. No claim of completed badminton extent.

Assembly reached **Clip 3 of 3**. UI render `93ecda73b9d943c898b841bc059fb191`
completed: 1280×720, 30 fps, **1,257 frames / 41.9s video and audio**. First 19.9s
cooking audio measured the −91dB silent floor. Export
`caaed1d4b64f4caa901a3ea5a09b7edb` then imported into actual **Resolve 21.1.2**,
project **Storyroom duration checkpoint 2026-10-27**. The native folder importer
granted access after the first attempt reported missing sources. Reimport succeeded.
The Edit Index showed exactly:

| Order | Source | In → exclusive Out (seconds:frames, 30 fps) | Duration |
|---|---|---|---|
| 1 | Cooking | 00:00:10 → 00:20:10 | 00:20:00 |
| 2 | Push-up | 00:21:06 → 00:23:18 | 00:02:12 |
| 3 | Football | 00:10:15 → 00:30:00 | 00:19:15 |

Timeline duration **00:00:41:27**; three video placements and two audio placements,
with no audio under silent cooking. Football played through the end. Visible source
labels are `edit.mp4`, not Storybin sections; do not claim Resolve-bin mapping.
Screenshot `data/evaluation/gemini-fresh/evidence/resolve-duration-v4.png` and
Storyroom shortfall/assembly screenshots remain local and ignored. Managed sources
and inputs for all eight clips match their registered SHA-256; SQLite quick check
passed, and recovery backups remain intact. This is selection-handoff evidence,
not a fresh comprehensive codec or audible-quality test.

Checks: **318 backend tests**, production build, **38 isolated browser tests** pass,
including retained media correctness. A timing-sensitive Pause click in a two-second
browser fixture was replaced by testing return-to-cut from either playing or ended
source state; playback-progress and paused-return assertions remain.

### Reproduce without new API calls

Use the prepared demo at `http://127.0.0.1:15176/`, **Gemini fresh validation v1**,
Visual AI → **Activity search (preview)**. Exact cached queries:

1. `I need 20 seconds of football practice on grass.` — preview the 20-second cut,
   Review activity, then View full source video. The saved adjusted selection is
   separately visible in **Duration checkpoint demo**.
2. `I need 20 seconds of a person demonstrating a hand sign indoors.` — preview
   all 2.63 seconds and read the informational shortfall.
3. `Give me 20 seconds of badminton court action.` — inspect the partial/stopped result. Do not
   choose Retry unless intending to make new provider calls.

Cache identity includes the complete query. Other wording can make new calls.
The exported XML and saved Resolve project above remain available locally.

Next: S2 labels/observed complete moves, then S3 continuity and duplicate activity
cards. Provider availability is a separate measured limitation. No more tuning this
same key, no Qwen/ANN integration, and no production-readiness claim.
