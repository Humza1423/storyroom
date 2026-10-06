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

Requirements: Python 3.12+, Node 22+, npm, FFmpeg/ffprobe. DaVinci Resolve is needed for the external timeline import check.

```sh
brew install ffmpeg
python3 -m venv .venv
.venv/bin/pip install -e '.[dev]'
npm ci
.venv/bin/python scripts/demo.py
.venv/bin/python scripts/dev.py
```

Open http://127.0.0.1:5173. Choose **First assembly · technical demo** in the sidebar, or create your own project. Run the demo seeder before the worker, not alongside it. Ctrl-C in the launch terminal stops the API, worker, and browser development server.

For a production UI build: run `npm run build`, then run `.venv/bin/python -m uvicorn server.app:app --host 127.0.0.1 --port 8765` and `.venv/bin/python -m server.worker` in separate terminals. Open http://127.0.0.1:8765.

## First exercise: make an assembly without AI

1. Open the generated demo. Play a source moment and add it to a section.
2. Select the clip in the story map. Change its in/out frames; 30 frames equals one second.
3. Reorder it using the drag handle or arrow controls. Add your own section and purpose.
4. Reload the browser. Your saved decisions should remain.
5. Render a preview, then export Resolve XML from Processing & exports.
6. Import the XML in Resolve. Verify clip order, boundaries, audio, and references. **This external check is required before calling the release complete.**

The UI's native sequential playback is a quick assembly preview, not a frame-accurate editing monitor. The rendered MP4 and exported timeline are the outputs to inspect for precise boundaries.

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
```

For browser tests, start the app, then generate its technical fixture and run:

```sh
mkdir -p data/fixtures
ffmpeg -y -f lavfi -i testsrc2=size=320x180:rate=30:duration=2 -c:v libx264 -pix_fmt yuv420p data/fixtures/browser-test.mp4
npm run test:e2e
```

Browser tests create clearly named test projects in the current local database. Backend tests use isolated temporary directories and make no paid calls.

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
