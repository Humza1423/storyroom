# Diverse held-out visual-search pilot

Updated: 2026-10-22. This is a partial engineering evaluation, not a production
accuracy claim.

## What was tested

Storyroom indexed 12 opaque-named H.264 proxy inputs in a separate local
project: eight sports/training clips plus cat, painting, sewing, and animation
clips. The sources span four collections: DVIDS, Wikimedia Commons, NASA, and
Blender. All 12 import/analysis jobs completed; the final project contains 161
visual ranges. Originals and converted files are ignored local data, not Git
assets. Per-file source URLs, authors, rights notes, hashes, media properties,
and conversions are in the ignored
`data/evaluation/visual-search/heldout-v1/provenance.json`.

The 40-query answer key contains 20 positives with reviewed ranges, 10
paraphrases, and 10 hard negatives. Every query is marked `test`; filenames
shown to Storyroom are `h01.mp4` through `h12.mp4`, not the source titles. The
search call went through the real visual-search endpoint: Gemini Embedding 2
query vectors, local exact-cosine search and event grouping, then the configured
Gemini video verifier. No training or paid-tier call was used.

## Sources

| Opaque file | Source and title | Creator | Rights noted in local provenance |
|---|---|---|---|
| h01 | [DVIDS: SPC Myron Harris trains boxing for upcoming bouts](https://www.dvidshub.net/video/1015471/spc-myron-harris-trains-boxing-upcoming-bouts) | Sgt. Myenn LaMotta | Public domain on item page; DVIDS notice and third-party rights still apply |
| h02 | [DVIDS: 18th Airborne Corps Best Squad Competition 2026 Obstacle Course](https://www.dvidshub.net/video/1003287/18th-airborne-corps-best-squad-competition-2026-obstacle-course) | Sgt. 1st Class Travis Fontane; Spc. Isaiah Mount | Public domain on item page; DVIDS notice and third-party rights still apply |
| h03 | [DVIDS: 22nd MEU Open Water Swim Training](https://www.dvidshub.net/video/1002919/22nd-meu-soc-india-co-open-water-swim-training) | Sgt. Maurion Moore | Public domain on item page; DVIDS notice and third-party rights still apply |
| h04 | [DVIDS: U.S. Navy and Latvian Sailors Compete in Tug of War](https://www.dvidshub.net/video/966097/us-navy-and-latvian-sailors-compete-tug-war) | PO1 Melissa Russell | Public domain on item page; DVIDS notice and third-party rights still apply |
| h05 | [Wikimedia: Wheelchair basketball](https://commons.wikimedia.org/wiki/File:Wheelchair_basketball.webm) | Splash TV | CC BY-SA 4.0 |
| h06 | [Wikimedia: Squat exercise demonstration](https://commons.wikimedia.org/wiki/File:Squat_-_exercise_demonstration_video.webm) | FitnessScape | CC BY 3.0 |
| h07 | [Wikimedia: Kenyan skateboarding](https://commons.wikimedia.org/wiki/File:Kenyan_skateboarding.webm) | Drewperez1 | CC BY-SA 4.0 |
| h08 | [NASA: Astronauts exercising on ARED](https://www.nasa.gov/missions/station/iss-research/astronaut-exercise/) | NASA; Bob Hines and Kjell Lindgren | NASA media guidelines; credit NASA, avoid implying endorsement, check third-party rights |
| h09 | [Wikimedia: Cat Plays](https://commons.wikimedia.org/wiki/File:Cat_Plays.webm) | Riverarvi | CC BY-SA 4.0 |
| h10 | [Wikimedia: Painting process](https://commons.wikimedia.org/wiki/File:Painting_process.webm) | Alvin Ategyeka | CC BY-SA 4.0 |
| h11 | [Wikimedia: Sewing with a 1894 Singer machine](https://commons.wikimedia.org/wiki/File:Sewing_with_a_1894_Singer_sewing_machine.webm) | Pannini | CC BY-SA 4.0 |
| h12 | [Blender: Big Buck Bunny](https://video.blender.org/videos/watch/bf1f3fb5-b119-4f9f-9930-8e20e892b898) | Blender Foundation | CC BY 3.0; excerpt credit: © 2008 Blender Foundation / www.bigbuckbunny.org |

## Results and blocker

The configured unpaid verifier, `gemini-3.5-flash-lite`, returned a successful
response for the first six positive queries before query p07 failed twice with
HTTP 503 `UNAVAILABLE` (“currently experiencing high demand”). The evaluation
runner stopped rather than treating a service outage as a search miss. No
results for the remaining 34 queries are claimed.

The six completed queries were replayed from the isolated project's caches
(zero Gemini requests during replay): **6/6** had the relevant source in the
top five and a relevant first result. These are six positives only; there were
no negative prompts in this partial sample, so false-positive rate is unknown.
Two queries had reviewed event boundaries. Median maximum boundary error was
**2.28 seconds** (1.20 s for low crawling; 3.37 s for climbing over a beam),
which misses the pilot's one-second timing goal. The correct source can rank
first while its returned time is still too early or too short.

One isolated request using `gemini-3.8-flash` succeeded, but the next request
also returned HTTP 503 after the bounded retry. This indicates temporary
provider availability across two supported model choices, not evidence that
changing model alone fixes reliability. Search configuration was not changed;
there was no paid fallback. A cache-only replay's local p50/p95 were 44.7/46.4
ms, but those numbers exclude Gemini and are **not live search latency**.

**Conclusion:** indexing works on this diverse set, and the initial six
positive searches found the right source. The full 40-query quality test is
incomplete because Gemini's verifier was unavailable. The small boundary
sample also shows timing still needs work. Do not call search production-ready
or tune rejection thresholds from these results.

## Reproduction

The local media, answer key, and isolated database are intentionally ignored by
Git. With those files reconstructed and the local unpaid Gemini key configured,
resume the test with:

```sh
STORYROOM_DATA="$PWD/data/evaluation/visual-search/heldout-v1/session" \
STORYROOM_GEMINI_TIER=unpaid \
STORYROOM_GEMINI_UNPAID_TERMS_ACKNOWLEDGED=true \
.venv/bin/python scripts/evaluate_visual_search.py \
  data/evaluation/visual-search/heldout-v1/answer-key.json \
  --profile heldout \
  --data-dir data/evaluation/visual-search/heldout-v1/session \
  --allow-free-gemini
```

The test runner resumes cached vectors/verdicts, but new verifier calls remain
subject to Google's free-tier quotas and availability. It never enables paid
service automatically.
