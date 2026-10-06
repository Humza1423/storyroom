# Product intent and decisions

This document preserves the creator's intent, not a claim that every capability
is implemented. See [STATUS](STATUS.md) for evidence and [ROADMAP](ROADMAP.md)
for delivery order. Revise decisions when results justify it; do not defend them
merely because an earlier chat chose them.

## The product

Storyroom is an AI-assisted pre-edit workspace for footage that already exists.
It helps a creator turn unfamiliar footage and a creative brief into an organized,
editable first assembly, then hand it to DaVinci Resolve for finishing.

AI should increase human creative productivity without replacing creative control.
The product is not a generic video generator, a replacement for professional
editors, or an unsolicited editing coach.

## First user and problem hypothesis

Start with an individual making short fitness or sports training montages from a
small shoot: sorting attempts, finding useful details, choosing a progression,
and handing off a first assembly. Weddings inspired the idea but are not the
initial niche. Full sports matches and synchronized multicamera shoots are out.

The hypothesis is that finding and selecting material takes enough repeated effort
to justify another tool before the editor. This is unproven. Extra imports,
analysis waiting time, organizing overhead, and a fragile export can erase the
benefit. Measure the complete workflow, not just search speed. Interviews are
deferred by request, not considered unnecessary; the saved checklist is in STATUS.

## Intended experience

1. Import footage without modifying the user's sources.
2. Describe the intended video, audience, emphasis, and optional constraints.
3. Explore a proposed story map grounded in that brief and available footage.
4. Search moments, inspect up to five candidates for a section, and choose them.
5. Create or rename sections, drag selections, trim ranges, and rearrange freely.
6. Preview, revise the brief or choices, save, and export an editable timeline.

This is a loop, not a compulsory wizard. Editors often discover the story while
assembling and revisiting footage. Planning and editing must remain interleaved.

Sections are niche-specific creative roles, not fixed generic boxes. A possible
training brief might suggest preparation, technique detail, difficult attempt,
progression, peak effort, and recovery. These are examples, not mandatory labels
or claims the model can reliably detect. Unsupported sections may remain empty.
Users can create their own sections; the same moment can serve several roles.

AI may explain why a candidate fits, with visible uncertainty. Suggestions are
separate from accepted edits. Regeneration must never overwrite manual decisions.
Manual import, organization, trim, preview, save, and export remain usable offline
without cloud AI. Cloud analysis requires explicit permission and budget checks.

## Bounded first release

- Local browser application, single local user; development targets an 8 GB Mac.
- Short SDR H.264 MP4 clips, up to 1080p; 30 files, 15 minutes, 2 GB per project.
- Managed source copies, constant-30-fps editing copies, smaller playback proxies.
- Cuts-only Resolve handoff using normalized copies, not camera-original relinking.
- Cloud AI development budget of US$50; local dispatch guardrail at US$45.
- No captions, transitions, music synchronization, full matches, multicamera sync,
  tracking/effects, autonomous coach, hosted collaboration, or full editor.

Later, beginners could finish a simple video here rather than opening an editor.
That is an expansion option, not a second MVP to build simultaneously. Broader
niches are possible only after testing that the workflow generalizes.

## Value and evidence

Semantic search and generated bins alone are not defensible differentiation.
The useful outcome is a faster, trustworthy handoff with the creator's choices
intact. Repeat use across shoots matters more than an impressive demo. Payment
and a business model remain unvalidated. Potential longer-term value could come
from reliable workflow integration and permissioned relevance feedback, but neither
is a moat today. Recheck current competitors before making market claims.

Success evidence should include import-to-assembly time, relevant results in the
first five, selected-candidate usefulness, recovery from mistakes, and successful
editor imports. A small retrieval benchmark is an engineering check, not proof
of demand. Social reactions and recruiter interest are not substitutes for usage.

## What the creator wants from development

- A genuinely useful open-source project with startup potential, plus serious
  engineering/AI learning and demonstrable co-op/job-ready skills.
- An MVP in weeks, originally estimated as two focused weeks, not a year of
  speculative infrastructure. Dates are estimates; correctness gates still apply.
- Direct, critical product judgment. Challenge assumptions, propose cuts, and
  explain tradeoffs without hype or automatic validation.
- Frequent explanations of what changed, why, where the code lives, and evidence
  it works. Give small exercises and keep the actual progress visible.
- Build in small vertical slices. Use coding agents to implement reviewable work,
  not to hide system understanding or produce unverified claims.

Application code is intended for MIT open-source release. Credentials, personal
footage, databases, and trained artifacts are not automatically public. Check each
asset's analysis, training, and redistribution rights separately. Repository
publication, footage uploads, paid analysis, and outreach require the relevant
authorization; earlier discussion is not blanket permission for all of them.
