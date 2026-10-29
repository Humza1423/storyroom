# Search quality: research and next implementation ticket

Planning/research only, 2026-10-26. No runtime code changed, provider inference,
media upload, billing change, new model installation or accuracy improvement.
Repository checkpoint: `809d0d2`, `codex/gemini-activity-search`.

## Decision

Keep Gemini Embedding 2, exact vector retrieval, SQLite and the existing worker.
The next ticket is **duration-independent recognition and inspectable failures**.
Then address complete-move boundaries and distinct occurrences. Do not start with
ANN, reindexing the library, a different model family or an agent framework.

Storyroom's objective is an editing decision, not a plausible search result:
find matching activity → inspect it → choose a useful cut → save in a Storybin →
render/export without changing the creator's accepted frames.

## Evidence and gaps

The saved eight-video/24-query test returned labeled relevant moments for 12/16
positives, labeled relevant first results for 12/13 returned searches, no false
returns on eight fixed negatives and requested duration for only 1/5 queries.
Four continuations failed with partial work retained. Only one discrete label
contributes to the 0.70-second boundary median. These are pilot results, not broad
accuracy or complete-move proof. See [the report](GEMINI_ACTIVITY_EVALUATION.md).

| Gap | Evidence / certainty | Consequence |
|---|---|---|
| Recognition and edit duration share one decision | Correct badminton, horse and Earth sources rank first/second; cached short-crop verdicts are `no_match` for 20-second prompts. Confirmed failing stage; precise model reasoning remains unknown. | Matching footage is hidden before continuation can inspect enough of it. |
| Presence is confused with a complete move | Push-up 21.2–23.6s passes overlap scoring but begins during descent. | A mathematically acceptable hit can be an unusable edit. |
| Continuation failures lose their useful explanation | Provider parsing collapses validation failures; worker substitutes generic `Activity inspection failed`. | We cannot tell which invariant failed without repeating the request. |
| Grouping is not a semantic occurrence model | `distinct_activities` suppresses ≥80% overlapping spans; no union across gaps. Conservative, but still heuristic. | Duplicate views can consume inspection work; distinct moves/pauses need better evidence. |
| Shortlist can spend its five slots near the same location | Raw anchors are suppressed by center distance, not verified event identity. Risk from inspected code, not a measured cause for the three duration misses. | More requests may inspect near-duplicates instead of finding a second occurrence. |
| Evaluation undercounts possible valid occurrences | Historical key mistakes are documented; current discrete labels are sparse. | A valid unlabelled event can look wrong, while an incomplete labelled move can pass IoU. |
| Search is expensive when uncached | 43 video SDK calls across 24 queries; 1,065.8 supplied video seconds; total p50 10.94s. | Reduce redundant work, not semantic checks merely to report faster results. |

## Research: what transfers, and what does not

### 1. Native embedding is candidate retrieval, not temporal proof

Google documents Embedding 2 video sampling at 1 FPS for short inputs, with at most
32 frames per video, and no processing of its audio track. Native cross-modal
retrieval is appropriate for anchors, not a guarantee of exact action boundaries.
Keep the current model; increasing verifier sampling cannot recover an event that
never reaches the shortlist. [Official embedding documentation](https://ai.google.dev/gemini-api/docs/embeddings).

### 2. Coarse selection and fine localization are different tasks

CONE (ACL 2023) uses query-guided window selection, proposal generation and
fine-grained ranking. Transfer that separation, not its trained contrastive stack:
an anchor tells us where to look, not the cut to export. Its long-video benchmark
gains do not predict Storyroom's accuracy. [Paper](https://aclanthology.org/2023.acl-long.445/),
[official code](https://github.com/houzhijian/CONE).

### 3. Relevant occurrences and attractive highlights need separate labels

QVHighlights/Moment-DETR represents multiple relevant moments and highlight
saliency separately. Borrow that distinction for activity versus suggested cut,
and label all acceptable occurrences. Its evaluator reports temporal overlap at
multiple thresholds; add complete-move playback to those metrics. No need to train
Moment-DETR now. [Paper](https://arxiv.org/abs/2107.09609),
[official model](https://github.com/jayleicn/moment_detr),
[evaluator source](https://github.com/jayleicn/moment_detr/blob/main/standalone_eval/eval.py).

### 4. Spend detail selectively, not everywhere

VideoTree (CVPR 2025) builds query-adaptive coarse-to-fine representations and
expands relevant branches. Borrow selective inspection: inspect unresolved
boundaries, not every video densely. Its main evidence is video question-answering,
not editable boundary accuracy; do not transplant its clustering/LLM stack.
[Paper](https://arxiv.org/abs/2405.19209),
[implemented depth expansion](https://github.com/Ziyang412/VideoTree/blob/main/depth_expansion.py).

BMN separates action-start/end evidence from proposal confidence. This supports
checking onset and completion separately from semantic presence; it does not make
BMN a drop-in language-query system. [Paper](https://arxiv.org/abs/1907.09702),
[official PaddleVideo implementation](https://github.com/PaddlePaddle/PaddleVideo/blob/develop/docs/en/model_zoo/localization/bmn.md).

### 5. Other published applications support the cascade, not guaranteed accuracy

SentrySearch implements video embeddings and an optional Gemini reranker. Its
single-clip reranker is useful as a diagnostic control against our batch. Its
chunk-boundary limitations, similarity thresholds and model-written confidence
are not solutions to complete-move accuracy. Do not copy its fallback behavior
into strict Storyroom search. [Project](https://github.com/ssrajadh/sentrysearch),
[actual Gemini reranker](https://github.com/ssrajadh/sentrysearch/blob/master/sentrysearch/gemini_reranker.py).

Edit Mind/Orcah demonstrates local video indexing, frame analysis, transcript and
metadata search, but adds multiple models/services and explicitly describes itself
as development software. It is not evidence that we need its infrastructure or
that its boundaries outperform ours. [Project](https://github.com/IliasHad/edit-mind).

### 6. API correctness is more specific than a valid HTTP response

Google supports multiple video parts and custom static sampling; Storyroom's
`Part.video_metadata.fps=3` is supported. Do not call batching broken without a
controlled comparison. Keep short-crop static processing for this ticket; agentic
video navigation is not automatically better for 8–30-second clips.
[Video documentation](https://ai.google.dev/gemini-api/docs/video-understanding),
[Google implementation examples](https://github.com/google-gemini/cookbook/blob/main/quickstarts/Video_understanding.ipynb).

`server/media.py::verification_clip` actually encodes a 640px-wide, silent, 3-FPS
video. A future 3-versus-6-FPS trial must change both this preprocessing and API
metadata while holding resolution fixed. Do not increase the entire index rate
to repair a confirmed semantic duration rejection.

Structured JSON provides a predictable shape, not factual correctness. Keep
client validation, evidence and timestamp rejection.
[Structured output documentation](https://ai.google.dev/gemini-api/docs/structured-output).

Current code also forces `temperature=0`. Google recommends default sampling for
Gemini 3 and newer documentation says some models ignore/deprecate these controls.
Remove the override for model compatibility after confirming the configured model's
documentation; do not promise an accuracy gain from a parameter it may ignore.
[Gemini 3 guide](https://ai.google.dev/gemini-api/docs/generate-content/gemini-3),
[current troubleshooting](https://ai.google.dev/gemini-api/docs/troubleshooting).
Storyroom already disables SDK retries with `HttpRetryOptions(attempts=1)` and
implements a bounded application retry; do not invent an unbounded-retry defect.

## Proposed next ticket: recognition first, duration second

### Intended visible output

`20 seconds of boxing` must not become `no match` merely because the initial
matching crop lasts eight seconds. It should establish visible boxing first, then
inspect enough adjacent footage to return **600 supported frames**, a genuine
shortfall, or **inspection incomplete**. Never join separated occurrences or add
burpees just to fill the requested length. A true absent action still returns no
confirmed match.

### Scope and implementation boundaries

1. **Preserve diagnostic reasons before changing prompts.** In `grounding.py`,
   give known validation failures stable safe codes: missing candidate, out-of-
   context time, invalid interval, unsupported continuity, unrelated anchor,
   malformed response and provider failure. Retain stage, crop hash/range/FPS,
   candidate ID, model/returned version, prompt version, batch membership/order
   and usage. No credentials, raw footage, hidden chain-of-thought or unbounded
   response logging. Keep existing valid siblings/partial progress.
2. **Make constraints orthogonal in the existing response.** Keep visible action
   kind (continuous/discrete) separate from requested edit length. Explicitly tell
   Gemini to report a visibly present activity even when the crop cannot satisfy
   the requested output length. Return a short observable rejection reason for
   no/uncertain matches. Preserve subjects, objects, relations and genuine action
   duration conditions; do not blindly delete every number from a query.
3. **Let existing cut logic decide feasibility.** `activities.py` calculates the
   requested frame count, inspects supported adjacent activity via the worker and
   selects inside that activity. Duration fulfillment must not establish semantic
   relevance or boundary completion. Leave embedding inputs/retrieval/indexes
   unchanged so this comparison isolates the confirmed failing layer.
4. **Version the changed contract/cache.** Retain historical results. Record the
   request batch fingerprint for reproducibility; current cached per-candidate
   results do not prove batch-order independence. No blanket reindex or destructive
   cache wipe. Old projects and accepted cuts remain readable/unchanged.
5. **Use one controlled trial, not repeated prompt tweaks.** Baseline comes from
   existing cached results with network disabled. Run the revised contract once
   over the same 24 development queries, same model, crops and initial batch.
   Cap the trial at 24 initial + 16 continuation generation attempts and 1,500
   supplied video seconds, counting retries. Stop on quota/budget/cancellation;
   report unfinished checks honestly. No paid fallback or new classifier request.

### Acceptance and verification

- An eight-second crop visibly showing the requested action remains a semantic
  match under a 20-second output request; feasibility is separate.
- Twenty supported continuous seconds yields exactly 600 frames; shorter activity
  reports the available range; incomplete inspection never claims a true shortfall.
- Retain no-result behavior on all eight fixed negatives, plus existing bag versus
  kettlebell and push-up versus curl regressions. Unverified failures never pass.
- Correct-source retrieval/ranking remains unchanged in this experiment. Report
  before/after decisions, duration fulfillment, positive recall, first-result
  precision and exact failure codes; do not promise a score before the trial.
- Invalid/reversed/outside/NaN timestamps remain rejected. Provider/malformed
  failures preserve valid sibling results, completed stage data and accepted cuts.
- Same query reuses validated completed work. Include paraphrases and ambiguous
  duration syntax tests without claiming a general language parser.
- Run backend suite, build, isolated browser and media regressions. In the real
  app, replay a successful duration result, an honest shortfall and an absent
  action, then add/trim/save/reopen/render/export with exact saved frame checks.
- Produce one before/after table and one clear next decision. Keep preview opt-in
  if the quality gate fails. No automatic threshold relaxation.

### Explicit exclusions

No ANN/vector database, new model family, fine-tuning, reindexing, new backend
framework, full UI redesign, general query agent, paid tier change or unconditional
padding. Do not change recognition, batching, sampling and model simultaneously.

## Following gates before calling search finished

**Boundary/occurrence ticket:** label and inspect at least ten complete moves;
track onset lateness/end truncation and visible preparation/finish, not just IoU.
Test pauses, adjacent actions, separate occurrences. Compare denser local sampling
only on confirmed fast-action misses. Group only supported same occurrences, and
avoid inspecting their duplicate contexts repeatedly. Treat three-versus-six FPS
or single-versus-batch requests as separate bounded experiments if evidence calls
for them, not simultaneous production changes.

**Release validation ticket:** after selecting a configuration, use fresh licensed
sources and prewritten queries, covering continuous activities, discrete moves,
output durations, repetitions and hard negatives across sports and non-sports.
Label all valid occurrences independently of predictions; retain uncertainty and
adjudicate disagreements. Keep previous gates: ≥95% returned-first precision,
≥90% positive top-five moment recall, zero fixed-negative false matches, median
discrete boundary error ≤1s. Also require no truncated reviewed complete moves,
exact duration where supported and honest insufficiency/uninspected states.
These small-sample gates justify a bounded MVP preview, not universal accuracy or
Adobe parity. Validate the creator's full selection-to-Resolve workflow.

If clear semantic/action failures remain after the corrected contract and
appropriate context, compare **one** stronger available Gemini model on the same
small cases. Higher paid quota does not repair application logic or by itself
make the same model more accurate. Propose a different model family only after
that measured limitation, not alongside this ticket.

## Learning exercise

Trace `suggested_cut` and `_refresh`: matching activity 0–8s, requested edit 20s.
Predict the selected frames, duration-fulfillment flag and boundary-completion
state. Then explain why a true semantic match is neither proof of 20 seconds nor
proof that the action's beginning/end has been seen. These are separate facts.

## Research limits

Sources were read and relevant public code inspected, not installed or benchmarked
against Storyroom. Research mechanisms are hypotheses until tested here. No claim
that papers' published numbers transfer. Moment-DETR's code and dataset have
different licenses; verify video/data/model permissions separately before reuse.
TimeLens label-quality work was reviewed as background, but its restricted assets
are not proposed for incorporation. A relevant CVPR2026-workshop abstract was found,
but full primary-paper access was unavailable, so it is not a dependency of this
decision. No broad repository audit or implementation was performed.
