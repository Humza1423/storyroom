# Lesson 1: keep a clip and its processing job together

## The real bug

Import previously committed a new asset with `status='processing'`, closed that
database transaction, and then opened another transaction to enqueue normalization.
If the queue write failed or the process stopped between those transactions,
the asset existed without any work for the worker to perform. The UI could keep
showing `processing`, and importing the same file again would hit duplicate detection.

This is a partial-success failure: each individual statement can be correct while
their ordering still allows an incorrect system state.

## The invariant

An invariant is a rule that must remain true across operations:

> Every newly registered, processing asset has a normalization job when the import commits.

The updated `import_file()` in [server/app.py](../../server/app.py) inserts the asset
and calls `enqueue_in_transaction()` using the same database connection:

```python
with db.connect() as c:
    c.execute("BEGIN IMMEDIATE")
    # Validate project limits, store the source copy, and insert the asset.
    job = db.enqueue_in_transaction(c, pid, "normalize", {"asset_id": ident})
```

This excerpt is abbreviated; read the complete function for the checks and file work.

[db.connect()](../../server/db.py) commits on successful exit and rolls back if an
exception escapes. If the job insert fails, the asset insert rolls back too. Other
database connections cannot see a committed asset without its committed job.

`enqueue()` is still the convenient entry point for independent jobs. It opens a
transaction and delegates to `enqueue_in_transaction()`. The latter never commits
its caller's work. Its active-transaction check helps prevent accidental misuse.

## Why we share the connection

A database transaction belongs to its connection. Calling the ordinary `enqueue()`
inside import would open another connection, which cannot join the first transaction
and may wait on its write lock. Passing the existing connection makes the boundary
explicit and keeps related writes together.

`BEGIN IMMEDIATE` acquires SQLite's write transaction early. That also protects the
import's duplicate and project-limit checks against competing writers. The tradeoff
is that the current implementation holds the write transaction while copying media.
For larger workloads, measure this delay and design a staged-file registration flow.

## What the test proves

[tests/test_import_atomicity.py](../../tests/test_import_atomicity.py) installs a
temporary SQLite trigger that rejects job inserts. It sends a real import request
using generated footage and checks that:

1. No asset or job survives the failed registration.
2. The request's staging file and managed copy are removed.
3. The user's source file is unchanged.
4. Removing the simulated failure allows re-import and successful normalization.

Another test uploads identical bytes under two names before processing begins.
It verifies there is one asset, one job, and an intact source copy.

This is failure injection: we deliberately cause a dependency failure and check
the behavior we want users to experience. We use real SQLite so the test exercises
rollback, rather than assuming a mocked database implements it correctly.

## The remaining boundary

The database and filesystem are separate storage systems. A transaction does not
automatically undo a file copy. The import handler cleans up its new files on handled
failures, but a power loss or hard process kill can skip that cleanup. An unreferenced
media directory can remain. A future recovery operation should reconcile filesystem
state against asset IDs; do not claim this change solves all crash recovery.

This pattern is relevant to many applications: saving a document and scheduling its
indexing, recording an upload and generating thumbnails, or accepting a report request
and queuing its export.

## Try it yourself

From the repository terminal, run:

```sh
.venv/bin/pytest -q tests/test_import_atomicity.py
```

Then explain:

- Where does the commit happen? Where does the rollback happen?
- Why would two separate connections weaken the guarantee?
- Why is the upload hash different from the asset's random ID?
- Which failure does this test simulate, and which crash does it not simulate?

You understand the change when you can predict the saved state at each failure
point and point to the test that supports your prediction.
