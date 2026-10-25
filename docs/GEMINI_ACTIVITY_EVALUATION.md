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

## Next bounded fix

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
