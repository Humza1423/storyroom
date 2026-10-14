import { test, expect } from "@playwright/test";
import { ImportController } from "../src/features/library/imports/controller";
import {
  footageSummary,
  rowStatus,
} from "../src/features/library/imports/presentation";
import { api, ApiError } from "../src/lib/api";
import type { Asset } from "../src/types";

const files = () => [
  new File(["A"], "same.mp4"),
  new File(["B"], "same.mp4"),
  new File(["C"], "third.mp4"),
];
const accepted = (id: string) => ({
  id,
  job_id: "job-" + id,
  duplicate: false,
});
const fixtureAsset = (id: string, status = "ready"): Asset => ({
  id,
  name: "same.mp4",
  frames: 30,
  duration: 1,
  provenance: {},
  status,
  preparation_job: {
    id: "job-" + id,
    status: status === "ready" ? "done" : "failed",
    progress: 0,
    message: "Fixture",
  },
});
const rig = (
  request: (url: string, method?: string, body?: unknown) => Promise<unknown>,
  refresh: (pid: string) => Promise<Asset[]> = async () => [],
) => new ImportController({ request: request as typeof api, refresh });
function deferred() {
  let resolve!: () => void;
  const promise = new Promise<void>((r) => {
    resolve = r;
  });
  return { promise, resolve };
}

test("file failures continue, rows have stable IDs, accepted files are released", async () => {
  let count = 0;
  const controller = rig(async () => {
    if (++count === 2)
      throw new ApiError("Bad file", 400, {
        code: "file_invalid",
        scope: "file",
        uncertain: false,
      });
    return accepted(String(count));
  });
  await controller.start("p", "Project", files());
  const batch = controller.getSnapshot().batches[0];
  expect(batch.rows.map((r) => r.state)).toEqual([
    "accepted",
    "rejected",
    "accepted",
  ]);
  expect(new Set(batch.rows.map((r) => r.id)).size).toBe(3);
  expect(batch.rows.every((r) => !r.file)).toBe(true);
  expect(batch.paused).toBe(false);
  controller.clear(batch.id);
  expect(controller.getSnapshot().batches).toEqual([]);
  expect(count).toBe(3); // Clearing is local; it never sends a delete.
});

for (const error of [
  new ApiError("Capacity", 400, {
    code: "project_capacity",
    scope: "batch",
    uncertain: false,
  }),
  new ApiError("Disk", 400, {
    code: "disk_space",
    scope: "batch",
    uncertain: false,
  }),
  new ApiError("Timed out", 0, {
    code: "timeout",
    scope: "batch",
    uncertain: true,
  }),
  new ApiError("Unknown code", 400, { code: "unexpected", scope: "file" }),
]) {
  test(`${error.message} pauses and explicit retry never reuploads accepted rows`, async () => {
    let attempts = 0;
    const names: string[] = [];
    const controller = rig(async (_url, _method, body) => {
      names.push(await ((body as FormData).get("file") as File).text());
      if (++attempts === 2) throw error;
      return accepted(String(attempts));
    });
    await controller.start("p", "Project", files());
    let batch = controller.getSnapshot().batches[0];
    expect(names).toEqual(["A", "B"]);
    expect(batch.rows[2].state).toBe("waiting");
    expect(batch.rows[1].file).toBeDefined();
    expect(batch.paused).toBe(true);
    await controller.retryUpload(batch.id, batch.rows[1].id);
    expect(names).toEqual(["A", "B", "B"]);
    await controller.resume(batch.id);
    batch = controller.getSnapshot().batches[0];
    expect(names).toEqual(["A", "B", "B", "C"]);
    expect(batch.rows.every((r) => r.state === "accepted" && !r.file)).toBe(
      true,
    );
    expect(batch.paused).toBe(false);
  });
}

test("unconfirmed uploads are not reconciled by matching filenames", async () => {
  const controller = rig(
    async () => {
      throw new ApiError("Lost response", 0);
    },
    async () => [fixtureAsset("existing")],
  );
  await controller.start("p", "Project", [files()[0]]);
  const row = controller.getSnapshot().batches[0].rows[0];
  expect(row.state).toBe("uncertain");
  expect(row.assetId).toBeUndefined();
  expect(row.file).toBeDefined();
});

test("a failed refresh keeps accepted IDs, releases that File and pauses waiting requests", async () => {
  const controller = rig(
    async () => accepted("saved"),
    async () => {
      throw new Error("offline");
    },
  );
  await controller.start("p", "Project", files());
  const batch = controller.getSnapshot().batches[0];
  expect(batch.paused).toBe(true);
  expect(batch.rows.map((r) => r.state)).toEqual([
    "accepted",
    "waiting",
    "waiting",
  ]);
  expect(batch.rows[0].assetId).toBe("saved");
  expect(batch.rows[0].file).toBeUndefined();
});

test("overlap is refused and disposal prevents another dispatch", async () => {
  const gate = deferred();
  const urls: string[] = [];
  const controller = rig(async (url) => {
    urls.push(url);
    await gate.promise;
    return accepted("saved");
  });
  const running = controller.start("original", "Original", files());
  await controller.start("other", "Other", files());
  expect(controller.getSnapshot().batches).toHaveLength(1);
  controller.dispose();
  gate.resolve();
  await running;
  expect(urls).toEqual(["/projects/original/import"]);
  expect(controller.getSnapshot().batches).toEqual([]);
});

test("preparation retries use the current job and do not upload", async () => {
  const asset = fixtureAsset("a", "failed");
  const urls: string[] = [];
  const controller = rig(
    async (url) => {
      urls.push(url);
      return { job_id: "replacement" };
    },
    async () => [asset],
  );
  await controller.retryPreparation("p", "a");
  expect(urls).toEqual(["/jobs/job-a/retry"]);
  asset.preparation_job!.status = "running";
  await controller.retryPreparation("p", "a");
  expect(urls).toHaveLength(1);
});

test("summary derives unique asset states and duplicate does not mean ready", () => {
  const ready = fixtureAsset("a");
  const failed = fixtureAsset("b", "failed");
  const preparing = {
    ...fixtureAsset("c", "processing"),
    preparation_job: null,
  };
  expect(footageSummary([])).toBe("No clips yet");
  expect(
    footageSummary([ready, failed, preparing, fixtureAsset("d", "new-state")]),
  ).toBe("1 ready · 1 preparing · 2 failed");
  expect(
    footageSummary([
      { ...fixtureAsset("d", "new-state"), preparation_job: null },
    ]),
  ).toBe("1 unknown");
  expect(
    rowStatus(
      {
        id: "row",
        name: "same.mp4",
        state: "accepted",
        duplicate: true,
        assetId: "b",
      },
      [failed],
    ),
  ).toContain("failed");
});

test("API timeout carries uncertainty rather than a definite file rejection", async () => {
  const originalFetch = globalThis.fetch;
  const originalTimer = globalThis.setTimeout;
  try {
    globalThis.setTimeout = ((fn: () => void) =>
      originalTimer(fn, 0)) as typeof setTimeout;
    globalThis.fetch = (_url, init) =>
      new Promise((_resolve, reject) => {
        init!.signal!.addEventListener(
          "abort",
          () => reject(new Error("aborted")),
          { once: true },
        );
      });
    await expect(
      api("/projects/p/import", "POST", new FormData()),
    ).rejects.toMatchObject({
      code: "timeout",
      scope: "batch",
      uncertain: true,
      status: 0,
    });
  } finally {
    globalThis.fetch = originalFetch;
    globalThis.setTimeout = originalTimer;
  }
});
