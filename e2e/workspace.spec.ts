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
    .setInputFiles(
      [0, 1, 2].map((i) => `${process.env.STORYROOM_FIXTURES}/clip-${i}.mp4`),
    );
  await expect(page.locator(".moment-card")).toHaveCount(3, { timeout: 30000 });
  await page.getByRole("button", { name: "Add story section" }).click();
  await page.getByLabel("Section title").fill("Practice");
  await page
    .getByLabel("What should it contribute?")
    .fill("Establish the action");
  await page.getByRole("button", { name: "Save section", exact: true }).click();
  await expect(page.locator(".story-section")).toHaveCount(1);
  await page
    .getByRole("button", { name: "Add to section", exact: true })
    .first()
    .click();
  await expect(page.locator(".clip-row")).toHaveCount(1);
  await page.locator(".clip-main").click();
  await page.getByLabel("In · frame").fill("5");
  await page.getByLabel("Out · frame").fill("45");
  await page.getByRole("button", { name: "Apply changes" }).click();
  await expect(page.locator(".clip-main small").first()).toHaveText(
    "00:00:05 → 00:01:15",
  );
  // Three placements include a repeated source; IDs and ranges stay independent.
  await page
    .getByRole("button", { name: "Add to section", exact: true })
    .nth(1)
    .click();
  await expect(page.locator(".clip-row")).toHaveCount(2);
  await page
    .getByRole("button", { name: "Add to section", exact: true })
    .first()
    .click();
  await expect(page.locator(".clip-row")).toHaveCount(3);
  await page
    .getByRole("button", { name: "Move clip later", exact: true })
    .first()
    .click();
  await expect(page.locator(".clip-main small").nth(1)).toHaveText(
    "00:00:05 → 00:01:15",
  );
  await page.reload();
  await expect(page.locator(".clip-main small").nth(1)).toHaveText(
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
  const otio = await request.get(href! + "?format=otio");
  expect(otio.ok()).toBeTruthy();
  expect(await otio.text()).toContain("Timeline");
  await page.getByRole("button", { name: "Undo board change" }).click();
  await expect(page.locator(".clip-main small").first()).toHaveText(
    "00:00:05 → 00:01:15",
  );
  expect(errors).toEqual([]);
});

test("responsive workspace has no horizontal overflow", async ({
  page,
  request,
}) => {
  const response = await request.post("/api/projects", {
    headers: { "X-Storyroom": "local" },
    data: { name: "Mobile project", brief: "" },
  });
  expect(response.ok()).toBeTruthy();
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
  await page.getByRole("button", { name: "Mobile project" }).click();
  await page.getByRole("button", { name: "Add story section" }).click();
  await page.getByLabel("Section title").fill("Mobile section");
  await page.getByRole("button", { name: "Save section", exact: true }).click();
  await expect(page.locator(".story-section")).toHaveCount(1);
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBeTruthy();
});

test("late project response cannot replace the active project or brief", async ({
  page,
  request,
}) => {
  const create = async (name: string) =>
    (
      await request.post("/api/projects", {
        headers: { "X-Storyroom": "local" },
        data: { name, brief: name + " brief" },
      })
    ).json();
  const old = await create("Slow project");
  await create("Active project");
  let release!: () => void;
  const gate = new Promise<void>((resolve) => {
    release = resolve;
  });
  let intercepted!: () => void;
  const arrived = new Promise<void>((resolve) => {
    intercepted = resolve;
  });
  await page.route(`**/api/projects/${old.id}`, async (route) => {
    const response = await route.fetch();
    intercepted();
    await gate;
    await route.fulfill({ response });
  });
  await page.goto("/");
  await page.getByRole("button", { name: "Slow project", exact: true }).click();
  await arrived;
  await page
    .getByRole("button", { name: "Active project", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "Active project", exact: true }),
  ).toBeVisible();
  release();
  await page.unrouteAll({ behavior: "wait" });
  await expect(
    page.getByRole("heading", { name: "Active project", exact: true }),
  ).toBeVisible();
  await expect(page.locator(".brief-bar textarea")).toHaveValue(
    "Active project brief",
  );
});
