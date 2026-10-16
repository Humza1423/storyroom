# Visual-search quality check

Updated: 2026-10-16. This is a small live engineering pilot, not an accuracy
claim. It uses four licensed, short exercise videos in the local project
`Visual search QA · Commons actions`. Pexels footage was not indexed.

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

## Engineering leak and correction

Before this change the endpoint always returned the top five ranked events. It
did not check whether a result was a plausible match or whether other clips
scored almost as well. This meant every query—including unsupported prompts—was
forced to look like a successful search. The search then grouped and locally
refined times, but those operations only shaped boundaries; neither verifies
that the event depicts the requested action.

Visual search now has a separate conservative rejection step after event
ranking: a best cosine score must clear a pilot floor, the best source clip must
separate from its runner-up, weaker source clips are suppressed, and weaker
events inside a retained clip are removed. The current pilot constants are in
`server/vector_index.py`. They are raw cosine-ranking cutoffs, **not confidence
probabilities**, and have not been calibrated on a representative labeled set.
When the gate rejects results, the UI asks the creator to describe the visible
action more specifically. Exact cosine search remains in use.

This is a precision-oriented patch, not the final search architecture. The
remaining semantic weakness is that the same visual embedding scores very
similar movements and scenes closely. The next real improvement is a second
stage that checks the top candidate ranges for the requested action using a
temporal video model, before the existing local boundary refinement. The free
Embedding 2 endpoint does not provide that independent verification, and the
configured Gemini video-generation endpoint has no available quota in this
environment. Do not silently add paid calls. Compare an available verifier
against human labels before choosing its provider or changing the index.

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
