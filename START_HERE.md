# Start here: build and understand Storyroom

Storyroom helps a creator turn existing footage into an editable story assembly.
Our first format is short fitness and sports training montages. The creator owns
the choices; optional AI helps find and describe possible material.

This is a local development preview. The manual workflow is implemented; real
AI quality and the DaVinci Resolve handoff are still release gates.

## See the code

Open this entire `storyroom` folder in VS Code using **File → Open Folder**.
The Explorer on the left shows the source tree. On macOS, `Cmd+P` opens a file
by name. Start with `server/models.py`, then `server/app.py`.

The repository, running app, and GitHub are different things:

- This folder contains the source code and its local Git history.
- The local app is a running program opened at `http://127.0.0.1:5173`.
- The private GitHub repository at
  [Humza1423/storyroom](https://github.com/Humza1423/storyroom) stores pushed
  commits. It is a source backup and collaboration point, not a hosted app.

Opening `index.html` directly does not start React, the API, or the worker.
Use the startup command from the [README](README.md). Existing installations
can start from a terminal in this folder with:

```sh
.venv/bin/python scripts/dev.py
```

Leave that terminal running. Stop with Ctrl-C. Closing the browser does not
stop the worker; stopping the launcher does.

## Follow one feature through the source

| File | Responsibility | Question to answer while reading |
| --- | --- | --- |
| [src/main.tsx](src/main.tsx) | Mounting and styles | Where does React start? |
| [src/App.tsx](src/App.tsx) | Workspace state and orchestration | Which action sends an HTTP request? |
| [src/types.ts](src/types.ts), [src/lib/api.ts](src/lib/api.ts) | API contracts and bounded requests | What happens on an error or timeout? |
| [src/features/](src/features/) | Library, board, and preview components | Which state comes from the parent? |
| [import controller](src/features/library/imports/controller.ts) | Per-file outcomes, pausing, explicit retry and project ownership | Why is upload acceptance different from ready media? |
| [server/imports.py](server/imports.py) | Import recovery fields and current preparation-job association | Which stage should be retried? |
| [src/style.css](src/style.css) | Layout, responsive behavior, visual styling | What changes presentation rather than saved project data? |
| [server/models.py](server/models.py) | Valid request and AI response shapes | Which malformed values are rejected automatically? |
| [server/app.py](server/app.py) | API routes, validation, media import, board updates | Which rules must hold even if the browser sends bad data? |
| [server/db.py](server/db.py) | SQLite transactions, job creation, cache, budget | Which changes must be committed together? |
| [server/migrations.py](server/migrations.py) | Locked, backed-up, atomic database upgrades | Why must schema and version commit together? |
| [scripts/e2e.py](scripts/e2e.py) | Generated browser fixtures and owned servers | What prevents a test from writing personal projects? |
| [server/worker.py](server/worker.py) | Job execution, progress, failure, cancellation | What survives a process restart? |
| [server/media.py](server/media.py) | Inspection, normalization, proxies, MP4 rendering | Which operation creates a new media file? |
| [server/exporter.py](server/exporter.py) | Cuts-only timeline and media references | Does this output contain video or instructions pointing to video? |
| [server/ai.py](server/ai.py) | Provider requests, schemas, caching, usage | What happens when a paid request times out? |
| [server/search.py](server/search.py) | Keyword matching and embedding similarity | What can search miss if an observation omitted a visual detail? |
| [tests/](tests/) | Backend and media regression checks | What failure would each assertion catch? |

Three processes run during development: the Vite frontend server, the FastAPI
server, and one background worker. The API and worker share a SQLite database
and managed media directory. This is one application with separate execution
roles. There is no need for independently deployed services at this scale.

## Current progress and next work

Read [the product intent](docs/PRODUCT.md) for the full idea, scope, and creator's
goals, and [the roadmap](docs/ROADMAP.md) for implementation order and acceptance.
Starting a new coding chat? Use [the handoff](docs/HANDOFF.md). For working between
the folder, VS Code, Codex, and GitHub, use [the workflow guide](docs/WORKFLOW.md).

Use [docs/STATUS.md](docs/STATUS.md) for implementation status, evidence, release
gates, and the ordered backlog. It distinguishes code that exists from behavior
we have verified. A passing mock-provider test does not prove AI usefulness.

Use [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for the request flow and design
choices, and [CONTRIBUTING.md](CONTRIBUTING.md) before changing the code.

## How we will work together

Each development session should include:

1. The user-visible behavior we are improving and the reason to prioritize it.
2. The files being changed and the boundary each file owns.
3. An explanation of one engineering concept, tied to the actual change.
4. Appropriate checks, with results and limitations recorded in the status log.
5. A small exercise you can do yourself and a reviewable local Git checkpoint.

For each change, try to explain its input, output, saved state, failure behavior,
and test. That builds the ability to review AI-generated code and debug it.

An effective coding-agent request contains a behavior, constraints, and evidence:

> Make clip import recover cleanly if queuing fails. The clip and preparation job
> must commit together; keep the user's source intact. Add a test that forces the
> queue insertion to fail, explain why it caught the original bug, and show the
> changed files.

Before accepting an agent's work, read the diff, run the relevant checks, and
try the feature. Ask it to explain assumptions when a test does not cover them.
Keep changes small enough to understand; measure speed or quality before claiming
an optimization.

## First lesson: a clip and its job belong together

Read [the import reliability lesson](docs/learning/01-import-transactions.md).
It explains a real failure found in this code and how a transaction fixes it.

Your exercise: run the two import tests, then locate the line that queues the job
inside the import transaction. Explain why moving it outside that transaction
could leave an asset permanently marked `processing`.

```sh
.venv/bin/pytest -q tests/test_import_atomicity.py
```

These tests use a temporary database and generated footage. They do not modify
your saved projects or call a cloud model.
