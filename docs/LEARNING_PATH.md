# Learn Storyroom by owning a small change

The creator has shaped the product and constraints; most code so far was implemented
by agents. Engineering confidence now needs direct practice. Completion speed and
learning speed are different: reserve 20–30 minutes of each milestone for a small
change the creator can explain, implement, and verify.

These sessions are ordered to match delivery: import flow now, a small UI/test
change alongside batch imports, media timing next, and retrieval evaluation once
real footage is available. They are optional practice, not prerequisites that stop
implementation. If a feature is already implemented, trace it and add a regression
test rather than recreating it. No exercise is reserved until you choose to own it.

## Session one: trace an import

Read only these places initially, following an actual action:

1. src/App.tsx: the hidden file input captures the destination;
   src/features/library/imports/controller.ts builds FormData and dispatches the batch.
2. src/lib/api.ts: sends the request to /api/projects/{id}/import.
3. server/app.py: import_file validates, hashes, copies, and registers the asset/job.
4. server/db.py: enqueue_in_transaction joins the caller's database transaction.
5. server/worker.py: perform's normalize branch claims the media operation result.
6. server/media.py: normalize creates editing media, proxy, and thumbnail.
7. The frontend's project refresh reads the asset's new ready state.

The source clip is media. A selected clip on the board is a reference plus frame
boundaries. Duplicating a placement does not duplicate the source file. SQLite
preserves decisions across browser restarts; React state handles current interaction.

Before asking for answers, write five sentences explaining: what the browser sends;
what the API stores; why the API returns before encoding finishes; how the UI learns
the result; and what survives closing the browser. Missing an answer identifies the
next file to study, not a reason to read the entire repository.

## Session two: your first feature

The A1 implementation now includes the summary helper in
`src/features/library/imports/presentation.ts` and tests in
`e2e/import-controller.spec.ts`. No exercise was reserved, so the whole feature was
implemented. Follow along by predicting the helper's output for an unknown asset
state, then add a small regression case for a cancelled preparation job. You can
still use the design exercise below to explain or revise the existing behavior.

Own a small footage summary near the library title: for example,
"3 ready · 1 preparing · 1 failed". Current persisted asset status values include
ready, processing, and failed; map processing to user-facing "preparing".

Define the rule first: zero counts may be omitted; an empty library says "No clips
yet"; failed assets remain visible. The summary comes from the current project's
assets, not from a second separately updated counter. Decide how unexpected states
are handled rather than pretending they are ready.

Start in src/types.ts and the library heading in src/App.tsx. Implement a small pure
summary helper and render its result. Ask Codex for a hint or review if stuck, then
make the edit yourself. Inspect inputs representing ready/processing/failed cases,
run the build, and check the displayed behavior in a later app session. Do not add
a new test framework just for this helper; use the existing browser test path when
the import feature integrates it. Codex can handle the batch import mechanics while
you own this contribution if responsibilities are agreed at task start.

Be able to explain why deriving counts from assets avoids stale duplicate state.

## Session three: verify a claim independently

Predict the duration of a selection with in-frame 5 and exclusive out-frame 45 at
30 fps before running it. Then locate where rendering translates frames to seconds.
Explain why a variable-rate input is normalized before those boundaries are applied.
Compare a measured output with the expected value; do not accept a screenshot as
evidence of an exact frame count.

## Session four: own the evaluation target

When the licensed real clips are prepared, watch them before running AI. Write five
search queries, useful source/time ranges, and at least one query with no supporting
clip. Record why a candidate is relevant. Later compare actual retrieval with your
judgments and classify a miss: not described, not retrieved, ranked poorly, or hard
to use in the UI. This is a substantive AI engineering contribution.

## Working agreement for learning tasks

- Start with a concrete behavior and a prediction about what will happen.
- Ask the agent to explain the current flow in a few sentences, then point to files.
- For an explicitly creator-owned exercise, offer hints/review before giving the full
  solution. Continue independent work rather than overwriting the creator's changes.
- Review one focused diff. Explain the input, output, saved state, and failure path.
- Keep a short note with behavior changed, check performed, result, and one mistake
  or surprise. A verified explanation is more useful than a large count of commits.
- If delivery is urgent, explicitly delegate the exercise too; this is a learning
  preference, not a mandatory approval gate on ordinary implementation.

Useful request: "Give me one hint for the summary helper. Do not write the function
yet. Review my code after I finish and ask me to explain how it handles empty input."
