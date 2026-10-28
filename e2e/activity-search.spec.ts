import { test, expect } from "@playwright/test";
import { execFileSync } from "node:child_process";
import { activityBounds } from "../src/features/preview/visualRange";
import type { VisualCandidate } from "../src/types";
import { activityPresentation } from "../src/features/library/activityPresentation";
import {
  createVisualRange,
  moveVisualHandle,
  selectEstablishedActivity,
} from "../src/features/preview/visualRange";
import { refreshVisualEvidence } from "../src/features/preview/refreshVisualEvidence";

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

test("duration presentation separates supported length, incomplete inspection and stopped work", () => {
  const durationCandidate = (
    complete: boolean,
    end = 240,
  ): VisualCandidate => ({
    ...candidate,
    start_frame: 0,
    end_frame: Math.min(end, 600),
    activity: {
      ...candidate.activity!,
      start_frame: 0,
      end_frame: end,
      complete,
      requested_frames: 600,
      duration_fulfilled: end >= 600,
    },
  });
  expect(activityPresentation(durationCandidate(true, 900))?.duration).toBe(
    "Requested 20 seconds. 20 seconds selected.",
  );
  expect(activityPresentation(durationCandidate(true))?.duration).toBe(
    "Requested 20 seconds. Found 8 seconds of this activity. The full 8 seconds are selected.",
  );
  const running = { id: "job", status: "running", message: "Inspecting" };
  const partial = activityPresentation(durationCandidate(false), running)!;
  expect(partial.duration).toContain("8 seconds confirmed so far");
  expect(partial.duration).toContain("Requested duration is not yet confirmed");
  expect(partial.inspection).toContain("Checking more footage");
  expect(partial.duration).not.toContain("Found 8 seconds of this activity");
  for (const status of ["failed", "cancelled"]) {
    const stopped = activityPresentation(durationCandidate(false), {
      id: "job",
      status,
      message: "Continuity could not be verified.",
    })!;
    expect(stopped.inspection).toContain("Inspection stopped");
    expect(stopped.inspection).toContain("Confirmed footage remains available");
    expect(stopped.duration).toContain(
      "Requested duration is not yet confirmed",
    );
    expect(stopped.duration).not.toContain("Found 8 seconds of this activity");
  }
  const supportedButUnresolved = activityPresentation(
    durationCandidate(false, 600),
    running,
  )!;
  expect(supportedButUnresolved.duration).toBe(
    "Requested 20 seconds. 20 seconds selected.",
  );
  expect(supportedButUnresolved.inspection).toContain("Checking more footage");
  expect(
    activityPresentation(durationCandidate(true, 600), undefined, 150)
      ?.duration,
  ).toBe("Requested 20 seconds. 20 seconds supported. 5 seconds selected.");
  expect(
    activityPresentation(durationCandidate(true), undefined, 150)?.duration,
  ).toBe(
    "Requested 20 seconds. Found 8 seconds of this activity. 5 seconds selected.",
  );
});

test("boundary conflicts keep recognized activity available without claiming a duration shortfall", () => {
  const stopped = activityPresentation(
    { ...candidate, activity: { ...candidate.activity!, complete: false } },
    {
      id: "job",
      status: "failed",
      message: "Inspection is unrelated to its retrieved anchor",
    },
  )!;
  expect(stopped.inspection).toContain(
    "The next inspection found a different moment",
  );
  expect(stopped.inspection).not.toContain("retrieved anchor");
  for (const conflict of [
    "boundary_conflict_before",
    "boundary_conflict_after",
  ] as const) {
    const conflicted: VisualCandidate = {
      ...candidate,
      start_frame: 0,
      end_frame: 240,
      activity: {
        ...candidate.activity!,
        start_frame: 0,
        end_frame: 240,
        // A conflict always remains unresolved, including a stale completion flag.
        complete: true,
        [conflict]: true,
        requested_frames: 600,
        duration_fulfilled: false,
      },
    };
    for (const status of ["running", "failed", "cancelled"]) {
      const presentation = activityPresentation(conflicted, {
        id: "job",
        status,
        message: "Boundary unresolved.",
      })!;
      expect(
        presentation.inspection.startsWith(
          "Action found; its beginning or end needs another look.",
        ),
      ).toBe(true);
      expect(presentation.inspection).toContain(
        status === "running" ? "Checking more footage" : "Inspection stopped",
      );
      expect(presentation.duration).toContain("8 seconds selected");
      expect(presentation.duration).toContain(
        "Requested duration is not yet confirmed",
      );
      expect(presentation.duration).not.toContain(
        "Found 8 seconds of this activity",
      );
      expect(presentation.inspection).not.toContain(
        "Activity extent inspected",
      );
    }
  }
  expect(activityPresentation(candidate)?.inspection).not.toContain(
    "needs another look",
  );
});

test("updated activity evidence preserves manual draft frames and rejects unrelated updates", () => {
  const initial = createVisualRange(candidate, 900)!;
  const draft = { ...initial, selectedStart: 160, selectedEnd: 290 };
  const updated = {
    ...candidate,
    start_frame: 180,
    end_frame: 780,
    activity: { ...candidate.activity!, end_frame: 900, complete: true },
  };
  const refreshed = refreshVisualEvidence(draft, [updated], 900);
  expect(refreshed.candidate).toBe(updated);
  expect([refreshed.selectedStart, refreshed.selectedEnd]).toEqual([160, 290]);
  expect(refreshed.contextEnd).toBe(900);
  expect(draft.candidate).toBe(candidate);
  expect(refreshVisualEvidence(draft, [{ ...updated, id: "other" }], 900)).toBe(
    draft,
  );
  expect(
    refreshVisualEvidence(draft, [{ ...updated, asset_id: "other" }], 900),
  ).toBe(draft);
  expect(
    refreshVisualEvidence(draft, [{ ...updated, end_frame: 901 }], 900),
  ).toBe(draft);
});

test("full activity handles and full selection use established frames, not suggested context", () => {
  const range = createVisualRange(candidate, 900)!;
  expect([range.contextStart, range.contextEnd]).toEqual([60, 660]);
  expect(moveVisualHandle(range, "in", -1).selectedStart).toBe(60);
  expect(moveVisualHandle(range, "out", 999).selectedEnd).toBe(660);
  const full = selectEstablishedActivity(range);
  expect([full.selectedStart, full.selectedEnd]).toEqual([60, 660]);
  const expanded = refreshVisualEvidence(
    full,
    [{ ...candidate, activity: { ...candidate.activity!, end_frame: 900 } }],
    900,
  );
  expect([expanded.selectedStart, expanded.selectedEnd]).toEqual([60, 660]);
  expect(expanded.contextEnd).toBe(900);
});

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
    expect(
      createVisualRange(
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
  page.setDefaultTimeout(15000);
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
              // A completed/duplicate candidate may have no job marker. The
              // worker snapshot still replaces the entire original proposal batch.
              inspection_job_id: undefined,
            },
          },
        ],
        page: 0,
        has_more: false,
        warning: body.grounded
          ? "Only the first five candidate locations on this page were checked."
          : undefined,
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
    "Activity extent inspected",
  );
  const previewWrites: string[] = [];
  const recordPreviewWrite = (request: import("@playwright/test").Request) => {
    if (request.method() !== "GET") previewWrites.push(request.url());
  };
  page.on("request", recordPreviewWrite);
  await page
    .getByRole("button", {
      name: "Review activity & choose cut visual match 1",
    })
    .click();
  await expect(page.locator(".assembly-controls span")).toContainText(
    "/ 20.0s",
  );
  await expect(
    page.getByRole("slider", { name: "Selected cut in frame" }),
  ).toHaveValue("150");
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
  await page.getByRole("button", { name: "Return to selected cut" }).click();
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
    .getByRole("button", { name: "Review before adding", exact: true })
    .click();
  await expect(page.locator(".clip-row")).toHaveCount(0);
  await page
    .getByRole("button", { name: "Select full activity", exact: true })
    .click();
  await expect(
    page.getByRole("slider", { name: "Selected cut in frame" }),
  ).toHaveValue("60");
  await expect(
    page.getByRole("slider", { name: "Selected cut out frame" }),
  ).toHaveValue("660");
  await page
    .getByRole("spinbutton", { name: "Selected cut start frame number" })
    .fill("60");
  await page.getByRole("slider", { name: "Selected cut in frame" }).focus();
  await page.keyboard.press("ArrowRight");
  await page
    .getByRole("spinbutton", { name: "Selected cut end frame number" })
    .fill("660");
  await page
    .getByRole("spinbutton", { name: "Selected cut end frame number" })
    .press("Enter");
  await page.getByRole("slider", { name: "Selected cut out frame" }).focus();
  await page.keyboard.press("ArrowLeft");
  await expect(
    page.getByRole("slider", { name: "Selected cut out frame" }),
  ).toHaveValue("659");
  await expect(page.getByLabel("Selected cut frame summary")).toContainText(
    "598 frames",
  );
  await page
    .getByRole("button", { name: "Add selected cut to Storybin" })
    .click();
  await expect
    .poll(
      async () =>
        (await (await request.get(`/api/projects/${projectId}`)).json())
          .board[0].selections[0],
    )
    .toMatchObject({ start_frame: 61, end_frame: 659 });
  await page
    .getByRole("button", { name: "Drag visual match" })
    .dragTo(page.locator(".story-section").first());
  await expect(page.locator(".clip-row")).toHaveCount(1);
  // Reopening the same result retains the draft; choose a different range explicitly.
  await expect(
    page.getByRole("slider", { name: "Selected cut in frame" }),
  ).toHaveValue("61");
  await page
    .getByRole("spinbutton", { name: "Selected cut start frame number" })
    .fill("150");
  await page
    .getByRole("spinbutton", { name: "Selected cut end frame number" })
    .fill("300");
  await page
    .getByRole("button", { name: "Add selected cut to Storybin" })
    .click();
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
  let failedJob = false;
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
            status: failedJob ? "failed" : completedJob ? "done" : "running",
            progress: completedJob ? 1 : 0.5,
            message: failedJob
              ? "Continuity could not be verified."
              : "Fixture activity inspection",
            result:
              completedJob || failedJob
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
                          end_frame: 720,
                          complete: completedJob,
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
    "Checking more footage",
  );
  await page
    .getByRole("button", {
      name: "Review activity & choose cut visual match 1",
    })
    .click();
  await page
    .getByRole("button", { name: "Select activity found so far" })
    .click();
  completedJob = true;
  await expect(page.locator(".moment-card .filename").first()).toContainText(
    "6.0–11.0s",
    { timeout: 10000 },
  );
  await expect(page.locator(".moment-card")).toHaveCount(1);
  await expect(page.getByLabel("Activity inspection status")).toContainText(
    "Activity extent inspected",
  );
  await expect(
    page.getByRole("slider", { name: "Selected cut in frame" }),
  ).toHaveValue("60");
  await expect(
    page.getByRole("slider", { name: "Selected cut out frame" }),
  ).toHaveValue("660");
  await expect(
    page.getByRole("slider", { name: "Selected cut out frame" }),
  ).toHaveAttribute("max", "720");
  await page
    .getByRole("spinbutton", { name: "Selected cut start frame number" })
    .fill("160");
  await page
    .getByRole("spinbutton", { name: "Selected cut end frame number" })
    .fill("290");
  await page
    .getByRole("spinbutton", { name: "Selected cut end frame number" })
    .press("Enter");
  await expect(
    page
      .getByRole("alert")
      .filter({ hasText: "Only the first five candidate locations" }),
  ).toBeVisible();
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
    [61, 659],
    [150, 300],
  ]);
  // Failed continuation keeps the same confirmed proposal, not a no-match result.
  completedJob = false;
  failedJob = true;
  await expect(page.locator(".moment-card")).toContainText(
    "Inspection stopped",
  );
  await expect(page.getByLabel("Activity inspection status")).toContainText(
    "Confirmed footage remains available",
  );
  await expect(
    page.getByRole("slider", { name: "Selected cut in frame" }),
  ).toHaveValue("160");
  failedJob = false;
  // A previously tracked job must not reinsert boxing results after a new query.
  completedJob = false;
  await page.getByRole("button", { name: "Search", exact: true }).click();
  await expect(page.locator(".moment-card")).toContainText(
    "Checking more footage",
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
    start_frame: 61,
    end_frame: 659,
  });

  // Exercise all duration messages in the browser over the real prepared source.
  let durationEnd = 660;
  let durationCase = "fulfilled";
  let durationComplete = true;
  let durationJobStatus = "done";
  const durationResult = (): VisualCandidate => ({
    ...candidate,
    id: `duration-result-${durationCase}`,
    asset_id: details.assets[0].id,
    start_frame: 0,
    end_frame: Math.min(600, durationEnd),
    activity: {
      ...candidate.activity!,
      start_frame: 0,
      end_frame: durationEnd,
      complete: durationComplete,
      continues_after: !durationComplete,
      requested_frames: 600,
      duration_fulfilled: durationEnd >= 600,
      inspection_job_id: "duration-job",
    },
  });
  await page.route("**/api/projects/*/search", (route) =>
    route.fulfill({
      json: {
        results: [durationResult()],
        page: 0,
        has_more: false,
        activity_job_id: "duration-job",
      },
    }),
  );
  await page.route(`**/api/projects/${projectId}`, async (route) => {
    if (route.request().method() !== "GET") return route.continue();
    const response = await route.fetch();
    await route.fulfill({
      response,
      json: {
        ...(await response.json()),
        jobs: [
          {
            id: "duration-job",
            kind: "activity_inspect",
            status: durationJobStatus,
            progress: durationJobStatus === "done" ? 1 : 0.5,
            message:
              durationJobStatus === "failed"
                ? "Continuity could not be verified."
                : "Checking activity",
            result: { visual_results: [durationResult()] },
          },
        ],
      },
    });
  });
  await page.getByLabel("Search mode").selectOption("visual");
  await page.getByLabel("Search footage").fill("20 seconds of boxing");
  for (const state of [
    "fulfilled",
    "shortfall",
    "checking",
    "failed",
  ] as const) {
    durationCase = state;
    durationEnd = state === "fulfilled" ? 660 : 240;
    durationComplete = state === "fulfilled" || state === "shortfall";
    durationJobStatus = durationComplete
      ? "done"
      : state === "failed"
        ? "failed"
        : "running";
    await page.getByRole("button", { name: "Search", exact: true }).click();
    const card = page.locator(".moment-card");
    const expectedDuration =
      state === "fulfilled"
        ? "Requested 20 seconds. 20 seconds selected."
        : state === "shortfall"
          ? "Requested 20 seconds. Found 8 seconds of this activity. The full 8 seconds are selected."
          : "Requested duration is not yet confirmed.";
    await expect(card).toContainText(expectedDuration);
    await page
      .getByRole("button", {
        name: "Review activity & choose cut visual match 1",
      })
      .click();
    const status = page.getByLabel("Activity inspection status");
    await expect(status).toContainText(expectedDuration);
    await expect(
      page.getByRole("slider", { name: "Selected cut in frame" }),
    ).toHaveValue("0");
    await expect(
      page.getByRole("slider", { name: "Selected cut out frame" }),
    ).toHaveValue(state === "fulfilled" ? "600" : "240");
    if (state === "checking" || state === "failed") {
      await expect(status).toContainText(
        state === "checking" ? "Checking more footage" : "Inspection stopped",
      );
      await expect(card).not.toContainText("Found 8 seconds of this activity");
    } else {
      await expect(card.getByRole("alert")).toHaveCount(0);
      await page
        .getByRole("button", { name: "Add selected cut to Storybin" })
        .click();
      await expect
        .poll(async () => {
          const project = await (
            await request.get(`/api/projects/${projectId}`)
          ).json();
          return project.board[0].selections.at(-1);
        })
        .toMatchObject({
          start_frame: 0,
          end_frame: state === "fulfilled" ? 600 : 240,
        });
    }
  }
  // Drag is a destination proposal, not a write or a dependence on later focus.
  const beforeDestination = await (
    await request.get(`/api/projects/${projectId}`)
  ).json();
  await page
    .getByRole("button", { name: "Add story section", exact: true })
    .click();
  await page.getByLabel("Section title").fill("Alternate destination");
  await page.getByRole("button", { name: "Save section", exact: true }).click();
  await page
    .getByRole("button", { name: "Drag visual match", exact: true })
    .dragTo(page.locator(".story-section").nth(1));
  await expect(page.locator(".visual-add-destination")).toContainText(
    "Alternate destination",
  );
  const pending = await (
    await request.get(`/api/projects/${projectId}`)
  ).json();
  expect(pending.board[1].selections).toEqual([]);
  await page
    .getByRole("button", { name: "Select Storybin Training", exact: true })
    .click();
  await expect(page.locator(".visual-add-destination")).toContainText(
    "Alternate destination",
  );
  await page
    .getByRole("button", { name: "Add selected cut to Storybin", exact: true })
    .click();
  await expect
    .poll(
      async () =>
        (await (await request.get(`/api/projects/${projectId}`)).json())
          .board[1].selections[0],
    )
    .toMatchObject({ start_frame: 0, end_frame: 240 });
  const afterDestination = await (
    await request.get(`/api/projects/${projectId}`)
  ).json();
  expect(afterDestination.board[0].selections).toEqual(
    beforeDestination.board[0].selections,
  );
  await page
    .locator(".story-section")
    .nth(1)
    .getByRole("button", { name: "Remove section", exact: true })
    .click();
  await expect(
    page.getByRole("button", {
      name: "Add selected cut to Storybin",
      exact: true,
    }),
  ).toBeDisabled();
  await page.reload();
  await expect(page.locator(".clip-row")).toHaveCount(
    beforeDestination.board[0].selections.length,
  );
  expect(
    (await (await request.get(`/api/projects/${projectId}`)).json()).board[0]
      .selections,
  ).toEqual(beforeDestination.board[0].selections);
});
