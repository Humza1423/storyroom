import type { VisualCandidate } from "../../types";
import { createVisualRange, type VisualRange } from "./visualRange";

/** A worker may improve a proposal's evidence, but never owns the user's draft. */
export function refreshVisualEvidence(
  current: VisualRange,
  updates: VisualCandidate[],
  sourceFrames: number,
): VisualRange {
  const candidate = updates.find(
    (update) => update.id === current.candidate.id,
  );
  if (!candidate || candidate.asset_id !== current.candidate.asset_id)
    return current;
  const proposed = createVisualRange(candidate, sourceFrames);
  if (!proposed) return current;
  return {
    ...current,
    candidate,
    contextStart: Math.min(current.contextStart, proposed.contextStart),
    contextEnd: Math.max(current.contextEnd, proposed.contextEnd),
  };
}
