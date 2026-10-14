import { test, expect } from "@playwright/test";
import { moveSelection } from "../src/features/board/changes";
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
