import {
  test,
  expect,
  type APIRequestContext,
  type Page,
} from "@playwright/test";
import { readFileSync } from "node:fs";
import { join } from "node:path";

const headers = { "X-Storyroom": "local" };
const generated = (index: number, name = `clip-${index}.mp4`) => ({
  name,
  mimeType: "video/mp4",
  buffer: readFileSync(
    join(process.env.STORYROOM_FIXTURES!, `clip-${index}.mp4`),
  ),
});
async function create(request: APIRequestContext, name: string) {
  const response = await request.post("/api/projects", {
    headers,
    data: { name, brief: "" },
  });
  expect(response.ok()).toBeTruthy();
  return (await response.json()).id as string;
}
async function open(page: Page, name: string) {
  await page.goto("/");
  await page.getByRole("button", { name, exact: true }).click();
  await expect(page.getByRole("heading", { name, exact: true })).toBeVisible();
}
const project = async (request: APIRequestContext, pid: string) =>
  (await request.get(`/api/projects/${pid}`)).json();

test("a delayed board save preserves footage imported while it was pending", async ({
  page,
  request,
}) => {
  const pid = await create(request, "Import during board save");
  await open(page, "Import during board save");
  let release!: () => void;
  const gate = new Promise<void>((resolve) => {
    release = resolve;
  });
  let arrived!: () => void;
  const received = new Promise<void>((resolve) => {
    arrived = resolve;
  });
  await page.route(`**/api/projects/${pid}/board`, async (route) => {
    const response = await route.fetch();
    arrived();
    await gate;
    await route.fulfill({ response });
  });
  await page
    .getByRole("button", { name: "Add story section", exact: true })
    .click();
  await page.getByLabel("Section title").fill("Saved while importing");
  await page.getByRole("button", { name: "Save section", exact: true }).click();
  await received;
  try {
    await page.locator("input[type=file]").setInputFiles([generated(0)]);
    const summary = page.getByRole("status", { name: "Footage summary" });
    await expect(summary).toHaveText(/1 (preparing|ready)/);
    await expect(
      page.getByRole("button", { name: "Import footage", exact: true }),
    ).toBeEnabled();
    // Stop subsequent polls from masking a stale-state replacement by the save.
    await page.route(`**/api/projects/${pid}`, (route) => route.abort());
    release();
    await expect(page.locator(".story-section")).toHaveCount(1);
    await expect(summary).toHaveText(/1 (preparing|ready)/);
    const saved = await project(request, pid);
    expect(saved.assets).toHaveLength(1);
    expect(saved.board[0].title).toBe("Saved while importing");
  } finally {
    release();
    await page.unrouteAll({ behavior: "wait" });
  }
});

test("mixed files keep later successes, distinguish identical names and duplicates, and survive reload", async ({
  page,
  request,
}) => {
  const pid = await create(request, "Mixed import");
  await open(page, "Mixed import");
  await expect(
    page.getByRole("status", { name: "Footage summary" }),
  ).toHaveText("No clips yet");
  await page.locator("input[type=file]").setInputFiles([
    generated(0, "same.mp4"),
    {
      name: "broken.mp4",
      mimeType: "video/mp4",
      buffer: Buffer.from("not video"),
    },
    generated(1, "same.mp4"),
  ]);
  await expect(page.locator(".import-row")).toHaveCount(3);
  await expect(page.locator(".import-row").nth(1)).toContainText(
    "Upload rejected",
  );
  await expect(page.locator(".import-row").nth(1)).toContainText(
    "Cannot read this video",
  );
  await expect(
    page.getByRole("status", { name: "Footage summary" }),
  ).toHaveText("2 ready", { timeout: 60000 });
  await expect(
    page.getByRole("status", { name: "Batch summary" }),
  ).toContainText("1 rejected");
  await expect(page.locator(".import-row").nth(0)).toContainText(
    "Ready to use",
  );
  await expect(page.locator(".import-row").nth(2)).toContainText(
    "Ready to use",
  );
  await page
    .locator("input[type=file]")
    .setInputFiles([generated(0, "renamed.mp4")]);
  await expect(page.locator(".import-row").last()).toContainText(
    "Already imported",
  );
  let saved = await project(request, pid);
  expect(saved.assets).toHaveLength(2);
  expect(saved.assets[0].name).toBe(saved.assets[1].name);
  expect(
    saved.jobs.filter((j: { kind: string }) => j.kind === "normalize"),
  ).toHaveLength(2);
  await page
    .getByRole("button", { name: "Clear outcomes", exact: true })
    .first()
    .click();
  saved = await project(request, pid);
  expect(saved.assets).toHaveLength(2);
  await page.reload();
  await expect(
    page.getByRole("status", { name: "Footage summary" }),
  ).toHaveText("2 ready");
  await expect(page.locator(".import-row")).toHaveCount(0);
  await expect(
    page.getByRole("region", { name: "Import outcomes" }),
  ).toContainText("select any unuploaded files again");
});

test("a committed upload with a lost response pauses and explicit retry deduplicates", async ({
  page,
  request,
}) => {
  const pid = await create(request, "Unconfirmed import");
  await open(page, "Unconfirmed import");
  let calls = 0;
  await page.route(`**/api/projects/${pid}/import`, async (route) => {
    calls++;
    if (calls === 2) {
      await route.fetch(); // Real registration succeeds; only the response is lost.
      await route.abort("connectionreset");
    } else await route.continue();
  });
  await page
    .locator("input[type=file]")
    .setInputFiles([generated(0), generated(1), generated(2)]);
  await expect(
    page.getByRole("status", { name: "Batch summary" }),
  ).toContainText("1 unconfirmed");
  await expect(page.locator(".import-row").nth(2)).toContainText(
    "Waiting to upload",
  );
  await expect(
    page.getByRole("button", { name: "Retry upload", exact: true }),
  ).toBeEnabled();
  expect(calls).toBe(2);
  expect((await project(request, pid)).assets).toHaveLength(2);
  await page.getByRole("button", { name: "Retry upload", exact: true }).click();
  await expect(page.locator(".import-row").nth(1)).toContainText(
    "Already imported",
  );
  expect((await project(request, pid)).assets).toHaveLength(2);
  await page
    .getByRole("button", { name: "Resume remaining files", exact: true })
    .click();
  await expect(
    page.getByRole("status", { name: "Footage summary" }),
  ).toHaveText("3 ready", { timeout: 60000 });
  expect(calls).toBe(4);
  const saved = await project(request, pid);
  expect(
    saved.jobs.filter((j: { kind: string }) => j.kind === "normalize"),
  ).toHaveLength(3);
});

for (const code of ["project_capacity", "disk_space"]) {
  test(`${code} response pauses waiting files until explicit recovery`, async ({
    page,
    request,
  }) => {
    const name = "Pause " + code;
    const pid = await create(request, name);
    await open(page, name);
    let calls = 0;
    await page.route(`**/api/projects/${pid}/import`, async (route) => {
      if (++calls === 2)
        await route.fulfill({
          status: 400,
          json: {
            detail: "Free capacity before retrying",
            code,
            scope: "batch",
            uncertain: false,
          },
        });
      else await route.continue();
    });
    await page
      .locator("input[type=file]")
      .setInputFiles([generated(0), generated(1), generated(2)]);
    await expect(
      page.getByRole("status", { name: "Batch summary" }),
    ).toContainText("Batch paused");
    await expect(
      page.getByRole("button", { name: "Retry upload", exact: true }),
    ).toBeEnabled();
    expect(calls).toBe(2);
    expect((await project(request, pid)).assets).toHaveLength(1);
    await page
      .getByRole("button", { name: "Retry upload", exact: true })
      .click();
    await expect(page.locator(".import-row").nth(1)).not.toContainText(
      "Upload rejected",
    );
    await page
      .getByRole("button", { name: "Resume remaining files", exact: true })
      .click();
    await expect(
      page.getByRole("status", { name: "Footage summary" }),
    ).toHaveText("3 ready", { timeout: 60000 });
    expect(calls).toBe(4);
  });
}

test("delayed import and refresh stay with their original project while another board is open", async ({
  page,
  request,
}) => {
  const original = await create(request, "Original destination");
  const other = await create(request, "Other destination");
  const board = [
    {
      id: "other-section",
      title: "Other board stays",
      purpose: "",
      selections: [],
    },
  ];
  expect(
    (
      await request.put(`/api/projects/${other}/board`, {
        headers,
        data: { revision: 0, sections: board },
      })
    ).ok(),
  ).toBeTruthy();
  await open(page, "Original destination");
  let release!: () => void;
  const gate = new Promise<void>((resolve) => {
    release = resolve;
  });
  let arrived!: () => void;
  const received = new Promise<void>((resolve) => {
    arrived = resolve;
  });
  const destinations: string[] = [];
  await page.route("**/api/projects/*/import", async (route) => {
    destinations.push(route.request().url());
    const response = await route.fetch();
    if (destinations.length === 1) {
      arrived();
      await gate;
    }
    await route.fulfill({ response });
  });
  await page
    .locator("input[type=file]")
    .setInputFiles([generated(0), generated(1), generated(2)]);
  await received;
  await page
    .getByRole("button", { name: "Other destination", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "Other destination", exact: true }),
  ).toBeVisible();
  await page.locator(".brief-bar textarea").fill("Keep this unsaved draft");
  await expect(page.locator(".import-row")).toHaveCount(0);
  await expect(
    page.getByRole("button", { name: "Import footage", exact: true }),
  ).toBeDisabled();
  release();
  await expect.poll(() => destinations.length).toBe(3);
  await expect(
    page.getByRole("button", { name: "Import footage", exact: true }),
  ).toBeEnabled();
  expect(
    destinations.every((url) => url.endsWith(`/projects/${original}/import`)),
  ).toBe(true);
  await expect(
    page.getByRole("status", { name: "Footage summary" }),
  ).toHaveText("No clips yet");
  await expect(page.locator(".brief-bar textarea")).toHaveValue(
    "Keep this unsaved draft",
  );
  expect((await project(request, other)).board).toEqual(board);
  expect((await project(request, other)).assets).toHaveLength(0);
  await page
    .getByRole("button", { name: "Original destination", exact: true })
    .click();
  await expect(page.locator(".import-row")).toHaveCount(3);
  await expect(
    page.getByRole("status", { name: "Footage summary" }),
  ).toHaveText("3 ready", { timeout: 60000 });
});

test("preparation retry controls after reload use job endpoint without reupload (simulated failed worker response)", async ({
  page,
  request,
}) => {
  const pid = await create(request, "Preparation recovery");
  const response = await request.post(`/api/projects/${pid}/import`, {
    headers,
    multipart: { file: generated(0) },
  });
  expect(response.ok()).toBeTruthy();
  const imported = await response.json();
  await expect
    .poll(async () => (await project(request, pid)).assets[0].status, {
      timeout: 60000,
    })
    .toBe("ready");
  let retried = false;
  let retryCalls = 0;
  let uploadCalls = 0;
  page.on("request", (r) => {
    if (r.url().endsWith("/import")) uploadCalls++;
  });
  await page.route(`**/api/projects/${pid}`, async (route) => {
    const response = await route.fetch();
    const data = await response.json();
    data.assets[0].status = retried ? "processing" : "failed";
    data.assets[0].error = retried ? null : "Synthetic preparation failure";
    data.assets[0].preparation_job = {
      id: retried ? "replacement-job" : imported.job_id,
      status: retried ? "queued" : "failed",
      progress: 0,
      message: "Synthetic stage",
    };
    await route.fulfill({ response, json: data });
  });
  await page.route(`**/api/jobs/${imported.job_id}/retry`, async (route) => {
    retryCalls++;
    retried = true;
    await route.fulfill({ json: { job_id: "replacement-job" } });
  });
  await open(page, "Preparation recovery");
  await page.reload();
  await expect(
    page.getByRole("status", { name: "Footage summary" }),
  ).toHaveText("1 failed");
  await page
    .getByRole("button", { name: "Retry preparation", exact: true })
    .click();
  await expect(
    page.getByRole("status", { name: "Footage summary" }),
  ).toHaveText("1 preparing");
  expect(retryCalls).toBe(1);
  expect(uploadCalls).toBe(0);
  expect((await project(request, pid)).assets).toHaveLength(1);
});

test("reload keeps accepted assets but does not resume waiting local Files", async ({
  page,
  request,
}) => {
  const pid = await create(request, "Reload paused import");
  await open(page, "Reload paused import");
  let calls = 0;
  await page.route(`**/api/projects/${pid}/import`, async (route) => {
    if (++calls === 2) await route.abort("connectionrefused");
    else await route.continue();
  });
  await page
    .locator("input[type=file]")
    .setInputFiles([generated(0), generated(1), generated(2)]);
  await expect(
    page.getByRole("status", { name: "Batch summary" }),
  ).toContainText("1 unconfirmed");
  await expect(page.locator(".import-row").nth(2)).toContainText(
    "Waiting to upload",
  );
  await page.unrouteAll({ behavior: "wait" });
  await page.reload();
  await expect(
    page.getByRole("status", { name: "Footage summary" }),
  ).toHaveText("1 ready", { timeout: 60000 });
  await expect(page.locator(".import-row")).toHaveCount(0);
  expect((await project(request, pid)).assets).toHaveLength(1);
  expect(calls).toBe(2);
});

test("an import refresh cannot replace a board saved after that refresh started", async ({
  page,
  request,
}) => {
  const pid = await create(request, "Edit while importing");
  await open(page, "Edit while importing");
  await page.locator(".brief-bar textarea").fill("Keep this draft too");
  let hold = false;
  let release!: () => void;
  const gate = new Promise<void>((resolve) => {
    release = resolve;
  });
  let arrived!: () => void;
  const received = new Promise<void>((resolve) => {
    arrived = resolve;
  });
  await page.route(`**/api/projects/${pid}/import`, async (route) => {
    const response = await route.fetch();
    hold = true;
    await route.fulfill({ response });
  });
  await page.route(`**/api/projects/${pid}`, async (route) => {
    const response = await route.fetch();
    if (hold) {
      arrived();
      await gate;
    }
    await route.fulfill({ response });
  });
  await page.locator("input[type=file]").setInputFiles([generated(0)]);
  await received;
  await page
    .getByRole("button", { name: "Add story section", exact: true })
    .click();
  await page.getByLabel("Section title").fill("Keep this accepted section");
  await page.getByRole("button", { name: "Save section", exact: true }).click();
  await expect(page.locator(".story-section")).toHaveCount(1);
  hold = false;
  release();
  await page.unrouteAll({ behavior: "wait" });
  await expect(
    page.getByRole("button", { name: "Import footage", exact: true }),
  ).toBeEnabled();
  await expect(
    page.getByRole("status", { name: "Footage summary" }),
  ).toHaveText("1 ready", { timeout: 60000 });
  await expect(page.locator(".story-section")).toHaveCount(1);
  await expect(page.locator(".brief-bar textarea")).toHaveValue(
    "Keep this draft too",
  );
  expect((await project(request, pid)).board[0].title).toBe(
    "Keep this accepted section",
  );
});
