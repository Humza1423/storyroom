import { test, expect } from "@playwright/test";

test("visual search explains missing permission before a search request", async ({
  page,
}) => {
  await page.route("**/api/status", async (route) => {
    const response = await route.fetch();
    await route.fulfill({
      response,
      json: {
        ...(await response.json()),
        visual_ai_ready: true,
        embedding_tier: "unpaid",
        unpaid_terms_acknowledged: true,
      },
    });
  });
  await page.goto("/");
  await page.getByRole("button", { name: "New project", exact: true }).click();
  await page.getByLabel("Project name").fill("Unindexed visual project");
  await page.getByRole("button", { name: "Create project" }).click();
  await page
    .locator("input[type=file]")
    .setInputFiles(`${process.env.STORYROOM_FIXTURES}/clip-0.mp4`);
  await expect(page.locator(".moment-card")).toHaveCount(1, {
    timeout: 60000,
  });
  await page.getByLabel("Search mode").selectOption("visual");
  await page.getByLabel("Search footage").fill("jumping jacks");
  await expect(
    page.getByRole("button", { name: "Search", exact: true }),
  ).toBeDisabled();
  await expect(
    page.getByText(/No clips are approved for Visual AI yet/),
  ).toBeVisible();
  await page.getByLabel("Search footage").press("Enter");
  await expect(
    page.getByText(/Index prepared clips for visual search first/),
  ).toHaveCount(0);
});

test("visual candidates can be previewed, selected and independently trimmed", async ({
  page,
  request,
}) => {
  await page.route("**/api/status", async (route) => {
    const response = await route.fetch();
    const status = await response.json();
    await route.fulfill({
      response,
      json: {
        ...status,
        visual_ai_ready: true,
        embedding_tier: "unpaid",
        embedding_model: "gemini-embedding-2",
        unpaid_terms_acknowledged: true,
      },
    });
  });
  await page.goto("/");
  await page.getByRole("button", { name: "New project", exact: true }).click();
  const name = "Visual search browser test " + Date.now();
  await page.getByLabel("Project name").fill(name);
  await page.getByRole("button", { name: "Create project" }).click();
  await page
    .locator("input[type=file]")
    .setInputFiles(`${process.env.STORYROOM_FIXTURES}/clip-0.mp4`);
  await expect(page.locator(".moment-card")).toHaveCount(1, {
    timeout: 60000,
  });

  const permissions = page.getByRole("button", {
    name: /Permissions for clip-0\.mp4/,
  });
  await permissions.click();
  await page
    .getByLabel("source", { exact: true })
    .fill("Generated browser fixture");
  await page.getByLabel("author", { exact: true }).fill("Storyroom tests");
  await page
    .getByLabel("license", { exact: true })
    .fill("Test fixture; no external media");
  await page
    .getByLabel("I have permission to send this footage for cloud analysis")
    .check();
  await page.getByRole("button", { name: "Save permissions" }).click();

  await page.getByRole("button", { name: "Add story section" }).click();
  await page.getByLabel("Section title").fill("Technique");
  await page.getByLabel("What should it contribute?").fill("Show the exercise");
  await page.getByRole("button", { name: "Save section", exact: true }).click();

  await page.route("**/api/projects/*/visual-index-estimate", (route) =>
    route.fulfill({
      json: {
        estimated_usd: 0,
        reserved_usd: 0.00474,
        segment_count: 1,
        missing_segment_count: 1,
        frame_count: 6,
        indexed_count: 0,
        tier: "unpaid",
        quota_note: "Free-tier quota varies.",
      },
    }),
  );
  await page.route("**/api/projects/*/visual-index", (route) =>
    route.fulfill({ json: { job_ids: ["fake-visual-index-job"] } }),
  );
  await page.route("**/api/projects/*/search", async (route) => {
    if (route.request().postDataJSON().mode !== "visual") {
      await route.continue();
      return;
    }
    const project = await page.evaluate(() =>
      localStorage.getItem("storyroom.project"),
    );
    const details = await request.get(`/api/projects/${project}`);
    const asset = (await details.json()).assets[0];
    await route.fulfill({
      json: {
        results: [
          {
            id: "visual-test-candidate",
            asset_id: asset.id,
            asset_name: asset.name,
            start_frame: 6,
            end_frame: 36,
            rank: 1,
            kind: "visual",
            media_url: `/api/assets/${asset.id}/proxy`,
          },
        ],
        checked_candidates: 1,
        incomplete: true,
        warning: "Only one ranked moment was verified to limit cloud requests.",
      },
    });
  });

  await page.getByLabel("Search mode").selectOption("visual");
  await page
    .getByRole("button", { name: "Estimate & index permitted clips" })
    .click();
  await expect(
    page
      .getByText(/Do not send sensitive, confidential, or personal footage/)
      .last(),
  ).toBeVisible();
  await page.getByRole("button", { name: "Index 1 new segments" }).click();
  await page.getByLabel("Search footage").fill("person doing a jumping jack");
  await page.getByRole("button", { name: "Search", exact: true }).click();
  await expect(page.getByText("VISUAL MATCH · #1")).toBeVisible();
  await expect(page.getByRole("alert")).toContainText(
    "Only one ranked moment was verified",
  );
  await page.getByLabel("Search footage").fill("a different action");
  await expect(page.getByText("VISUAL MATCH · #1")).not.toBeVisible();
  await page.getByLabel("Search footage").fill("person doing a jumping jack");
  await page.getByRole("button", { name: "Search", exact: true }).click();
  await expect(page.getByText("VISUAL MATCH · #1")).toBeVisible();
  await page.getByRole("button", { name: "Preview visual match 1" }).click();
  await expect(page.locator("video")).toBeVisible();
  await expect(
    page.getByRole("slider", { name: "Position within selected clip" }),
  ).toBeVisible();
  await expect(page.locator(".assembly-controls span")).toContainText("/ 1.0s");
  expect(
    await page
      .locator("video")
      .evaluate((v) => (v as HTMLVideoElement).controls),
  ).toBe(false);
  await page
    .getByRole("button", { name: "Add to section", exact: true })
    .click();
  await expect(page.locator(".clip-row")).toHaveCount(1);
  await page.locator(".clip-main").click();
  await page.getByLabel("In · frame").fill("12");
  await page.getByLabel("Out · frame").fill("42");
  await page.getByRole("button", { name: "Apply changes" }).click();

  const projectId = await page.evaluate(() =>
    localStorage.getItem("storyroom.project"),
  );
  // The save is asynchronous; inspect persisted state only after it commits.
  await expect
    .poll(async () => {
      const saved = await (
        await request.get(`/api/projects/${projectId}`)
      ).json();
      return saved.board[0].selections[0];
    })
    .toMatchObject({ moment_id: null, start_frame: 12, end_frame: 42 });
});

test("visual search checks more moments without losing earlier matches", async ({
  page,
  request,
}) => {
  await page.route("**/api/status", async (route) => {
    const response = await route.fetch();
    await route.fulfill({
      response,
      json: {
        ...(await response.json()),
        visual_ai_ready: true,
        embedding_tier: "unpaid",
        unpaid_terms_acknowledged: true,
      },
    });
  });
  await page.goto("/");
  await page.getByRole("button", { name: "New project", exact: true }).click();
  await page.getByLabel("Project name").fill("Visual pagination " + Date.now());
  await page.getByRole("button", { name: "Create project" }).click();
  await page
    .locator("input[type=file]")
    .setInputFiles(`${process.env.STORYROOM_FIXTURES}/clip-0.mp4`);
  await expect(page.locator(".moment-card")).toHaveCount(1, {
    timeout: 60000,
  });
  await page
    .getByRole("button", { name: /Permissions for clip-0\.mp4/ })
    .click();
  await page.getByLabel("source", { exact: true }).fill("Generated fixture");
  await page.getByLabel("author", { exact: true }).fill("Storyroom tests");
  await page
    .getByLabel("license", { exact: true })
    .fill("Test fixture; no external media");
  await page
    .getByLabel("I have permission to send this footage for cloud analysis")
    .check();
  await page.getByRole("button", { name: "Save permissions" }).click();

  const projectId = await page.evaluate(() =>
    localStorage.getItem("storyroom.project"),
  );
  const project = await (
    await request.get(`/api/projects/${projectId}`)
  ).json();
  const assetId = project.assets[0].id;
  let pageOneAttempts = 0;
  const requestedPages: number[] = [];
  await page.route("**/api/projects/*/search", async (route) => {
    const body = route.request().postDataJSON();
    if (body.mode !== "visual") return route.continue();
    requestedPages.push(body.page);
    if (body.page === 1 && pageOneAttempts++ === 0) {
      await route.fulfill({
        status: 429,
        json: { detail: "Verifier quota reached" },
      });
      return;
    }
    const candidate = (
      id: string,
      start: number,
      end: number,
      rank: number,
    ) => ({
      id,
      asset_id: assetId,
      start_frame: start,
      end_frame: end,
      rank,
      kind: "visual",
    });
    await route.fulfill({
      json:
        body.page === 0
          ? {
              page: 0,
              has_more: true,
              results: [candidate("first", 0, 30, 1)],
            }
          : {
              page: 1,
              has_more: false,
              results: [
                candidate("first", 0, 30, 1),
                candidate("second", 30, 60, 2),
              ],
            },
    });
  });

  await page.getByLabel("Search mode").selectOption("visual");
  await page.getByLabel("Search footage").fill("jumping jacks");
  await page.getByRole("button", { name: "Search", exact: true }).click();
  await expect(page.getByText("VISUAL MATCH · #1")).toBeVisible();
  const more = page.getByRole("button", { name: "Check more moments" });
  await expect(more).toBeVisible();
  await more.click();
  await expect(page.getByRole("alert")).toContainText(
    "Could not check more moments: Verifier quota reached",
  );
  await expect(page.getByText("VISUAL MATCH · #1")).toBeVisible();
  await more.click();
  await expect(page.getByText("VISUAL MATCH · #2")).toBeVisible();
  await expect(page.locator(".moment-card")).toHaveCount(2);
  await expect(more).toHaveCount(0);
  expect(requestedPages).toEqual([0, 1, 1]);

  await page.getByLabel("Search footage").fill("another action");
  await expect(page.locator(".moment-card")).toHaveCount(0);
  await expect(more).toHaveCount(0);
  await page.getByLabel("Search mode").selectOption("keyword");
  await page.getByLabel("Search mode").selectOption("visual");
  await expect(more).toHaveCount(0);
});
