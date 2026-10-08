# Storyroom

A local, open-source footage-to-story workspace. Import short training clips, build an editable story map, preview a first assembly, and export a cuts-only timeline for DaVinci Resolve.

**Status: working development preview, not a validated production release.** Manual operation is independent of AI. Real Gemini quality and a real Resolve import must be verified separately. Generated demo patterns are technical fixtures, not sports footage or ML training evidence.

New to the code? Start with [the source map and learning guide](START_HERE.md).
Track progress in [the release checklist](docs/STATUS.md) and read
[contribution guidance](CONTRIBUTING.md) before making changes.

Project context: [product vision and constraints](docs/PRODUCT.md),
[delivery roadmap](docs/ROADMAP.md), [new-session handoff](docs/HANDOFF.md), and
[folder/Codex/GitHub workflow](docs/WORKFLOW.md).

## Run on macOS

Supported user platform: macOS. Requirements: Python 3.12, Node 22+, npm,
uv 0.12.23, FFmpeg/ffprobe. Ubuntu CI is automation coverage, not a claim of
validated end-user Linux or Windows support. DaVinci Resolve is needed for the external timeline import check.

```sh
brew install ffmpeg
python3.12 -m venv .tools/uv
.tools/uv/bin/pip install uv==0.12.23
.tools/uv/bin/uv sync --locked --extra dev
npm ci
.venv/bin/python scripts/dev.py
```

Open http://127.0.0.1:5173 and create a project. No `.env`, provider key, or demo
is required. For the optional generated technical demo, stop the app, run
`.venv/bin/python scripts/demo.py`, then restart and choose **First assembly ·
technical demo**. Do not run the seeder alongside the worker. Ctrl-C in the launch terminal stops the API, worker, and browser development server.
The launcher checks Python/Node, dependencies, FFmpeg/ffprobe, writable storage and
free ports. It announces readiness only after API and UI respond; a child failure
names that process and exits nonzero. Set `STORYROOM_API_PORT` and
`STORYROOM_UI_PORT` together as needed; defaults remain 8765/5173.
If the API disconnects, the UI keeps your open project and drafts and shows a
Reconnect button. Failed saves are shown as errors; retry explicitly after reconnecting.

`uv.lock` pins Python packages and hashes, including the `dev` extra. Use
`.tools/uv/bin/uv sync --locked --extra dev` after pulling changes; it refuses an out-of-date
lockfile. `npm ci` uses `package-lock.json`. Dependency changes require an intentional
`.tools/uv/bin/uv lock` update and fresh checks. FFmpeg remains a separately installed system tool.
The previous `python3.12 -m venv .venv` and `.venv/bin/pip install -e '.[dev]'`
path remains valid but resolves ranges; it is not the reproducible contribution path.
The `.tools/uv` environment keeps the installer separate from app dependencies
and avoids modifying an externally managed system Python. If uv 0.12.23 is already
on your PATH, use `uv` in place of `.tools/uv/bin/uv`.

For a production UI build: run `npm run build`, then run `.venv/bin/python -m uvicorn server.app:app --host 127.0.0.1 --port 8765` and `.venv/bin/python -m server.worker` in separate terminals. Open http://127.0.0.1:8765.

## First exercise: make an assembly without AI

1. Open the generated demo. Play a source moment and add it to a section.
2. Select the clip in the story map. Change its in/out frames; 30 frames equals one second.
3. Reorder it using the drag handle or arrow controls. Add your own section and purpose.
4. Reload the browser. Your saved decisions should remain.
5. Render a preview, then export Resolve XML from Processing & exports.
6. Import the XML in Resolve. Verify clip order, boundaries, audio, and references. **This external check is required before calling the release complete.**

The UI's native sequential playback is a quick assembly preview, not a frame-accurate editing monitor. The rendered MP4 and exported timeline are the outputs to inspect for precise boundaries.

## Import recovery

Select several clips together. Each file has its own outcome: invalid files do not
block later valid files; capacity, disk and connection problems pause the remaining
queue. **Retry upload** retries only that eligible row; **Resume remaining files**
attempts the waiting rows. An unconfirmed upload may already be saved; its explicit
retry checks content hashes to avoid duplicate assets. It still retransmits the file.

**Already imported** identifies duplicate content, not readiness. Wait for **Ready
to use** before selecting it. If preparation fails, **Retry preparation** reuses the
stored source. Switching projects keeps a batch attached to its original destination.
Reload keeps registered clips/jobs, but waiting files must be selected again. Clearing
local outcomes never deletes clips or edits. Upload progress is a state, not an
estimated byte percentage.

## Media limits and storage

- Up to 30 files, 15 minutes total source duration, and 2 GB total source bytes per project.
- H.264 SDR MP4 up to 1080p, landscape or portrait. No HDR, 10-bit, camera RAW, or intentional speed ramps yet.
- Sources are copied into `data/media/` and never edited. Editing copies use constant 30 fps; proxies are smaller playback files.
- Resolve exports reference the local normalized editing copies, **not the original camera files**. Do not move/delete those copies after export. Camera-original relinking is not implemented.
- MP4 previews use a 1280×720 canvas with letterboxing/pillarboxing. Finishing, cropping, and music belong in the professional editor.
- Database, media, exports, credentials, and generated training artifacts are excluded from Git.
- This development preview has no project deletion interface. Back up the complete `data/` directory with the application stopped.

## Enable cloud AI

Manual editing works with no account or API key. To enable AI:

1. Create a paid Gemini API project/key. Do not paste keys into chat or commit them.
2. Copy `.env.example` to `.env` and set `GEMINI_API_KEY` locally.
3. Confirm model availability and prices in your provider account. Update rates, then set `STORYROOM_PRICING_CONFIRMED=true`.
4. Restart the application. Record the source/license and cloud-analysis permission for each clip using its settings button.
5. Click Analyze to inspect the estimate, then explicitly start analysis. Search with AI or request a story structure after adding a creative brief.

The default adapter targets `gemini-3.8-flash` and `gemini-embedding-2`. SDK construction is tested; availability, actual output quality, and real costs are **not verified until a real credentialed call succeeds**. An unavailable model produces an error; the application never silently switches models.

The initial rate configuration is conservative, not a billing quote: $1.50/M input tokens, $9/M output tokens, and $0.20/M text embedding tokens. Check https://ai.google.dev/gemini-api/docs/pricing before confirming it.

The local ledger stops new requests at $45, reserving $5 of the stated $50 development budget. Ambiguous failed requests retain their reservation. SDK retries are disabled; a user-requested retry receives a new reservation. Actual provider billing is authoritative, and spending by other programs is outside this ledger.

Analysis sends reduced-resolution, 2 fps video chunks without audio. It does not currently transcribe speech. Story generation sends the brief and textual inventory. AI results are uncertain suggestions; accepted edits are separate. No invisible auto-editing occurs.

## Test

```sh
.venv/bin/pytest -q
npm run build
npx playwright install chromium
npm run test:e2e
.venv/bin/ruff check server tests scripts --select E9,F63,F7,F82
```

Run `npm run test:e2e`. The harness generates three H.264 clips in a unique
system temporary directory, starts its own API/worker/Vite stack, and removes only
that directory after stopping its process groups. No demo or development server is
needed. Test defaults are ports 15173/18765; override with
`STORYROOM_TEST_UI_PORT`/`STORYROOM_TEST_API_PORT`. Occupied ports fail rather than
reuse a server. Provider credentials are emptied, pricing disabled, and budget zero.
Backend tests also use temporary directories and make no paid calls.

## Learning and ML work

- [Architecture and engineering walkthrough](docs/ARCHITECTURE.md)
- [Model choices and comparison strategy](docs/MODELS.md)
- [Release checklist and remaining verification](docs/STATUS.md)

The labeling dialog records relevance judgments only for footage with recorded training permission. It does not call AI. The initial feature set is deliberately small: lexical overlap, optional semantic similarity, duration capped at 30 seconds, and whether the observation expresses uncertainty. Duration is not yet a measure of fit against a requested section length. Semantic similarity is recorded only when the exact query and moment embeddings are already cached; otherwise it is zero. Run an AI search before labeling when comparing a semantic ranker. Do not confuse unavailable semantic features with an assessment of clip quality.

```sh
.venv/bin/python scripts/train_ranker.py
.venv/bin/python scripts/evaluate_retrieval.py path/to/retrieval-judgments.json
```

Training refuses fewer than 30 permitted, deduplicated judgments or fewer than three footage groups. Aim for 300–500 judgments; the minimum is only for an exploratory exercise. Held-out splits are by footage group. The portable model and report remain in `data/training/`; training never automatically activates a new model.

Evaluation input is a JSON array with `project_id`, `footage_group`, `query`, and human-reviewed `relevant_moment_ids`. At least 20 queries and three groups are required. `--semantic` makes paid embedding calls subject to the ledger. No human benchmark results are bundled or fabricated.

## License

Application code: MIT. Dependency, model, and media licenses are separate; see [third-party notes](docs/THIRD_PARTY.md). Your credentials and footage are not part of the open-source application. Publication has not been performed automatically.
