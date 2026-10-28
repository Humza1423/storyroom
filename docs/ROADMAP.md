# Delivery roadmap and implementation approach

[PRODUCT](PRODUCT.md) owns intent; [STATUS](STATUS.md) owns current completion
claims and the live checklist. This is the order of work and its acceptance gates,
not a claim that the original schedule has been met. Some later-stage code already
exists; finish evidence and reliability before adding more surface area.

## 1. Reliable local foundation

The executable scope and acceptance gates are in
[FOUNDATION_PLAN](FOUNDATION_PLAN.md). The subsequent real-footage exercise is in
[FOOTAGE_TEST_SET](FOOTAGE_TEST_SET.md).

Use the existing React/TypeScript interface, FastAPI validation boundary, SQLite
storage, and one persistent Python worker. Keep FFmpeg processing outside HTTP
requests. See [ARCHITECTURE](ARCHITECTURE.md) for the implemented flows.

Foundation implementation now includes the isolated browser harness, transactional
migrations, frontend modules, startup/recovery checks, Python lockfile and CI workflow.
See STATUS and FOUNDATION_PLAN for measured acceptance results. The manual
real-footage handoff has been verified; hosted infrastructure and model training
remain deferred.

Acceptance: a fresh test run cannot change personal projects; old project data
survives upgrades; refactoring preserves behavior; startup failures are actionable.

## 2. Prove the manual vertical slice

Phases A1–A3 cover resilient batch import, independent generated-media correctness,
and bounded processing diagnostics. A four-source licensed real-footage workflow has
now passed inside Storyroom, including restart persistence and rendered-preview
checks. The actual Resolve 21.1.1 application import was also visually verified;
see current evidence and limits in [STATUS](STATUS.md).

Import → normalize → select clips → trim/reorder → save/reopen → preview →
render → export and inspect in Resolve. Edit boundaries are integer frames with an exclusive out
point. Source assets, observed moments, and placed selections remain distinct.
Board revisions provide recovery and prevent stale writes from overwriting changes.

The small licensed-footage Resolve import preserves tested order, references,
audio/silent ranges, and 30-fps cuts. A later
[mixed-profile check](MEDIA_COMPATIBILITY.md) covers portrait, silent, VFR-derived,
and rotation-tagged H.264 inputs through an actual Resolve import. Expand only
where real camera evidence warrants it before claiming broad codec compatibility;
HEVC/HDR and portable relinking remain unproven. A valid XML file or OTIO
round-trip alone does not pass this gate.

The subsequent 4K online-footage check confirmed the FCP7 timeline imports and
plays in Resolve 21.1.1, but also exposed a performance gap: unconditional
full-resolution software transcoding is too slow on the 8 GB development Mac.
Treat 1080p as the practical backbone for development, testing, and demos; 4K
remains accepted but experimental. Defer encoder/disk optimization until better
hardware or user demand justifies it. This does not silently lower the output
resolution or weaken the verified 1080p and 4K handoff checks.

## 3. Direct visual search vertical slice

Current Gemini-first milestone: [approved plan](GEMINI_COMPLETION_PLAN.md).
Ticket 1 corrected the historical labels. Tickets 2–3 now have an opt-in combined
grounding/activity pipeline and actual app/Resolve handoff, but the frozen fresh
evaluation misses quality gates (12/16 moment recall; only 1/5 durations).
See [the checkpoint](GEMINI_ACTIVITY_EVALUATION.md) and
[focused research-based tickets](AI_SEARCH_TICKETS.md). S1a–S1c now provide safe
diagnostics, independent edit duration and unresolved-boundary handling. Their
controlled development comparison did not improve aggregate quality/speed; provider
failures and fragmented movement remain explicit. The three-cut app/render/
Resolve handoff passed. S1d now implements same-activity continuation and full-
activity frame selection, with a five-cut render/Resolve check. Its bounded live
comparison still fails two of four reviewed boundaries, so **S1 remains open**;
see [activity-review evidence](ACTIVITY_REVIEW_EVALUATION.md). Do not start S2
until the continuation gate is resolved or its scope is explicitly revised.
After that, S2 checks complete movements independently of overlap
scores; S3 checks continuous activity/occurrence grouping and bounded reuse; S4
freezes fresh release examples only after selecting a configuration.
Keep exact retrieval and Gemini;
no default promotion or parallel model integration. The older twelve-video
numbers below are historical, not the current release decision.

The provider/index/retrieval/UI code is implemented on the feature branch; see
[STATUS](STATUS.md) for the exact test evidence. It adds a distinct Gemini
Embedding 2 path over adaptive event/detail ranges of prepared 720p proxies,
cached text-query embeddings, SQLite persistence, exact cosine ranking, and
playable candidates that become ordinary frame-range selections. Existing keyword
and description search remain separate. The model is a candidate generator, not
an exact action detector; audio is not indexed. Vector spaces are isolated by
provider, model, dimensions, proxy hash, and sampling version.

The live adapter now uses Gemini Embedding 2 to shortlist distinct events and a
separate video verifier to check visible action before returning a candidate. The
earlier score-based gate remains as a benchmark baseline. Verifier fan-out is
bounded to one uncached request containing up to five labeled candidate clips
per explicit search page; cached confirmed results survive a batch failure.
The alternate unpaid project now supports live searches. Page 0 remains
unchanged; creators can explicitly inspect further verified candidates without
automatically increasing every query's cost. The Commons exercise check found
an early burpee that ranks tenth and is too narrowly cut to show a full
movement. A smaller reviewed 16-video/20-query development diagnostic found
the correct source for all 12 positives but the correct playable moment for only
9; sports timing was weakest (1/4). Ticket 1 added an **opt-in** bounded,
query-aware localization pass: it improved four sports development queries
from 1/4 to 3/4 useful moments, but one cut still misses the requested action
and the pass adds an API request. It remains off by default. A diverse
12-video/40-query held-out pilot is now complete: relevant moment in top five
25/30 positives, first-result precision 24/29 returned searches, zero false
positives on 10 negatives, and 3.23-second median maximum boundary error.
Several answer-key intervals need correction; see
[the evaluation report](HELDOUT_EVALUATION.md) before interpreting these as
model-quality scores. The next step is one focused answer-key audit and an
event-fragment fix if confirmed by footage, followed by one rerun—not another
model or ANN change. Preserve
the embedding retriever and frame-range selection format. Compare provider
billing with Storyroom's conservative reservation. Do not use
Pexels for indexing. Google unpaid-service data terms and human review mean the
dataset itself must be suitable for cloud submission; source license alone does
not establish that. The UI requires explicit indexing and cloud-analysis
permission; do not submit sensitive, confidential, or personal footage. If no
suitable human footage is cleared, test the API with non-personal footage and
defer the human-footage quality claim.

Preserve the no-AI path. Timeouts, malformed vectors, rate/quota limits, cache
reuse, partial indexing, cancellation, model isolation, and budget exhaustion
must remain safe. Use the results to decide whether Gemini's direct visual
retrieval is useful and what alternative, including local open weights, is worth
benchmarking; do not assume it is the best model.

## 4. Complete the story workspace

Generate sections from the brief and actual inventory. Retrieve/rerank a small
candidate set for each section and expose alternatives in the UI. Backend code
alone is not the feature. Allow custom sections and repeated use of a moment;
preserve independent trim/placement for each selection. Keep proposals separate.

Acceptance: a creator can request alternatives, accept selectively, ignore AI,
reorder, undo, and reopen with exact choices intact. Empty or uncertain results
are legitimate. Measure whether organizing helps decisions rather than adding work.

## 5. Evaluate and prepare an open-source release

The diverse 12-video/40-query held-out pilot is complete; its labels and event
fragmentation limit the conclusions. First audit the few known bad/broad labels,
make one focused event-grouping improvement if footage confirms it, and rerun
the same pilot once. Only then decide whether a larger set is necessary; do not
treat the earlier 50-video/100-query proposal as a prerequisite. Any future
expansion should add genuinely different scenes and sources, split by source
group, and include human-reviewed positives, paraphrases, and hard negatives.
Report top-five recall,
top-one precision, negative-query false positives, and boundary error separately.
The working pilot targets are 90% for the first three retrieval measures (with
negative-query false positives at most 5%) and median boundary error at most one
second; publish per-action misses instead of averaging them away. These are
engineering targets, not evidence of product demand or Adobe parity.

Fifty local Mendeley inputs have been prepared, but they are not yet part of this
completed benchmark and are not a prerequisite for the focused next step. Do not send these
participant videos to Gemini's unpaid service without documented consent for
that processing purpose: the dataset page's reuse license is not a privacy
release, and Google's unpaid terms prohibit submitting personal information.
Proceed with live model comparison only after that constraint is resolved, or
with appropriate footage that does not depict identifiable people. Paid model
calls remain outside the approved scope. Do not alter the result cutoff based
only on the current red-team examples.

Acceptance: clean-machine setup from README, full relevant automated checks, real
Resolve evidence, honest demo, license/provenance review, and documented limits.
Source is public and verified checkpoints are routinely pushed under the creator's
authorization. Public source is not proof of a validated product launch. Interview
and adoption tasks remain saved for later in STATUS.

## 6. Custom ranking experiment after usable labels exist

Use the explicit relevance-labeling workflow with permitted footage. Aim for
300–500 reviewed candidate judgments across multiple shoots. Split by footage
group, not individual clips. Train the regularized logistic-regression baseline
and compare held-out ranking metrics against retrieval without the trained model.

The existing script uses lexical score, available semantic score, capped duration,
and uncertainty presence. It does not yet model requested-duration fit or directly
encode the brief. Fix missing-feature handling and add tested runtime inference
only when justified. A saved model file is not a deployed improvement.

Acceptance: reproducible data provenance, grouped evaluation, reported limitations,
and measurable held-out improvement before activation. No labels means no training
claim. Add a narrow visual classifier only after identifying a specific visual gap.

## Schedule and later options

The original two-week allocation was foundation (days 1–2), media (3–4), intelligence
(5–6), workspace (7–9), handoff (10–11), evaluation/release (12–14). Treat it as
scope guidance, not current progress. Training was a separate roughly one-week
experiment once labels exist. Cut polish and advanced suggestions before cutting
persistence or export reliability.

After real use: broader codecs/original relinking, measured retrieval improvements,
a second niche, easier packaging, then possibly beginner finishing or collaboration.
Hosted use needs a separate design for authentication, isolation, object storage,
distributed jobs, quotas, and operations. Do not introduce those systems into the
single-user prototype merely to appear startup-ready.
