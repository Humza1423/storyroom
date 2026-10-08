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

## Immediate implementation entry point

For the full foundation task, follow [FOUNDATION_PLAN](FOUNDATION_PLAN.md). Its
five checkpoints have concrete completion checks and a prompt for the executing
session. [FOOTAGE_TEST_SET](FOOTAGE_TEST_SET.md) lists researched real footage for
the next manual handoff test; it has not been downloaded or evaluated yet.

Unless STATUS or the user sets a newer priority, isolate the browser tests before
the frontend refactor. Inspect `playwright.config.ts`, `e2e/workspace.spec.ts`,
`scripts/dev.py`, and `server/config.py`. Design a dedicated test data directory,
generated fixtures, controlled server lifecycle, and cleanup restricted to that
test directory. Preserve the normal development startup path.

Acceptance: run the browser suite from a clean test state, repeat it successfully,
and prove the existing user database/media were not modified. No paid requests.
This is the next task, not a claim it has already been implemented.

## Verification and handoff discipline

For backend changes run `.venv/bin/pytest -q`; for frontend changes run
`npm run build` plus the relevant browser checks. See CONTRIBUTING before running
the current non-isolated browser suite. Record the date and exact checks actually
run. Existing test counts are historical evidence, not a new session's result.

Explain purpose → code boundary → engineering concept → evidence. End with changed
files, limitations, an exercise, and the next step. Update STATUS after milestones;
change PRODUCT for a product decision, ROADMAP for a delivery change, ARCHITECTURE
for a structural change, and README for setup changes. Keep AGENTS short.

Suggested fresh-session prompt:

> Read AGENTS.md and docs/HANDOFF.md and follow the linked project context. Confirm
> the current state before editing. Continue the next unfinished milestone in
> docs/STATUS.md with a small tested change. Explain what you are changing and why
> as you work, show me the code, and update the handoff evidence. Do not make paid
> calls, upload footage, or publish externally without the relevant authorization.
