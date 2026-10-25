import { test, expect } from "@playwright/test";
import { execFileSync } from "node:child_process";
import { activityBounds } from "../src/features/preview/visualRange";
import type { VisualCandidate } from "../src/types";

const candidate: VisualCandidate = {
  id: "boxing-activity",
  asset_id: "fixture",
  kind: "visual",
  rank: 1,
  start_frame: 150,
  end_frame: 300,
  activity: {
    id: "boxing-event",
    start_frame: 60,
    end_frame: 660,
    complete: true,
    continues_before: false,
    continues_after: false,
    intent: "broad_activity",
    requested_frames: null,
    duration_fulfilled: true,
  },
};

test("activity playback rejects invalid bounds and ranges excluding the selected cut", () => {
  expect(activityBounds(candidate, 720)).toEqual({ start: 60, end: 660 });
  for (const [start_frame, end_frame] of [
    [-1, 660],
    [60, 721],
    [660, 60],
    [151, 660],
    [60, 299],
    [0.5, 660],
  ]) {
    expect(
      activityBounds(
        {
          ...candidate,
          activity: { ...candidate.activity!, start_frame, end_frame },
        },
        720,
      ),
    ).toBeNull();
  }
  expect(activityBounds({ ...candidate, activity: undefined }, 720)).toBeNull();
});

test("suggested cut, activity and source previews preserve independent saved cuts", async ({
  page,
  request,
}) => {
  const fixture = `${process.env.STORYROOM_FIXTURES}/activity-24s.mp4`;
  execFileSync("ffmpeg", [
    "-nostdin",
    "-y",
    "-v",
    "error",
    "-f",
    "lavfi",
    "-i",
    "testsrc2=size=320x180:rate=30:duration=24",
    "-c:v",
    "libx264",
    "-threads",
    "2",
    "-pix_fmt",
    "yuv420p",
    fixture,
  ]);
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
  await page.getByLabel("Project name").fill(`Activity playback ${Date.now()}`);
  await page.getByRole("button", { name: "Create project" }).click();
  await page.locator("input[type=file]").setInputFiles(fixture);
  await expect(page.locator(".moment-card")).toHaveCount(1, { timeout: 60000 });
  await page
    .getByRole("button", { name: /Permissions for activity-24s\.mp4/ })
    .click();
  await page
    .getByLabel("source", { exact: true })
    .fill("Generated browser fixture");
  await page.getByLabel("author", { exact: true }).fill("Storyroom tests");
  await page
    .getByLabel("license", { exact: true })
    .fill("Generated test fixture");
  await page
    .getByLabel("I have permission to send this footage for cloud analysis")
    .check();
  await page.getByRole("button", { name: "Save permissions" }).click();
  await page.getByRole("button", { name: "Add story section" }).click();
  await page.getByLabel("Section title").fill("Training");
  await page.getByLabel("What should it contribute?").fill("Coherent movement");
  await page.getByRole("button", { name: "Save section", exact: true }).click();
  const projectId = await page.evaluate(() =>
    localStorage.getItem("storyroom.project"),
  );
  const details = await (
    await request.get(`/api/projects/${projectId}`)
  ).json();
  let activityComplete = true;
  const submittedGrounding: boolean[] = [];
  await page.route("**/api/projects/*/search", async (route) => {
    const body = route.request().postDataJSON();
    if (body.mode !== "visual") return route.continue();
    submittedGrounding.push(body.grounded);
    await route.fulfill({
      json: {
        results: [
          {
            ...candidate,
            id: body.query === "kick" ? "kick-result" : candidate.id,
            start_frame: body.query === "kick" ? 30 : candidate.start_frame,
            end_frame: body.query === "kick" ? 60 : candidate.end_frame,
            asset_id: details.assets[0].id,
            activity: {
              ...candidate.activity,
              complete: activityComplete,
              start_frame:
                body.query === "kick" ? 0 : candidate.activity!.start_frame,
              inspection_job_id: body.grounded ? "activity-job" : undefined,
            },
          },
        ],
        page: 0,
        has_more: false,
        activity_job_id:
          body.grounded && body.query !== "kick" ? "activity-job" : undefined,
      },
    });
  });
  await page.route("**/api/projects/*/visual-index-estimate", (route) =>
    route.fulfill({
      json: {
        estimated_usd: 0,
        reserved_usd: 0,
        segment_count: 1,
        missing_segment_count: 1,
        frame_count: 6,
        indexed_count: 0,
        tier: "unpaid",
        quota_note: "Fixture",
      },
    }),
  );
  await page.route("**/api/projects/*/visual-index", (route) =>
    route.fulfill({ json: { job_ids: ["fake-activity-index"] } }),
  );
  await page.getByLabel("Search mode").selectOption("visual");
  await page
    .getByRole("button", { name: "Estimate & index permitted clips" })
    .click();
  await page.getByRole("button", { name: "Index 1 new segments" }).click();
  await page.getByLabel("Search footage").fill("boxing");
  await page.getByRole("button", { name: "Search", exact: true }).click();
  await expect(page.locator(".moment-card")).toContainText(
    "20.0s · fully inspected",
  );
  const previewWrites: string[] = [];
  const recordPreviewWrite = (request: import("@playwright/test").Request) => {
    if (request.method() !== "GET") previewWrites.push(request.url());
  };
  page.on("request", recordPreviewWrite);
  await page
    .getByRole("button", { name: "Preview suggested cut visual match 1" })
    .click();
  await expect(page.locator(".assembly-controls span")).toContainText("/ 5.0s");
  await expect(
    page.getByRole("slider", { name: "Selected cut in frame" }),
  ).toHaveValue("150");
  await page
    .getByRole("button", { name: "Review activity", exact: true })
    .click();
  await expect(page.locator(".assembly-controls span")).toContainText(
    "/ 20.0s",
  );
  await expect(
    page.getByRole("slider", { name: "Scrub activity" }),
  ).toHaveAttribute("min", "60");
  await expect
    .poll(() =>
      page
        .locator("video")
        .evaluate((video) => (video as HTMLVideoElement).currentTime),
    )
    .toBeCloseTo(2, 1);
  await page.getByRole("slider", { name: "Position in activity" }).fill("19.8");
  await page
    .getByRole("button", { name: "Play activity", exact: true })
    .click();
  await expect
    .poll(() =>
      page
        .locator("video")
        .evaluate((video) => (video as HTMLVideoElement).paused),
    )
    .toBe(true);
  await expect
    .poll(() =>
      page
        .locator("video")
        .evaluate((video) => (video as HTMLVideoElement).currentTime),
    )
    .toBeGreaterThanOrEqual(21.95);
  await page.getByRole("button", { name: "View full source video" }).click();
  await expect(page.locator(".assembly-controls span")).toContainText(
    "/ 24.0s",
  );
  await page.getByRole("button", { name: "Return to match preview" }).click();
  await expect(page.locator(".assembly-controls span")).toContainText("/ 5.0s");
  await expect(
    page.getByRole("slider", { name: "Selected cut in frame" }),
  ).toHaveValue("150");
  await expect(
    page.getByRole("slider", { name: "Selected cut out frame" }),
  ).toHaveValue("300");
  page.off("request", recordPreviewWrite);
  expect(previewWrites).toEqual([]);
  await page
    .getByRole("button", { name: "Quick add to Storybin", exact: true })
    .click();
  await expect
    .poll(
      async () =>
        (await (await request.get(`/api/projects/${projectId}`)).json())
          .board[0].selections[0],
    )
    .toMatchObject({ start_frame: 150, end_frame: 300 });
  await page
    .getByRole("button", { name: "Drag visual match" })
    .dragTo(page.locator(".story-section").first());
  await expect
    .poll(
      async () =>
        (await (await request.get(`/api/projects/${projectId}`)).json())
          .board[0].selections[1],
    )
    .toMatchObject({ start_frame: 150, end_frame: 300 });
  activityComplete = false;
  await page.getByRole("button", { name: "Search", exact: true }).click();
  await expect(page.locator(".moment-card")).toContainText(
    "partially inspected",
  );
  // The same polling path used by real worker jobs must update proposals only.
  let completedJob = false;
  let completedJobReads = 0;
  await page.route(`**/api/projects/${projectId}`, async (route) => {
    if (route.request().method() !== "GET") return route.continue();
    const response = await route.fetch();
    const project = await response.json();
    if (completedJob) completedJobReads++;
    await route.fulfill({
      response,
      json: {
        ...project,
        jobs: [
          ...project.jobs,
          {
            id: "activity-job",
            kind: "activity_inspect",
            status: completedJob ? "done" : "running",
            progress: completedJob ? 1 : 0.5,
            message: "Fixture activity inspection",
            result: completedJob
              ? {
                  query: "boxing",
                  visual_results: [
                    {
                      ...candidate,
                      asset_id: details.assets[0].id,
                      start_frame: 180,
                      end_frame: 330,
                      activity: {
                        ...candidate.activity,
                        complete: true,
                        inspection_job_id: "activity-job",
                      },
                    },
                  ],
                }
              : null,
          },
        ],
      },
    });
  });
  await page.getByLabel(/Activity search \(preview\)/).check();
  await page.getByRole("button", { name: "Search", exact: true }).click();
  expect(submittedGrounding.at(-1)).toBe(true);
  await expect(page.locator(".moment-card")).toContainText(
    "partially inspected",
  );
  completedJob = true;
  await expect(page.locator(".moment-card .filename").first()).toContainText(
    "6.0–11.0s",
    { timeout: 10000 },
  );
  const unchanged = await (
    await request.get(`/api/projects/${projectId}`)
  ).json();
  expect(
    unchanged.board[0].selections.map(
      (s: { start_frame: number; end_frame: number }) => [
        s.start_frame,
        s.end_frame,
      ],
    ),
  ).toEqual([
    [150, 300],
    [150, 300],
  ]);
  // A previously tracked job must not reinsert boxing results after a new query.
  completedJob = false;
  await page.getByRole("button", { name: "Search", exact: true }).click();
  await expect(page.locator(".moment-card")).toContainText(
    "partially inspected",
  );
  await page.getByLabel("Search footage").fill("kick");
  await page.getByRole("button", { name: "Search", exact: true }).click();
  await expect(page.locator(".moment-card .filename").first()).toContainText(
    "1.0–2.0s",
  );
  completedJobReads = 0;
  completedJob = true;
  await expect
    .poll(() => completedJobReads, { timeout: 10000 })
    .toBeGreaterThan(0);
  await expect(page.locator(".moment-card")).toHaveCount(1);
  await expect(page.locator(".moment-card .filename").first()).toContainText(
    "1.0–2.0s",
  );
  await page.reload();
  await expect(page.locator(".clip-row")).toHaveCount(2);
  const saved = await (await request.get(`/api/projects/${projectId}`)).json();
  expect(saved.board[0].selections[0]).toMatchObject({
    start_frame: 150,
    end_frame: 300,
  });
});
