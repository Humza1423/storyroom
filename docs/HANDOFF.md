# Resume work without the original chat

This is a navigation and session-entry guide, not a duplicate status log.

## Read in this order

1. [AGENTS](../AGENTS.md): working rules and the creator's learning preferences.
2. [PRODUCT](PRODUCT.md): idea, first user, scope, assumptions, and future options.
3. [STATUS](STATUS.md): what exists, actual checks, limitations, and next tasks.
4. [ROADMAP](ROADMAP.md): implementation sequence and acceptance gates.
5. [ARCHITECTURE](ARCHITECTURE.md), then the source for the task you are doing.

[README](../README.md) owns installation and commands. [START_HERE](../START_HERE.md)
owns the code map. [WORKFLOW](WORKFLOW.md) explains folders, Codex, Git, and GitHub.
[CONTRIBUTING](../CONTRIBUTING.md) owns change/test practices. [MODELS](MODELS.md)
and [THIRD_PARTY](THIRD_PARTY.md) cover model experiments and licensing boundaries.

## Before editing

- Confirm the working directory is the dedicated `storyroom` repository, not its
  parent workspace or the user's home-directory Git repository.
- Read `git status --short --branch`, `git log -5 --oneline`, and `git remote -v`.
  Preserve unrelated changes; do not assume a remote exists or contains local work.
- Read STATUS, then inspect the relevant code. If documentation and code disagree,
  investigate and correct the record rather than assuming the more optimistic claim.
- Check existing processes before launching another API or worker. Do not run the
  demo seeder alongside the worker. Never print `.env` or credentials into chat.

## Next entry point

The foundation history and A1/A2 work are on `codex/media-correctness`, pushed to
the existing public repository under [PR #1](https://github.com/Humza1423/storyroom/pull/1).
Read [STATUS](STATUS.md), [FOUNDATION_PLAN](FOUNDATION_PLAN.md), and
[MEDIA_CORRECTNESS_PLAN](MEDIA_CORRECTNESS_PLAN.md) for exact local/remote checks
and outstanding gates. Do not infer that `main` contains this work before merge.

Next product milestone: the manual real-footage exercise in
[REAL_FOOTAGE_PLAN](REAL_FOOTAGE_PLAN.md), with Phase A1's resilient batch import now verified in
[IMPORT_PLAN](IMPORT_PLAN.md). A2 now has independent generated-media geometry,
frame-timing and audio regressions with bounded fixes. The next coding task is
Phase A3: measure performance before optimizing, using the read-only-reviewed
[PERFORMANCE_PLAN](PERFORMANCE_PLAN.md). [LEARNING_PATH](LEARNING_PATH.md) offers the creator a small code contribution
and request-flow exercise. The source list is in
[FOOTAGE_TEST_SET](FOOTAGE_TEST_SET.md). No listed footage has been downloaded or
sent to a provider. Use its rights/provenance procedure, then prove import → saved
three-clip montage → rendered review → actual Resolve import. Ask for the relevant
external action authorization when needed. Do not substitute an XML round-trip for
an editor import, or fake-provider tests for real model quality.

For further foundation changes, browser tests are now self-contained:
`npm run test:e2e` owns a fresh temporary root, fixtures and process groups. Never
run Playwright directly against personal development data. Existing databases stay
at schema version 1; future changes go through `server/migrations.py` with backup
and rollback tests. `main.tsx` mounts the UI; `App.tsx` owns orchestration and drafts.

## Verification and handoff discipline

For backend changes run `.venv/bin/pytest -q`; for frontend changes run
`npm run build` plus the relevant browser checks. See CONTRIBUTING for the locked setup and isolated browser harness. Record the date and exact checks actually
run. Existing test counts are historical evidence, not a new session's result.

Explain purpose → code boundary → engineering concept → evidence. End with changed
files, limitations, an exercise, and the next step. Update STATUS after milestones;
change PRODUCT for a product decision, ROADMAP for a delivery change, ARCHITECTURE
for a structural change, and README for setup changes. Keep AGENTS short.

Suggested fresh-session prompt:

> Read AGENTS.md and docs/HANDOFF.md and follow the linked project context. Confirm
> the current state before editing. Continue the next unfinished milestone in
> docs/STATUS.md with a small tested change. Explain what you are changing and why
> as you work, show me the code, and update the handoff evidence. Plan before coding
> and use parallel agents only when independent work justifies the overhead. Push verified checkpoints to the existing
> feature branch and update its PR as authorized in AGENTS. Do not merge, make paid
> calls, upload footage, or change visibility without the relevant authorization.
