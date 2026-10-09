# A2: prove media geometry, timing and audio

Planned 2026-10-09 at local commit 70515a9, before implementation. The creator
requested planning, coordinated agents, implementation, a stronger README and
GitHub pushes after verified milestones. Native Codex Plan mode cannot be toggled
through the available tools; agents inspected read-only first and this written
plan is the execution gate. Completion evidence belongs in STATUS.md.

## Decision and alternatives

Choose small generated fixtures with independently decoded video/audio assertions,
then fix demonstrated failures. Metadata-only checks are fast but can agree with
incorrect output. Replacing the renderer wholesale adds complexity before the
failure modes are measured. Keep the local React/FastAPI/SQLite/FFmpeg architecture,
existing import boundaries and one expensive media operation at a time.

The first hypotheses are display-aspect distortion from resetting sample aspect
ratio without resizing, and timing drift from concatenating independently encoded
AAC parts. These are hypotheses until fixtures reproduce them.

## Responsibilities and sequence

1. Media engineering agent: inspect and then own server/media.py; worker metadata
   changes only if required by a reproduced defect. Explain the reason for each fix.
2. Validation agent: own tests/test_media_correctness.py and a helper if needed;
   generate fixtures, record failures against existing code, then verify corrections.
   Expected values must come from designed fixtures/independent decoders, not from
   the same production helper being tested.
3. Documentation agent: own README.md and docs/DEVELOPMENT.md; make the product,
   implemented engineering and contributor setup clear. Preserve runnable setup
   instructions. Move deep operational detail behind links and avoid invented demos,
   adoption claims or unverified model/Resolve claims.
4. Coordinator: own plan/status/handoff/workflow instructions, API/export integration
   fixes if needed, review all changes and run integration checks. Coordinate file
   ownership before crossing boundaries. Commit/push only reviewed checkpoints.

No agent commits or pushes independently. No paid calls, downloaded footage or
training are necessary for this milestone. Tests use temporary, generated media.

## Contract and acceptance matrix

| Case | Independent evidence |
| --- | --- |
| Landscape, portrait, 90-degree rotation metadata | Decoded corner markers remain upright; editing/proxy dimensions agree with pixels; render preserves aspect with documented padding |
| Non-square pixels | Display aspect survives conversion to square pixels, within even-pixel rounding; constrain normalized dimensions to supported bounds |
| 24/30/60 fps and genuine VFR | Decoded count agrees with stored editing-frame count; timestamps start at zero, increase at 1/30 second, and elapsed video length stays within one output frame |
| Nonzero source timestamps and delayed audio | First video frame defines editing time zero; audio retains its relative offset, with silence/leading trim as needed; avoid independently zeroing both streams |
| Known visual flash and tone | Decode video marker and PCM audio cue; relative onset within one 30fps frame; account for documented codec priming/tolerance |
| Audio, silent clips, repeated short cuts, final frame | Exact summed video frame count, expected source/order at boundaries, continuous 30fps timestamps, silent ranges and audio cues within one frame |
| XML/OTIO cuts and gaps | Repeated source ranges/order and silent audio gaps survive interchange; explicitly not a Resolve compatibility claim |
| Corrupt, unsupported codec/container, HDR | Real generated/marked inputs rejected with useful errors; include current import-path checks without expanding formats |
| Missing editing media | Render/export error names the affected asset |

Use tiny fixtures (typically under two seconds, low resolution) and bounded tool
timeouts. Decode representative frames and audio samples; do not load full-size
real footage into memory. Avoid new dependencies and FFmpeg-version-specific
features where portable options work. If a confirmed defect demands a different
algorithm, document the choice and bounded resource cost before implementing it.

Media policy applies to newly normalized files. Preserve existing saved sources,
editing copies and frame selections. Do not silently renormalize existing projects;
document any historical-output limitations and safe evaluation in a new project.

## Verification and delivery

Record failing reproductions before fixes, then run targeted media checks, complete
backend tests, TypeScript/build, fatal-error lint, and isolated browser workflow.
Review fixtures for false positives (e.g. constant color cannot prove cut order;
duration multiplied by fps cannot prove decoded frame count).

Update architecture/status/handoff with exact results and limitations, and provide
one learning exercise explaining why video and audio need a shared clock. This
completes A2 only; measured performance (A3), unfamiliar real footage, actual Resolve
import and provider evaluation remain separate gates.

The existing public remote is https://github.com/Humza1423/storyroom. Fetch and
inspect it before pushing. Use a normal feature-branch push preserving history,
including prior local foundation commits not yet on GitHub. Create a reviewable PR
with changes and verification; inspect remote CI and fix relevant failures. Do not
force-push or change repository visibility. Report the branch/PR link so the creator
can actually find the updated code and README. Persist the preference to push
verified future implementation checkpoints in project working instructions.
