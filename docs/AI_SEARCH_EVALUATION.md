# Visual-search quality check

Updated: 2026-10-20. This page records engineering observations, **not** a
representative accuracy claim. The original four-clip exercise pilot and its
older results below are historical; the current evidence is in STATUS. Pexels
footage was not indexed.

## Current evaluation path

The live path embeds the text query once, ranks stored proxy-video embeddings
with exact cosine similarity, groups events, and sends at most five candidate
ranges to one Gemini video-verification request. Only `match` with visible
evidence is shown. Page 0 uses the original five-candidate ordering; each
explicit **Check more moments** page takes the next five unchecked ranked
events. More pages can cost more provider requests, but do not slow or charge
the initial search. The model cannot infer a complete action from a cut that
contains only part of the movement.

`scripts/evaluate_visual_search.py` now hooks the actual batch verifier and
refuses uncached cloud calls by default. It has strict `--profile pilot`
(16 videos, 60 reviewed queries: 36 positive, 12 paraphrase, 12 negative)
and `--profile full` (50 videos, 100 reviewed queries) shapes, plus a smaller
`--profile smoke` (16 videos, 20 queries: 12 positive, 8 negative) diagnostic.
Run it only
against a dedicated ignored evaluation database; `--allow-free-gemini`
explicitly permits missing unpaid-tier requests. The report separates
right-source retrieval from right-moment overlap and start/end error, and
records shortlist, verifier, cache, and latency evidence. An isolated dataset
and reviewed answer key are still required; neither strict benchmark has a score.

The local smoke answer key is
`data/evaluation/visual-search/pilot16/answer-key-smoke.json`. Its 20 queries
are all **development** queries, not a held-out quality estimate. In a
cache-only run, the verified path found the right source for 12/12 positives,
but a useful reviewed moment for only 9/12; all 8/8 absent-action prompts
returned no result. The embedding-only gate on the same set falsely returned
something for 3/8 absent-action prompts. Sports timing was the clearest leak:
only 1/4 sports positives yielded a useful moment. Those counts expose what to
fix; they do not establish general accuracy or live latency. To reproduce
without spending API quota, run:

```sh
.venv/bin/python scripts/evaluate_visual_search.py \
  data/evaluation/visual-search/pilot16/answer-key-smoke.json \
  --profile smoke \
  --data-dir data/evaluation/visual-search/pilot16/session
```

The next quality experiment should compare query-aware localization inside
bounded neighboring context with the current motion-only cuts, on reviewed
action boundaries. Keep source identity, frame mapping, and the five-candidate
verification limit fixed while comparing; do not ship a new cut policy from
three favorable examples. The local answer key and media are ignored, so a
fresh checkout must reconstruct the rights-checked dataset before this command
can run.

The first diverse pilot inputs are locally prepared under ignored
`data/evaluation/visual-search/diverse-expansion/` with source revisions,
licenses, hashes, conversions, and exclusions. Sixteen clips (these eight plus
eight previously licensed clips) are imported and indexed in the isolated
`data/evaluation/visual-search/pilot16/session/` project. The 253 video ranges
needed 67 batched embedding requests; batching did not change the vectors.
A 12-prompt smoke run found expected sources on completed requests but suffered
four initial Gemini HTTP 503 verifier failures. Subsequent free-tier retries
completed those prompts, including a correct rejection for punching a heavy
bag; one swing search took 63.5 seconds. This is neither a 60-query score nor
a reliability guarantee. Do not
copy source-page titles into search labels or treat them as visual ground truth;
review the actual frames and mark event boundaries independently. Split by
source/creator before tuning any policy, and keep an untouched held-out set.

The added Commons source pages are [soccer corner](https://commons.wikimedia.org/wiki/File:2018_FIFA_U-17_Women%27s_World_Cup_-_New_Zealand_vs_Canada_-_22.webm),
[track start](https://commons.wikimedia.org/wiki/File:VIDEO0036_01.webm),
[sleeping dog](https://commons.wikimedia.org/wiki/File:REM_-_Rapid_eye_movement_sleep_of_a_dog.webm),
[cat close-up](https://commons.wikimedia.org/wiki/File:2_year_old_Siamese_Tabby_Cat_1_2016-05-22.webm),
[strawberry growth](https://commons.wikimedia.org/wiki/File:Strawberry_growth_(Video).webm),
[metronome](https://commons.wikimedia.org/wiki/File:Metronome.webm),
[electric bike pump](https://commons.wikimedia.org/wiki/File:Lamicell_electric_air_pump_inflating_a_bicycle_tyre.webm),
and [washing dishes](https://commons.wikimedia.org/wiki/File:Washing_Dishes.webmhd.webm).
The ignored local provenance file records authors, revisions, individual
licenses, original URLs, hashes, and conversions. The existing exercise and
four-source Commons sets supply the other eight clips. No media is committed.

## Historical observations (superseded where they conflict with STATUS)

## Current search decision and blocker

The live search path now shortlists distinct moments with Gemini Embedding 2,
then checks up to ten short silent proxy ranges with a Gemini video verifier.
Only a `match` accompanied by visible evidence can appear as a result. The
previous fixed 0.62 cosine gate is retained in the evaluation runner as the
embedding-only baseline. The runner records raw ranks, verifier decisions,
accepted results, and separate baseline/verified metrics when reviewed query
labels and API quota are available.

The known one-asset failure was reproduced on a real indexed bicep-curl clip:
both `bicep curls` and `push-ups` returned ranges from that same clip under the
old ranking path. Deterministic tests now reject the wrong action, uncertain
verdicts, and missing evidence. A live verifier comparison cannot yet run:
Google reports zero GenerateContent requests per minute for this API project
on both Flash models tried. A real search now produces a clear quota error and
does not show unverified results. No live accuracy claim is justified by that.

## 50-video accuracy investigation (2026-10-17)

A separate test harness and 50-file local set are now prepared. The set uses five
Mendeley exercise categories (abs, back, bicep curl, push-up, squat), ten
participants per category, opaque media names, SDR H.264 inputs, and a
participant-held-out split (participants 001–005 for development; 006–010 for
test). Provenance and original answer labels live only in ignored local files
under `data/evaluation/visual-search/mendeley/`; they are not committed. The
benchmark runner requires its own SQLite database and refuses the normal
Storyroom database.

No 50-video search-quality score is available yet. The 100-query set still
needs human review and timing labels. One selected curl clip has been indexed
with Gemini Embedding 2 under the creator's explicit authorization; the full
50-clip set has not been indexed. No successful verifier request or paid model
comparison was made.

The red-team harness detects the false-match patterns using deterministic fake
vectors and checks that the new verifier boundary excludes them. This does
**not** measure Gemini accuracy. See [current project status](STATUS.md) for
the actual checks and quota blocker.

## What was tested

The three existing Commons clips are “Jumping jacks and burpees,” “Double
kettlebell clean and jerk,” and “Kettlebell swing, hip-hinge style.” They are
attributed to Taco Fleur / Cavemantraining under CC BY-SA 4.0. A fourth clip,
[“Boxing training”](https://commons.wikimedia.org/wiki/File:Boxing_training.webm),
is by Evworo under CC BY-SA 3.0. Its local source, conversion, hashes, and actual
media properties are recorded in the ignored
`data/evaluation/commons-boxing/PROVENANCE.md` file. It is a 10-second, 1920×1080
boxing drill with a coach, not a heavy-bag video.

All four clips were imported through Storyroom, prepared by its worker, and
indexed from prepared proxies with Gemini Embedding 2 (768 dimensions, unpaid
service configured). The existing three produced 106 ranges; boxing added 8.
Search uses cached text-query embeddings and exact cosine comparison in SQLite.
No model was trained. No caption, filename, or source-title text participates
in visual ranking. Four clips from two Commons contributors are still a small,
related sample; they do not test arbitrary camera footage or broad domains.

## Historical embedding-only gate

Before this change the endpoint always returned the top five ranked events. It
did not check whether a result was a plausible match or whether other clips
scored almost as well. This meant every query—including unsupported prompts—was
forced to look like a successful search. The search then grouped and locally
refined times, but those operations only shaped boundaries; neither verifies
that the event depicts the requested action.

The previous visual search had a separate conservative rejection step after event
ranking: a best cosine score must clear a pilot floor, the best source clip must
separate from its runner-up, weaker source clips are suppressed, and weaker
events inside a retained clip are removed. The current pilot constants are in
`server/vector_index.py`. They are raw cosine-ranking cutoffs, **not confidence
probabilities**, and have not been calibrated on a representative labeled set.
When the gate rejects results, the UI asks the creator to describe the visible
action more specifically. Exact cosine search remains in use.

This gate remains useful for comparing the embedding-only baseline. It is no
longer the live result decision. The video verifier is now connected, but its
quality comparison remains blocked by the project's zero generation quota.

## Live query results

The result ranges below are seconds on Storyroom’s normalized 30-fps clock.
Scores are internal diagnostics and are not shown as confidence in the app.

| Prompt | Returned result(s) | Assessment |
|---|---|---|
| `jumping` | Jumping/burpees source: 23.20–25.37, 11.00–13.17, 34.20–35.97, 0.00–2.57 | **Fail for timing/meaning.** Other source clips are now suppressed, but this broad prompt still returns several weak or wrong times inside the one plausible source. |
| `jumping jacks` | Jumping/burpees: 0.00–2.57, 10.00–13.17 | Correct source and action at both reviewed locations. The first end is still about half a second later than the visible action transition. |
| `burpees` | Jumping/burpees: 36.40–38.77, 32.20–34.20, 40.00–42.00, 25.60–27.60 | Correct source, but the full set is not verified and includes a likely false/ambiguous range. **Partial, not a pass.** |
| `kettlebell swing` | Swing source only; top ranges 4.20–7.97 and 46.20–50.20 | Cross-clip leakage is suppressed. The returned source is right; exact movement boundaries and every additional occurrence are not fully reviewed. |
| `double kettlebell clean and jerk` | No result | **False negative.** The short label scores the clean-and-jerk and swing footage almost equally, so the gate abstains. |
| `the person lifts two kettlebells from the floor to the shoulders then pushes them overhead` | Clean-and-jerk source only; 4.40–6.40, 19.20–21.20, 12.20–13.97 | Correct source survives with the more descriptive prompt; individual ranges still need frame-by-frame validation. |
| `boxing` / `boxing training` | Boxing source only; 4.80–10.00 and 0.00–1.80 (short prompt); 4.80–10.00 (longer prompt) | Correct source found. The 0–1.8 range is weakly localized and should not be treated as a verified punch segment. |
| `punching a heavy bag` | No result | Appropriate for this particular clip: it shows practice with a coach and no heavy bag. |
| `cat sleeping` | No result | Appropriate rejection for this four-video project. |

The strongest positive and negative evidence is that `jumping jacks`, `boxing`,
and `kettlebell swing` now stay with their visually appropriate source files,
while the unsupported cat prompt returns nothing. The important failure is that
`jumping` still surfaces wrong moments within the right file, and short
clean-and-jerk language is rejected. This shows the separate clip-level gate
fixes cross-file leakage but cannot validate action meaning or precise time.

## Reproduction and checks

Project: **Visual search QA · Commons actions**. Search in Visual AI mode after
opening this local project. Indexing footage requires explicit cloud-analysis
permission; the test clips were sent to the provider. The app was configured for
the unpaid tier and reported an estimated provider price of $0; Storyroom cannot
verify the provider account's billing/quota state, and its local ledger retains
conservative reservations. The generation endpoint was not used.

The four-source live indexing/search check completed on 2026-10-16. Focused
backend visual-search tests pass. Full-suite/build/browser results are recorded
in [STATUS](STATUS.md). Results above include failures by design; this pilot does
not meet the larger reviewed-query acceptance gate in [ROADMAP](ROADMAP.md).
