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

Current checkpoint: Gemini-first activity-search preview on
`codex/gemini-activity-search`, draft PR #6 stacked on evaluation PR #5.
Read the latest STATUS entry and [GEMINI_ACTIVITY_EVALUATION](GEMINI_ACTIVITY_EVALUATION.md)
before the historical foundation summary below. The frozen eight-video/24-query
test is complete but fails recall, precision and duration targets; do not claim
the AI completion plan passed. Next bounded task: separate requested duration
from recognition in short contexts and preserve sanitized continuation validation
reasons. Do not re-audit, integrate Qwen/ANN, or retune the frozen key.

Canonical repository is now `/Users/hamzah_ali/Documents/Codex/2026-10-02/storyroom`;
the old long path is a compatibility symlink. The demo uses port 15176/API 18767,
`data/evaluation/gemini-fresh/session`, project **Gemini fresh validation v1**,
eight clips. Old 12-clip evidence remains separately intact. Check the startup
banner for code and database identity; do not infer them from the port.

### Historical foundation handoff

The foundation, A1–A3, real-footage checks, and Resolve handoff are merged into
the public repository's `main` branch. [PR #1](https://github.com/Humza1423/storyroom/pull/1)
contains the review and CI history. Read [STATUS](STATUS.md),
[FOUNDATION_PLAN](FOUNDATION_PLAN.md), and [MEDIA_CORRECTNESS_PLAN](MEDIA_CORRECTNESS_PLAN.md)
for the checks and remaining release gates.

Next product milestone: evaluate search/retrieval quality on permissioned, unfamiliar footage in
[REAL_FOOTAGE_PLAN](REAL_FOOTAGE_PLAN.md), with Phase A1's resilient batch import now verified in
[IMPORT_PLAN](IMPORT_PLAN.md). A2 now has independent generated-media geometry,
frame-timing and audio regressions with bounded fixes. Phase A3 added bounded
processing-time/output-size diagnostics and a generated-media baseline; see
[STATUS](STATUS.md) and [PERFORMANCE_PLAN](PERFORMANCE_PLAN.md).

The four licensed sources have been downloaded, hashed, converted, and run through
the actual local Storyroom workflow. The project survived restart; search, bins,
repeated source ranges, preview, and FCP7 XML export were checked. DaVinci Resolve
21.1.1 imported the XML at 30 fps / 1920×1080; visible footage is in the 26-second,
six-cut timeline. The final silent placement has no audio lane, the repeated source
range remains distinct, and Storyroom section labels appear in clip names (not as
Resolve bins). See [STATUS](STATUS.md) for evidence and scope limits. Local media
and provenance are ignored under `data/evaluation/cavemantraining/`. No cloud
analysis or training was run. Next, measure retrieval quality on permissioned,
unfamiliar footage before expanding computer-vision infrastructure.
[LEARNING_PATH](LEARNING_PATH.md) offers the creator a small code contribution and
request-flow exercise. Do not substitute XML parsing for an editor import.

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
