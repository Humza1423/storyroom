# Diverse held-out visual-search pilot

Updated: 2026-10-24. This is a small engineering evaluation, not a production
accuracy claim.

## Manual Storyroom workflow smoke test (2026-10-24)

I used the isolated Storyroom browser app at `http://127.0.0.1:15174/` rather
than relying only on the evaluation script. I selected Visual AI, entered
ordinary conversational prompts, opened the returned clips in the player, and
added selected cuts to a test Storybin. The media names remained opaque (`h01`
through `h12`). These are examples from a small hands-on smoke test, not the
40-query answer-key benchmark and not a broad accuracy score.

| User-style search | What Storyroom returned | What I saw when played |
|---|---|---|
| “I need the bit where the boxer is moving around and practicing punches for a training montage.” | h01, 6.0–8.0 s first; another h01 range followed | Boxer visibly shadowboxing/practicing punches; added the 2-second cut to the test Storybin |
| “I need an insert showing hands feeding fabric through a sewing machine—anything like that here?” | h11, 12.0–16.2 s | Hands guiding fabric through the sewing machine |
| “Can you find the cat rolling around and playing on the floor? I want a quick animal cutaway.” | h09, 3.0–8.3 s and 0.0–0.8 s | Cat visibly rolling/playing; the 0.8-second fragment is too short to be a useful standalone shot |
| “I need a soccer player striking the ball toward goal for this montage—do we have that shot?” | No result in the first ten candidates checked (first page plus “Check more moments”) | No false match was shown in those ten candidates; later pages were not exhausted, so this is not a library-wide rejection claim |
| “I need an indoor wheelchair basketball shot where the play is moving toward the basket—can you find that?” | h05, 10.0–14.4 s | Wheelchair basketball action near the basket |
| “Can you find the astronauts exercising on the machine inside the space station? I need a shot that clearly feels like space.” | h08, 5.0–10.6 s and 0.0–5.0 s | Astronaut exercising on the ARED machine inside the station |
| “Do we have a close-up of an artist putting bright paint on a canvas at an outdoor stall? I need an art-process cutaway.” | h10, 0.0–4.8 s | Painter visibly working at the canvas |
| “Do we have a shot where people are pulling against each other? I want to show teamwork and effort.” | h04, 16.8–20.0 s and 12.0–15.6 s | Both results appear to be fragments of the same tug-of-war event |
| “Does this project have a shot of someone swimming in open water? I need a training-montage moment.” | h03, 1.0–3.0 s and 12.4–15.8 s | The first result visibly shows a swimmer; the later range may be another occurrence |
| “I need a dog running through a park—do we have anything like that in this footage?” | No result among the first five verified candidates | No match was shown on the initial results page; deeper candidates were not checked |
| “Where does the animated rabbit notice or react to the purple butterfly? I need a quick reaction shot.” | h12, 6.0–7.4 s | Played in Storyroom; the rabbit visibly reacts to the butterfly |

Nine positive prompts produced a visibly relevant first result across boxing,
tug of war, open-water swimming, sewing, cat footage, wheelchair basketball,
astronaut exercise, painting, and the rabbit/butterfly moment. The soccer
prompt produced no false match among the ten candidates checked; the absent-dog prompt returned
no match among its first five verified candidates. This is a small user-flow
smoke test, not an overall accuracy score or reliable negative-rejection
claim. The cat search returned a 0.8-second fragment; tug-of-war also surfaced
two fragments of one apparent
continuous event. Swimming returned a second range much later in the clip.
Duplicate-event grouping and useful shot-length behavior need a focused
quality/UX ticket; blindly merging all hits from one source would also risk
combining genuinely repeated actions.

The same three selected clips were played through the Storyroom assembly. The
player initially skipped or stopped around a middle clip because a late media
event from the previous video could advance the newly selected range. The
playback event guard added in this checkpoint was then verified in the real
app: all three placements advanced in order (boxing → sewing → astronaut),
and the expanded browser test now checks that the third clip is reached. I
also played the returned rabbit/butterfly range (6.0–7.4 s) in the live app;
it visibly shows the animated rabbit reacting to the butterfly. No media was
modified. The app-side development-budget meter changed during the search and
preview flow; it must not be treated as Google's billing record. No paid-tier
fallback was used.

At the 900-pixel browser viewport used for this session, the search column was
too narrow. Its compact-desktop/tablet grid now gives it a 270-pixel minimum
instead of 240 pixels; the phone layout still stacks, and the browser test
checks both the 900-pixel width and phone overflow. Result cards now use seconds
like the player rather than frame-style timecode; the browser test checks this.
The search copy still wraps in this narrow window. Treat remaining layout limits
as usability follow-up, not search-quality failures.

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

## Results

The full 40-query benchmark completed using the configured unpaid Gemini
services, with no paid fallback. It contains 30 positive/paraphrase searches
and 10 hard-negative searches. Results:

| Measure | Result | Meaning |
|---|---:|---|
| Relevant source somewhere in top five | 29/30 (96.7%) | Gemini usually found the right file among candidates |
| Relevant moment somewhere in top five | 25/30 (83.3%) | Some candidate lists found the file but missed the labeled event/range |
| Relevant first result | 24/30 (80.0%) | The best-ranked result was relevant in four out of five positive searches |
| First-result precision when a result was returned | 24/29 (82.8%) | One of 29 returned first results was not relevant |
| False results for the 10 hard negatives | 0/10 | Promising, but too small a negative set to establish reliable rejection |
| Median maximum boundary error | 3.23 s across 11 labeled boundaries | Worse than the one-second pilot goal |

By category, top-five relevant-moment rates were sports 94.7%, craft 83.3%,
animals 66.7%, and animation 0/2. The category sample sizes are small. Search
failures were classified as two shortlist misses, one temporal-candidate miss,
and two verifier rejections; 25 positive/paraphrase queries succeeded, while
the 10 negative prompts were correctly rejected by the answer key.

### Slowness and API use

Cold live searches had p50 latency **5.33 s** and p95 **7.03 s**. Replaying the
same cached searches had p50 **41.2 ms** and p95 **44.8 ms**, with **zero new
Gemini requests**. The cold delay is dominated by external model/network
round-trips: one text-vector request must finish before Storyroom can choose
candidate videos, then one batched verifier request checks the shortlist.
Local exact cosine search is not the measured bottleneck. The current cache
already makes repeated searches fast. Removing a model stage or shrinking the
candidate set might reduce cold latency but could reduce quality; this run does
not justify that tradeoff, so no speculative search change was made.

The full run made 33 query-embedding and 34 verifier request attempts (67
total); 40 verifier batches were invoked. Cache hits reduced repeat work. These
are application-observed counts, not a Google billing statement. Google free
quotas and service availability still apply.

### Answer-key issues discovered

Some misses cannot safely be treated as model failures without fixing the
labels:

- The obstacle-course label for “getting over a raised beam” spans 14–20 s,
  but live playback showed a relevant crawl-over-beam moment around 8.2–9.6 s.
  The expected interval is wrong or too narrow in the wrong place.
- The cat query expects “on a blanket,” but the footage shows a cat on a hard
  floor. The verifier's rejection is appropriate; this is a bad positive label.
- Sewing labels cover a long continuous 5–20 s action, while Storyroom returns
  smaller neighboring fragments. The benchmark can penalize useful fragments
  even when they show sewing.
- The animated-rabbit labels cover most of the 13-second clip, while playback
  confirms a specific 6.0–7.4 s reaction shot. Full-clip labels do not measure
  moment localization consistently.

Therefore the figures above are the raw answer-key score, not a calibrated
claim about product accuracy. In particular, do not tune thresholds to these
labels yet. The immediate next work is a short audit/correction of these
specific labels, then one rerun; do not add models or redesign retrieval first.

**Conclusion:** indexing and end-to-end visual search work on the 12 clips,
but Storyroom is not production-ready. It finds the correct source reliably,
yet sometimes ranks a weak moment first, returns fragments of one event, or
cuts the moment inaccurately. Search latency is mostly API round-trip time;
repeat-query caching already fixes the avoidable repeated-query delay. Keep
exact vector search. The next quality task is event/result usefulness plus
answer-key cleanup, not ANN or another model.

## Reproduction

The local media, answer key, and isolated database are intentionally ignored by
Git. With those files present and the local unpaid Gemini key configured, rerun
the test with:

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
