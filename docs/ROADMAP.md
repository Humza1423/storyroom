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

## 3. Validate footage intelligence, not just the adapter

Keep pretrained inference behind the existing AI boundary. Verify current model
identifiers, SDK compatibility, account availability, and pricing before a real
call. Gemini is the current adapter, not a demonstrated best model. Compare
alternatives only on relevant failures; see [MODELS](MODELS.md).

Pipeline: normalized proxy → overlapping chunks of at most 30 seconds at 2 fps →
structured observations → validated frame ranges → description embeddings →
local keyword/vector retrieval. Sparse sampling can miss fast motion; do not
promise precise action boundaries or successful-attempt detection.

Reserve cost before dispatch, cache by content/model/prompt/settings, reconcile
reported usage, and include retries in the budget. Keep credentials backend-only.
The ledger covers this app's requests, not all provider spending. No silent model
switches or unbounded agent loops. The current pipeline omits audio transcription.

Acceptance: one permissioned clip works with a real provider; timestamps are
manually checked; costs are compared with billing; timeouts, malformed output,
rate limits, cache reuse, cancellation, and budget exhaustion behave safely.

## 4. Complete the story workspace

Generate sections from the brief and actual inventory. Retrieve/rerank a small
candidate set for each section and expose alternatives in the UI. Backend code
alone is not the feature. Allow custom sections and repeated use of a moment;
preserve independent trim/placement for each selection. Keep proposals separate.

Acceptance: a creator can request alternatives, accept selectively, ignore AI,
reorder, undo, and reopen with exact choices intact. Empty or uncertain results
are legitimate. Measure whether organizing helps decisions rather than adding work.

## 5. Evaluate and prepare an open-source release

Prepare 20 human-reviewed retrieval queries across at least three footage sets.
Initial engineering target: a relevant candidate in the first five for at least
16 queries. Report misses, analysis cost/time, and unsupported queries. Compare
complete manual and AI-assisted workflows on unfamiliar footage.

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
