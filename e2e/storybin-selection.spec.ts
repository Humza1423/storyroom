import { test, expect } from "@playwright/test";

test("selecting a Storybin chooses the add destination while explicit editing preserves cuts", async ({
  page,
  request,
}) => {
  await page.goto("/");
  await page.getByRole("button", { name: "New project", exact: true }).click();
  await page
    .getByLabel("Project name")
    .fill(`Storybin destination ${Date.now()}`);
  await page.getByRole("button", { name: "Create project" }).click();
  await page
    .locator("input[type=file]")
    .setInputFiles(`${process.env.STORYROOM_FIXTURES}/clip-0.mp4`);
  await expect(page.locator(".moment-card")).toHaveCount(1, { timeout: 60000 });
  const createBin = async (title: string) => {
    await page.getByRole("button", { name: "Add story section" }).click();
    await page.getByLabel("Section title").fill(title);
    await page
      .getByRole("button", { name: "Save section", exact: true })
      .click();
  };
  await createBin("Preparation");
  await page
    .getByRole("button", { name: "Add to section", exact: true })
    .click();
  await expect(page.locator(".clip-row")).toHaveCount(1);
  const projectId = await page.evaluate(() =>
    localStorage.getItem("storyroom.project"),
  );
  const readProject = async () =>
    (await request.get(`/api/projects/${projectId}`)).json();
  const initialCut = (await readProject()).board[0].selections;
  await createBin("Peak effort");
  const first = page.getByRole("button", {
    name: "Select Storybin Preparation",
    exact: true,
  });
  const second = page.getByRole("button", {
    name: "Select Storybin Peak effort",
    exact: true,
  });
  // Creation keeps its existing behavior; selecting another destination is explicit.
  await expect(first).toHaveAttribute("aria-pressed", "true");
  await second.click();
  await expect(page.getByLabel("Section title")).toHaveCount(0);
  await expect(page.locator(".modal-backdrop")).toHaveCount(0);
  await expect(second).toHaveAttribute("aria-pressed", "true");
  await expect(first).toHaveAttribute("aria-pressed", "false");
  await expect(page.locator(".add-target")).toContainText("Peak effort");
  await page
    .getByRole("button", { name: "Edit Storybin Peak effort", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "Shape this section" }),
  ).toBeVisible();
  const renamed = "TechniqueDetailsForOurNextTrainingMontageAndStrongestFinish";
  await page.getByLabel("Section title").fill(renamed);
  await page.getByRole("button", { name: "Save section", exact: true }).click();
  await expect(page.locator(".add-target")).toContainText(renamed);
  await expect(
    page.getByRole("button", {
      name: `Select Storybin ${renamed}`,
      exact: true,
    }),
  ).toHaveAttribute("aria-pressed", "true");
  await expect
    .poll(async () => (await readProject()).board[1].title)
    .toBe(renamed);
  expect((await readProject()).board[0].selections).toEqual(initialCut);
  await page
    .getByRole("button", { name: "Add to section", exact: true })
    .click();
  await expect(
    page.locator(".story-section").nth(1).locator(".clip-row"),
  ).toHaveCount(1);
  const saved = await readProject();
  expect(saved.board[0].selections).toEqual(initialCut);
  expect(saved.board[1].selections[0]).toMatchObject({
    start_frame: 0,
    end_frame: 60,
  });
  await page.reload();
  await expect(
    page.getByRole("button", {
      name: `Select Storybin ${renamed}`,
      exact: true,
    }),
  ).toBeVisible();
  expect((await readProject()).board).toEqual(saved.board);
  await page.setViewportSize({ width: 390, height: 844 });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBeTruthy();
  const section = page.locator(".story-section").nth(1);
  expect(
    await section.evaluate((element) => {
      const bounds = element.getBoundingClientRect();
      return [...element.querySelectorAll("header button")].every((button) => {
        const control = button.getBoundingClientRect();
        return control.left >= bounds.left && control.right <= bounds.right;
      });
    }),
  ).toBeTruthy();
});
