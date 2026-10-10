# Contributing to Storyroom

Start with [START_HERE.md](START_HERE.md), follow the [README](README.md) setup,
and check [current status](docs/STATUS.md) before picking a feature.

## Keep changes reviewable

Describe the observable behavior, its failure cases, and why it helps a montage
creator. Prefer one focused change at a time. Read the existing path from UI to
API to worker before introducing a new abstraction or dependency.

Preserve these boundaries:

- React handles interaction; the API validates all saved decisions.
- The backend owns durable project state and credentials.
- Slow processing belongs in persistent jobs.
- Media sources remain unchanged; edits are frame ranges and ordered references.
- AI proposals stay separate from accepted selections.
- Paid requests use the configured provider, cache, and budget ledger.

When changing stored data, provide a tested migration from an existing project.
Add ordered migrations in `server/migrations.py` using individual SQL statements.
The runner locks startup, backs up existing databases before upgrades, and commits
schema changes with version history. Never commit or use `executescript` inside a migration. When changing model output, update schemas and prompt/cache versions together.

## Verification

Use Python 3.12 and `.tools/uv/bin/uv sync --locked --extra dev`, then `npm ci`. Do not
hand-edit `uv.lock`; resolve intentional dependency changes with `.tools/uv/bin/uv lock` and
verify from a fresh environment. FFmpeg/ffprobe are system prerequisites.

Run commands in the repository root after setup:

```sh
.venv/bin/pytest -q
npm run build
npm run test:e2e
.venv/bin/ruff check server tests scripts --select E9,F63,F7,F82
```

Backend tests use temporary databases and synthetic media. They require FFmpeg
and make no paid cloud calls. The frontend build checks TypeScript and bundling.

For UI changes, also follow the README's Playwright setup and run `npm run test:e2e`.
The browser harness owns its temporary data, synthetic fixtures, and server process
groups. Do not bypass it by pointing Playwright at a personal development server. Database and media changes need tests for the affected
failure paths, not just happy-path requests.

An OTIO XML round-trip is not a DaVinci Resolve compatibility result. Provider mocks
do not establish model quality. Record those external checks separately.

## Git and review

Use a focused branch, normally prefixed `codex/`, and inspect the diff before a
commit. Keep `.env`, `data/`, model artifacts, virtual environments, and dependency
folders out of version control. Confirm rights before adding any sample footage.

A local commit is a recoverable code checkpoint. Pushing to GitHub is a separate
publication action. Do not add project exports containing personal filesystem
paths to the public sample set.

Update `docs/STATUS.md` with the behavior changed, verification actually completed,
and known limitations. Add a short learning note when a change illustrates a new
architectural concept. Keep status claims specific enough for another contributor
to reproduce.

`.github/workflows/checks.yml` runs these checks on Ubuntu with Python 3.12,
Node 22, FFmpeg and Chromium. It has no provider secrets or real footage. A checked-in
workflow is not evidence of a remote run; record the actual run separately.
