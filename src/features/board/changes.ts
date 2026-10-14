import type { Section } from "../../types";

/** Move a placement, never identify it by its reusable source/moment ID. */
export function moveSelection(
  board: Section[],
  selectionId: string,
  sectionId: string,
  beforeId: string,
): Section[] {
  const next = structuredClone(board);
  const from = next.find((s) => s.selections.some((c) => c.id === selectionId));
  const to = next.find((s) => s.id === sectionId);
  if (!from || !to) return next;
  const index = from.selections.findIndex((c) => c.id === selectionId);
  const [clip] = from.selections.splice(index, 1);
  const insert = to.selections.findIndex((c) => c.id === beforeId);
  to.selections.splice(insert < 0 ? to.selections.length : insert, 0, clip);
  return next;
}
