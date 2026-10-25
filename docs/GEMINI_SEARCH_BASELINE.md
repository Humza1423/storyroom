# Gemini search: corrected development baseline

Reviewed 2026-10-25 against code `dcce1a5`, Gemini Embedding 2 and the configured
`gemini-3.5-flash-lite` verifier. Search used exact cosine retrieval, motion-based
event grouping and the normal five-candidate verifier path. Optional localization
was off. No search policy, model, threshold or source media was changed.

## What was reviewed

All twelve input contact sheets were independently inspected: boxing, obstacle
course, swimming, tug of war, wheelchair basketball, squats, skateboarding,
astronaut exercise, cat, painting, sewing and animation. Additional sheets used
2 fps for the obstacle/rabbit clips and 4 fps for squat repetitions; individual
8.5-second obstacle and 7.8-second rabbit frames were inspected at full resolution.
These are approximate human labels (roughly ±0.5 seconds), not frame-perfect
annotations. Continuous-shot usefulness still requires playback review.

The original answer key and historical report remain unchanged. The ignored
`data/evaluation/visual-search/heldout-v1/review-answer-key.py` generates
`answer-key-reviewed-v2.json`, retaining the original SHA-256, original changed
rows and reasons. All forty queries are now development evidence. Their exact
wording is preserved, so existing model responses can be rescored without calls.

Label corrections:

- p02/v02 ask for crawling **under/beneath** an obstacle. The soldier crawls over
  the logs. These are negatives; rewriting them into easier positives would hide
  the semantic confusion.
- p03/v03's over-log interval is approximately 7.5–13 seconds; the former
  14–20-second label shows walking/balancing on a beam.
- v09 asks for a blanket, but the cat is on a hard floor: another negative.
- p16/p17/p20/v10 describe continuous sewing. A short relevant shot is acceptable;
  coverage of the entire fifteen-second label is unnecessary.
- Rabbit shots occur around 4–5.9 and 7.5–8.9 seconds. The reaction label uses the
  latter shot. The historically reported 6–7.4-second rabbit match shows the
  squirrel/fox characters and is a real wrong moment.
- p08/p09 label individual squat repetitions/descent phases instead of spanning
  two repetitions; v07's broad plural squats query is continuous activity.

The reviewed key includes unexecuted broad/specific/duration development examples.
They are not included in the forty-query score.

## Actual results

| Measure | Original key, reproduced | Reviewed key, same returned results |
|---|---:|---:|
| Positive / negative queries | 30 / 10 | 27 / 13 |
| Correct source in first five | 29/30 | 27/27 |
| Relevant moment in first five | 25/30 | 24/27 (88.9%) |
| Relevant first result among positives | 24/30 | 24/27 (88.9%) |
| Precision among queries returning results | 24/29 (82.8%) | 24/29 (82.8%) |
| Negative queries returning a result | 0/10 | 2/13 (15.4%) |
| Median maximum boundary error, successful discrete labels only | 3.233 s / 11 labels | 1.067 s / 5 labels |

**24/29 means five incorrect returned first results**, not one. Rejection and
first-result accuracy use different denominators. Boundary error is conditional
on successful matches and excludes the three missed positive moments; it must
not be presented as overall localization quality. Corrections change the score,
not the software. This is no longer an untouched test set.

Reviewed positive top-five moment recall: sports 16/17, craft 6/6, animals 2/2,
animation 0/2. These small category counts are diagnostic only.

## Earliest failures and the evidence

| Query IDs | Observed failure | Earliest confirmed cause |
|---|---|---|
| p02, v02 | 8.2–13s accepted as crawling under logs | Verifier accepts wrong spatial relation; frame at 8.5s shows body on top |
| p03 | 13–16.6s returned; actual over-log range omitted | Grouping retains only 11.6–13s of relevant event; two higher-ranked same-source events exhaust initial source allocation |
| p18 | 6–7.4s returned as rabbit watching | Raw 4.2–6s and 7.4–8.8s exist; grouping substitutes other intervals; verifier also accepts wrong character |
| p19 | 2.6–4.2s and 6–7.4s returned as rabbit reaction | Raw 7.4–8.8s exists, grouping changes it to 8.8–11.6s; initial verifier accepts wrong-character intervals |
| v09, n01–n10 | No result | Correct rejection under reviewed key |
| All other positive IDs | Relevant moment returned | Coarse moment criterion passes; does not establish complete activities or polished cuts |

The evaluator now records all raw segments, grouped events, the actual shortlist,
verdict evidence and returned ranges. It distinguishes loss during grouping from
absence in raw retrieval. This supports preserving candidate anchors and giving
Gemini contextual video; it does not justify ANN or switching embedding models.

**Not yet tested:** a live controlled comparison of reviewed context versus short
candidate input. All responses above were cached before this work. Contextual
verification remains a hypothesis until that comparison runs.

## Calls and performance

The original-key replay exercised the actual endpoint against the isolated
database, with forty cached query vectors and two hundred cached candidate
verdicts: **zero embedding requests and zero verifier requests**. Cache-only
guards reject any missing entry before a network request. The reviewed-key
rescore used the saved result/trace JSON and made no endpoint or provider calls.

Cached endpoint p50 was 88.5 ms and p95 107.5 ms in this run. These timings include
hashing/profiles and local search; they are not comparable hardware-normalized
speed regressions against the earlier 41ms run. Historical cold p50/p95 of
5.33/7.03 seconds are quoted from `HELDOUT_EVALUATION.md`, not remeasured here.
Current provider input seconds and retries were **zero**. Historical uploaded
seconds and internal retry counts are unavailable from these cached verdicts;
do not invent them. New instrumentation records candidate seconds and uncached
candidate seconds separately; a batch invocation is not necessarily a request.

## Reproduce and open the correct workspace

From the repository root, regenerate the reviewed labels, then rescore the saved
baseline:

```sh
.venv/bin/python data/evaluation/visual-search/heldout-v1/review-answer-key.py
.venv/bin/python scripts/evaluate_visual_search.py \
  data/evaluation/visual-search/heldout-v1/answer-key-reviewed-v2.json \
  --profile reviewed-development \
  --data-dir data/evaluation/visual-search/heldout-v1/session \
  --replay-report data/evaluation/visual-search/heldout-v1/baseline-original-cached.json \
  --output data/evaluation/visual-search/heldout-v1/baseline-reviewed-v2.json
```

To open the evaluation projects, stop the previously managed Storyroom stack and
launch with this explicit data directory:

```sh
STORYROOM_DATA="$PWD/data/evaluation/visual-search/heldout-v1/session" \
STORYROOM_UI_PORT=15176 STORYROOM_API_PORT=18767 \
.venv/bin/python scripts/dev.py
```

Select **Held-out diverse visual search v1** (12 clips); the master-derived copy
is a separate project in the same evaluation database. A port does not identify
a database. The default `data` database contains the older four-clip project.

Verification: `pytest tests/test_visual_search_evaluation.py -q` passed **17 tests**,
including raw-versus-grouped loss, explicit metric denominators and cache guards.
