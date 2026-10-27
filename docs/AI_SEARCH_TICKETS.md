# AI search delivery tickets — 2026-10-27

Goal: matching footage → usable cut → Storybin → render/Resolve. This plan follows
the [research brief](SEARCH_QUALITY_RESEARCH_2026-10-26.md), relevant original papers,
official implementation inspection, and three independent reviews. It supersedes
any implication that the previous 24-query pilot completed search quality.

## Research decisions

| Work inspected | Mechanism and requirements | Storyroom comparison / decision | Expected benefit and test |
|---|---|---|---|
| [CONE paper](https://aclanthology.org/2023.acl-long.445.pdf), [inference code](https://github.com/houzhijian/CONE/blob/main/cone/inference.py) | Rank overlapping windows using visual/text alignment, run trained proposals, rerank/local suppress spans; needs pretrained feature encoders and trained grounding weights. | We already retrieve visual anchors then inspect cropped video. Borrow task separation; do not reproduce the training stack or assume its score fusion transfers to Gemini. | Prevent anchors becoming final cuts; track raw retrieval separately from verified moments. |
| [QVHighlights paper](https://arxiv.org/pdf/2107.09609), [Moment-DETR model](https://github.com/jayleicn/moment_detr/blob/main/moment_detr/model.py), [evaluator](https://github.com/jayleicn/moment_detr/blob/main/standalone_eval/eval.py) | Separate relevant spans and saliency; trained set prediction and assignment losses; evaluation over multiple temporal-overlap thresholds. | Adapt multiple-occurrence labels and metric definitions in our own small scorer, not the trained model. Our suggested cut is not the full relevant activity. Code/data/media have separate rights. | Score each acceptable occurrence, duration support and complete-move usability separately. Its coarse labels cannot prove subsecond editing quality. |
| [VideoTree paper §§3,7,10](https://arxiv.org/html/2405.19209v3), [depth expansion](https://github.com/Ziyang412/VideoTree/blob/main/depth_expansion.py) | Cluster visual features, caption representatives, relevance-guided subclustering; requires encoders/captioners/LLM and targets QA. | Borrow bounded selective inspection only. Our worker already expands adjacent crops; a tree or caption stack adds complexity without demonstrated need. | Spend detail on unresolved action boundaries, not every frame. Compare call/video-second counts and actual boundary playback; QA scores do not establish editing accuracy. |
| [SentrySearch Gemini reranker](https://github.com/ssrajadh/sentrysearch/blob/master/sentrysearch/gemini_reranker.py) | One video/query per structured reranking call. | Retain as a diagnostic single-crop control if batching is implicated. Do not copy confidence-as-probability or unverified fallback. | Identical crop alone versus original batch isolates batch effects; not part of the first prompt comparison. |

No third-party research code or weights are being imported by these tickets.

## Gap ownership and evidence

| Gap | Failing stage / certainty | Fix / visible outcome | Gate |
|---|---|---|---|
| Duration rejections | Correct source reaches inspection; cached `no_match`. Cause remains a hypothesis. | S1b independent recognition/edit length; matching short crop stays available. | Same crop/model/batch, paired duration queries; strict negatives retained. |
| Incomplete move | Presence/localization: push-up begins during descent. | S2 distinguish available inspected extent from observed move onset/finish. | Complete execution watched, onset lateness/end truncation, source-truncated negative. |
| Duplicates/incorrect grouping | Overlap and temporal continuity heuristics; broad issue not fully measured. | S3 supported occurrence identities, not proximity-only joins. | Pauses, adjacent actions, alternating people, separated repetitions. |
| Hidden failures | Validation collapses reasons, worker substitutes generic error. | S1a safe failure codes and preserved valid siblings. | Invalid times/IDs/provider/cancel, no leaked secrets, unchanged acceptance. |
| Evaluation gaps | Few discrete labels; overlap can reward truncated cuts or ignore valid alternatives. | S2/S4 playback labels all acceptable occurrences; separate presence/completeness/duration. | Frozen labels before predictions, misses kept in denominator. |
| Wasteful calls | Duplicate contexts may be re-inspected; no causal speed claim yet. | S3 measure and reuse established occurrence inspections. | Compare actual dispatches/context seconds, never skip semantic verification. |
| Confusing UI | Dense card status; open preview can retain stale activity evidence; global completion may erase page warnings. | S1b calm duration states and independent progress; preserve manual draft/accepted cuts. | Real browser and explicit duration/failure/resume/stale-query checks. |

## S1a — Safe diagnostics, no decision changes

Implement stable validation codes in the provider boundary, a compact bounded
candidate/context manifest and safe errors preserved into the existing job result.
Do not change prompts, sampling, retrieval, acceptance or frames. Existing fake
provider tests plus focused new failures establish this contract, not accuracy.
Commit this checkpoint independently before S1b, and push verified work to PR #6.

## S1b — Recognition and duration are separate facts

Provider action intent stays broad activity or discrete move. A nullable requested
edit duration is independent; actual event-duration conditions remain semantic
requirements. Keep the original query in retrieval and inspection. No additional
query-classifier request, threshold relaxation or library reindex.

The combined request reports visible matching intervals even when a crop is too
short to fulfill an output duration. Local frame logic and worker continuation
decide fulfillment. A source extent exhausted is not proof of a complete move.
Version the new contract/cache; old projects/results and accepted cuts survive.

User-facing states for a 20-second request:

- 600 supported frames: exactly 20 seconds selected; boundary inspection may
  separately remain incomplete.
- Whole available matching activity 240 frames: select all eight seconds. Calm
  informational message: “Requested 20 seconds. Found 8 seconds of this activity.
  The full 8 seconds are selected.”
- Only 240 inspected frames with unresolved edges: eight seconds available so
  far; checking more footage, not a confirmed shortfall.
- Failure/cancellation: explain inspection stopped, retain usable confirmed
  ranges; never change it into no-match or verified insufficiency.

Keep suggested cut/activity/full source distinct. Update the open preview's
activity evidence without overwriting its manually adjusted range or a saved cut.
Keep candidate inspection state separate from search-page coverage warnings.

Controlled development comparison: retain historical key and cached baseline;
same 24 queries/model/initial crops/batch/sampling, revised contract once. Maximum
40 actual generation attempts and 1,500 supplied video seconds including retries;
no paid fallback. Record unfinished work on quota/cap. Add matched query pairs
with identical action wording and duration-only variation to isolate the hypothesis.
Review continuous support independently; historical labels alone cannot certify
20-second semantic continuity. Do not tune repeatedly against final examples.

Verify backend, build, isolated browser and retained media correctness. In the real
app play sufficient-duration, shortfall, incomplete and absent-action cases; adjust,
save/reopen, render and inspect export. Report exact frames, recognition, duration,
rejection, latency, calls and remaining limitations separately. Commit/push/CI.

## S1c — Retain recognition without pretending a conflicting boundary is known

The unchanged S1b trial exposed a dependency: p01 and p05 contain model `match`
intervals passing numeric bounds/order/frame/anchor checks, but a conflicting
continuation boolean vetoes the entire candidate. p04 separately fails numeric
timestamp bounds; that rejection must stay. Do not treat these as one failure.

Keep an otherwise valid local match as partial evidence, explicitly mark the
conflicting boundary unresolved, and retain bounded numeric/boolean diagnostics.
Never simply drop the veto and mark the span complete. Further inspection must
semantically establish any extension across the unresolved area; no gap filling
or automatic padding. Preserve prior work on failure/no progress. Change only this
validation/partial-state policy, not the S1b prompt, model, sampling or retrieval.
Version caches, retain historical evidence, and test both conflicting edges,
legitimate interior stops, invalid timestamps, interrupted continuation and honest
duration messages. After the unchanged S1b trial ends, compare affected examples
plus a negative in a separate trial capped at eight generation dispatches and 300
supplied video seconds. State any incomplete comparison; no paid fallback.
Retain stopped continuation snapshots on repeated searches; require the existing
Activity-panel retry action instead of silently starting the same failed work again.

## S2 — Complete movements and honest boundaries

Independently watch and label at least ten moves with preparation/execution/finish,
including source clips that start/end halfway through a move. Preserve old keys.
Separate source/crop exhaustion from observed action completion in the contract
and UI. Inspect only promising endpoint neighborhoods more densely if the current
samples miss them; change both actual preprocessing and API FPS for a sampling
comparison. No fixed buffer that absorbs the adjacent action. Acceptance includes
actual full-move playback, onset lateness/end truncation, all misses and counts;
temporal IoU alone cannot pass this ticket. Keep one-variable experiments.

## S3 — Distinct occurrences and bounded inspection

Review real continuous activity with pauses, action changes, multiple actors and
repeated separate events. Establish continuity from visible matching activity in
the overlap; don't infer identity solely from overlap magnitude. Reuse already
established occurrence evidence rather than expanding each duplicate anchor.
Keep result diversity and recurrence recall separate from clip similarity.
Compare requests/video seconds/latency to S1b on the same footage; retain strict
rejection and accepted-cut independence. Do not add ANN for this quality problem.

## S4 — Frozen release check and editing demonstration

Use new licensed sources and prewritten, playback-reviewed queries only after
selecting a configuration. Cover broad activities, complete moves, explicit edit
durations, event-duration conditions, pauses, adjacent actions, repetitions and
absent actions. Annotate all valid occurrences and uncertainty independently of
predictions. No retuning on this final set. Existing pilot gates remain ≥95%
returned-first precision, ≥90% positive top-five recall, zero fixed-negative false
returns, and median discrete boundary error ≤1s, with explicit matched/eligible
counts. Also require reviewed complete movements and supported-duration checks;
passing a small pilot is not universal accuracy or Adobe parity.

Show actual footage in Storyroom, adjustment, Storybins, save/reopen, assembly,
render and actual Resolve import. Stop with one clear limitation/next comparison
if application fixes and suitable context still cannot produce usable results.
Compare only one stronger Gemini configuration before proposing another family.

## Review decisions

Skeptic: approve diagnostics first; do not label the duration hypothesis proven;
existing completion flags and IoU cannot establish movement completeness.
Editor: preserve useful eight-second clips and manual drafts; show calm independent
duration, inspection and failure states. Solution review: fix the orthogonal
contract before retrieval; do not copy whole trained research stacks.

Coordinator: adopt these constraints. No billing change, model switch, ANN,
speculative infrastructure, broad repository audit or automatic main merge.
