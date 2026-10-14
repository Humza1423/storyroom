import { test, expect } from "@playwright/test";

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
  await page.getByLabel("source", { exact: true }).fill("Generated browser fixture");
  await page.getByLabel("author", { exact: true }).fill("Storyroom tests");
  await page.getByLabel("license", { exact: true }).fill("Test fixture; no external media");
  await page
    .getByLabel("I have permission to send this footage for cloud analysis")
    .check();
  await page.getByRole("button", { name: "Save permissions" }).click();

  await page.getByRole("button", { name: "Add story section" }).click();
  await page.getByLabel("Section title").fill("Technique");
  await page
    .getByLabel("What should it contribute?")
    .fill("Show the exercise");
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
      json: [
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
    });
  });

  await page.getByLabel("Search mode").selectOption("visual");
  await page
    .getByRole("button", { name: "Estimate & index permitted clips" })
    .click();
  await expect(
    page.getByText(/Do not send sensitive, confidential, or personal footage/).last(),
  ).toBeVisible();
  await page.getByRole("button", { name: "Index 1 new segments" }).click();
  await page.getByLabel("Search footage").fill("person doing a jumping jack");
  await page.getByRole("button", { name: "Search", exact: true }).click();
  await expect(page.getByText("VISUAL MATCH · #1")).toBeVisible();
  await page.getByRole("button", { name: "Preview visual match 1" }).click();
  await expect(page.locator("video")).toBeVisible();
  await page.getByRole("button", { name: "Add to section", exact: true }).click();
  await expect(page.locator(".clip-row")).toHaveCount(1);
  await page.locator(".clip-main").click();
  await page.getByLabel("In · frame").fill("12");
  await page.getByLabel("Out · frame").fill("42");
  await page.getByRole("button", { name: "Apply changes" }).click();

  const projectId = await page.evaluate(() =>
    localStorage.getItem("storyroom.project"),
  );
  const saved = await (await request.get(`/api/projects/${projectId}`)).json();
  expect(saved.board[0].selections).toHaveLength(1);
  expect(saved.board[0].selections[0]).toMatchObject({
    moment_id: null,
    start_frame: 12,
    end_frame: 42,
  });
});
