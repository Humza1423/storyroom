import { test, expect } from "@playwright/test";
import { moveSelection } from "../src/features/board/changes";
import { canAdvancePlaybackRange } from "../src/features/preview/playback";
import type { Section } from "../src/types";

test("moving duplicate source placements preserves independent ranges and input", () => {
  const board: Section[] = [
    {
      id: "a",
      title: "A",
      purpose: "",
      selections: [
        {
          id: "first",
          asset_id: "source",
          moment_id: "moment",
          start_frame: 0,
          end_frame: 10,
          note: "",
        },
        {
          id: "second",
          asset_id: "source",
          moment_id: "moment",
          start_frame: 20,
          end_frame: 30,
          note: "",
        },
      ],
    },
    { id: "b", title: "B", purpose: "", selections: [] },
  ];
  const moved = moveSelection(board, "second", "b", "section:b");
  expect(moved[0].selections.map((c) => c.id)).toEqual(["first"]);
  expect(moved[1].selections[0].start_frame).toBe(20);
  expect(board[0].selections).toHaveLength(2);
  expect(moveSelection(board, "missing", "b", "")).toEqual(board);
});

test("a stale media event cannot advance a newer playback range", () => {
  const oldVideo = {};
  const currentVideo = {};
  const completion = {
    eventRangeKey: "assembly:clip-1",
    activeRangeKey: "assembly:clip-2",
    eventVideo: oldVideo,
    activeVideo: currentVideo,
    alreadyAdvanced: false,
  };

  expect(canAdvancePlaybackRange(completion)).toBe(false);
  expect(
    canAdvancePlaybackRange({
      ...completion,
      eventRangeKey: "assembly:clip-2",
      activeRangeKey: "assembly:clip-2",
    }),
  ).toBe(false);
  expect(
    canAdvancePlaybackRange({
      eventRangeKey: "assembly:clip-2",
      activeRangeKey: "assembly:clip-2",
      eventVideo: currentVideo,
      activeVideo: currentVideo,
      alreadyAdvanced: false,
    }),
  ).toBe(true);
  expect(
    canAdvancePlaybackRange({
      eventRangeKey: "assembly:clip-2",
      activeRangeKey: "assembly:clip-2",
      eventVideo: currentVideo,
      activeVideo: currentVideo,
      alreadyAdvanced: true,
    }),
  ).toBe(false);
});
