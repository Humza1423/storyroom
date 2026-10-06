import { test, expect } from "@playwright/test";

test("create, import, select, trim, reopen, render, export, undo", async ({
  page,
  request,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await page.goto("/");
  await page.getByRole("button", { name: "New project", exact: true }).click();
  const name = "Browser test " + Date.now();
  await page.getByLabel("Project name").fill(name);
  await page.getByRole("button", { name: "Create project" }).click();
  await expect(page.getByRole("heading", { name, exact: true })).toBeVisible();
  await page
    .locator("input[type=file]")
    .setInputFiles("data/fixtures/browser-test.mp4");
  await expect(page.locator(".moment-card")).toHaveCount(1, { timeout: 30000 });
  await page.getByRole("button", { name: "Add story section" }).click();
  await page.getByLabel("Section title").fill("Practice");
  await page
    .getByLabel("What should it contribute?")
    .fill("Establish the action");
  await page.getByRole("button", { name: "Save section", exact: true }).click();
  await expect(page.locator(".story-section")).toHaveCount(1);
  await page
    .getByRole("button", { name: "Add to section", exact: true })
    .click();
  await expect(page.locator(".clip-row")).toHaveCount(1);
  await page.locator(".clip-main").click();
  await page.getByLabel("In · frame").fill("5");
  await page.getByLabel("Out · frame").fill("45");
  await page.getByRole("button", { name: "Apply changes" }).click();
  await expect(page.locator(".clip-main small")).toHaveText(
    "00:00:05 → 00:01:15",
  );
  await page.reload();
  await expect(page.locator(".clip-main small")).toHaveText(
    "00:00:05 → 00:01:15",
  );
  await page.getByRole("button", { name: "Play assembly" }).click();
  await expect(page.locator("video")).toBeVisible();
  await expect
    .poll(() =>
      page.locator("video").evaluate((v) => (v as HTMLVideoElement).readyState),
    )
    .toBeGreaterThanOrEqual(2);
  await expect
    .poll(() =>
      page
        .locator("video")
        .evaluate((v) => (v as HTMLVideoElement).currentTime),
    )
    .toBeGreaterThan(0.3);
  await page
    .getByRole("button", { name: "Render preview", exact: true })
    .click();
  await expect(page.getByRole("link", { name: "Preview MP4" })).toBeVisible({
    timeout: 30000,
  });
  await page.getByRole("button", { name: "Export to Resolve" }).click();
  await expect(page.getByRole("link", { name: "Resolve XML" })).toBeVisible({
    timeout: 30000,
  });
  const href = await page
    .getByRole("link", { name: "Resolve XML" })
    .getAttribute("href");
  const response = await request.get(href!);
  expect(response.ok()).toBeTruthy();
  expect(await response.text()).toContain("<xmeml");
  await page.getByRole("button", { name: "Undo board change" }).click();
  await expect(page.locator(".clip-main small")).toHaveText(
    "00:00:00 → 00:02:00",
  );
  expect(errors).toEqual([]);
});

test("responsive workspace has no horizontal overflow", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/");
  await expect(
    page.getByRole("heading", { name: /Find the story/ }),
  ).toBeVisible();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBeTruthy();
  await page
    .getByRole("button", { name: "First assembly · technical demo" })
    .click();
  await expect(page.locator(".story-section").first()).toBeVisible();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBeTruthy();
});
