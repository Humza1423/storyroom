# Development and operation

Start with the [README quickstart](../README.md#run-locally). This guide holds the
operational details; [START_HERE](../START_HERE.md) maps the code,
[CONTRIBUTING](../CONTRIBUTING.md) defines change/test practices, and
[STATUS](STATUS.md) records actual results and release gates.

## Dependencies and startup

Use Python 3.12, Node 22+, npm, uv 0.12.23, and system FFmpeg/ffprobe.
`uv.lock` pins Python packages and hashes, including the `dev` extra;
`package-lock.json` pins the Node dependency tree. After pulling changes, run:

```sh
.tools/uv/bin/uv sync --locked --extra dev
npm ci
.venv/bin/python scripts/dev.py
```

`--locked` refuses an out-of-date lockfile. Intentional Python dependency changes
require `.tools/uv/bin/uv lock` followed by fresh verification. The `.tools/uv`
environment keeps the installer separate from application dependencies and avoids
changing an externally managed system Python. If uv 0.12.23 is already on your
PATH, use `uv` instead. The older editable-pip install path resolves version ranges
and is not the reproducible contribution path.

The launcher checks Python/Node, dependencies, FFmpeg/ffprobe, writable storage,
and free ports. It announces readiness only after the API and UI respond. A child
process failure names the process and exits nonzero; Ctrl-C stops all three owned
processes. Closing a browser tab does not stop the worker, but stopping the launcher
does. Defaults are API port 8765 and UI port 5173; use `STORYROOM_API_PORT` and
`STORYROOM_UI_PORT` to select alternatives.

If the API disconnects, the interface keeps the open project and drafts and shows
**Reconnect**. Failed saves remain errors; retry explicitly after reconnecting.
Do not treat an unsaved draft as a persisted decision.

### Serve a built interface

Run `npm run build`, then start the following in separate terminals:

```sh
.venv/bin/python -m uvicorn server.app:app --host 127.0.0.1 --port 8765
```

```sh
.venv/bin/python -m server.worker
```

Open **http://127.0.0.1:8765**. This serves the built interface from the local API;
it is not a hosted deployment. Stop both terminals when finished. Do not run a
second worker alongside the development launcher.

## Import outcomes and recovery

Select several clips together. Invalid files do not block later valid files;
capacity, disk, and connection problems pause the remaining queue.

| Action or state | Meaning |
| --- | --- |
| Retry upload | Retries only the eligible row. An unconfirmed upload may already be saved; retry retransmits the file and the server checks its content hash to prevent duplicate registration. |
| Resume remaining files | Attempts the waiting rows after the problem is resolved. |
| Already imported | Identifies duplicate content; it does not mean preparation has finished. |
| Ready to use | The asset is prepared and available for selection. |
| Retry preparation | Reuses the registered source and queues preparation again. No new upload is needed. |
| Clear local outcomes | Clears the batch display without deleting clips or edits. |

Switching projects keeps a batch attached to its original destination. Reloading
preserves registered clips and jobs, but pending browser `File` objects do not
survive; select waiting files again. Upload progress is a state, not an estimated
byte percentage. Interrupted encoding is retryable; completed encoding stages are
not guaranteed to be reused.

## Media and backups

Sources live in `data/media/` by default. Normalized editing copies and playback
proxies are generated alongside them; saved selections reference integer ranges
on the 30 fps editing copies. Out points are exclusive: frames 30 through 89 form
the selection `[30, 90)`.

Media corrections apply when new editing copies and proxies are prepared, and
when new review videos are rendered. Existing editing copies and saved frame
ranges are not silently rewritten. Older copies may retain earlier aspect-ratio
or timing errors; evaluate the corrected pipeline by importing the original
sources into a new project, preserving the earlier project and its decisions.

Exports point to these local editing copies. Moving or deleting them breaks the
handoff. Browser sequential playback is approximate; inspect rendered media and
the actual imported editor sequence for cut precision.

This preview has no project-deletion or backup/restore interface. With the
application stopped, back up the complete `data/` directory, not just the SQLite
file. Keep credentials separately. Do not commit personal projects or sample
exports containing personal filesystem paths.

## Optional cloud AI

Manual editing works without cloud setup. Before enabling paid calls:

1. Create a paid Gemini API project/key and keep the key local.
2. Copy `.env.example` to `.env` and set `GEMINI_API_KEY`.
3. Verify model availability and prices in the provider account. Update the model
   settings and rates, then set `STORYROOM_PRICING_CONFIRMED=true`.
4. Restart Storyroom. Record each clip's source/license and cloud-analysis
   permission through its settings button.
5. Click **Analyze**, inspect the estimate, and explicitly start analysis. Use AI
   search or request a story structure after adding a creative brief.

The checked-in configuration names `gemini-3.8-flash` and `gemini-embedding-2`.
These are adapter defaults, not verified claims of model availability or quality.
Fake-provider tests cover the integration contract; real requests and evaluation
remain required. An unavailable model causes an error; there is no silent fallback.
See [model choices](MODELS.md).

The initial configured rates are $1.50/M input tokens, $9/M output tokens, and
$0.20/M text embedding tokens. These are provisional budget inputs, not a billing
quote. Check the provider's [pricing](https://ai.google.dev/gemini-api/docs/pricing)
for the selected models before confirming them.

The ledger reserves estimated cost before dispatch and stops new requests at
$45, retaining $5 of the stated $50 development budget. Ambiguous failed requests
retain their reservation. SDK retries are disabled; an explicit retry gets a new
reservation. Actual provider billing is authoritative, and calls by other
programs are outside this ledger.

Analysis sends reduced-resolution video chunks sampled at 2 fps, without audio.
It does not transcribe speech. Story generation sends the brief and textual
inventory. Analysis descriptions can omit useful visual details, making those
details difficult to retrieve. Proposed choices remain separate from accepted
selections.

## Test isolation

Use the test commands in the [README](../README.md#quality-and-next-steps).
`npm run test:e2e` generates H.264 fixtures in a unique system temporary directory,
starts its own API, worker, and frontend server, then removes its directory after
stopping its process groups. No seeded demo or development server is required.

Test ports default to 15173/18765; override with `STORYROOM_TEST_UI_PORT` and
`STORYROOM_TEST_API_PORT`. Occupied ports fail instead of reusing a server.
The harness clears provider credentials, disables pricing, and sets the budget
to zero. Backend tests also use temporary data and make no paid calls. These
checks establish application behavior, not real-provider usefulness or actual
Resolve compatibility.

## Labeling and ranking experiments

The labeling dialog records relevance judgments only for footage with recorded
training permission. Labeling itself makes no AI call. Features currently include
lexical overlap, optional semantic similarity, duration capped at 30 seconds, and
whether the description contains an uncertainty annotation. Duration does not
measure fit against a requested section length, and a missing uncertainty note
is not a calibrated confidence score.

Semantic similarity is available only when the exact query and moment embeddings
are already cached; otherwise it is zero. Run an AI search before labeling when
comparing a semantic ranker. Missing semantic features are not a judgment of clip
quality. The brief is saved with labels but is not directly encoded as a model
input.

```sh
.venv/bin/python scripts/train_ranker.py
.venv/bin/python scripts/evaluate_retrieval.py path/to/retrieval-judgments.json
```

Training refuses fewer than 30 permitted, deduplicated judgments or fewer than
three footage groups. Aim for 300–500; the minimum supports only an exploratory
exercise. Splits keep footage groups together and guard against the same source
appearing in multiple groups. Models and reports stay in `data/training/`, and
training never automatically activates a new model.

Retrieval evaluation takes a JSON array with `project_id`, `footage_group`,
`query`, and human-reviewed `relevant_moment_ids`. At least 20 queries across three
groups are required. `--semantic` makes paid embedding calls subject to the
ledger. No human benchmark results are bundled or fabricated.

For product intent and later scope, see [PRODUCT](PRODUCT.md) and
[ROADMAP](ROADMAP.md). For hands-on exercises ordered alongside development, see
[LEARNING_PATH](LEARNING_PATH.md).
