# Visual-search quality check

Updated: 2026-10-17. This page records a small live engineering pilot, not an accuracy
claim. The earlier pilot used four licensed, short exercise videos in the local project
`Visual search QA · Commons actions`. Pexels footage was not indexed.

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
