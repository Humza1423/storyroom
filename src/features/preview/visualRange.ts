import type { VisualCandidate } from "../../types";

export type VisualRange = {
  candidate: VisualCandidate;
  contextStart: number;
  contextEnd: number;
  selectedStart: number;
  selectedEnd: number;
};

/** Reject malformed activity metadata rather than playing outside the source. */
export function activityBounds(
  candidate: VisualCandidate,
  frames: number,
): { start: number; end: number } | null {
  const activity = candidate.activity;
  if (
    !activity ||
    !Number.isInteger(frames) ||
    frames < 1 ||
    !Number.isInteger(activity.start_frame) ||
    !Number.isInteger(activity.end_frame) ||
    activity.start_frame < 0 ||
    activity.end_frame > frames ||
    activity.start_frame >= activity.end_frame ||
    activity.start_frame > candidate.start_frame ||
    activity.end_frame < candidate.end_frame
  )
    return null;
  return { start: activity.start_frame, end: activity.end_frame };
}

export function createVisualRange(
  candidate: VisualCandidate,
  frames: number,
): VisualRange | null {
  if (
    !Number.isInteger(frames) ||
    !Number.isInteger(candidate.start_frame) ||
    !Number.isInteger(candidate.end_frame) ||
    frames < 1 ||
    candidate.start_frame < 0 ||
    candidate.start_frame >= candidate.end_frame ||
    candidate.end_frame > frames
  )
    return null;
  const activity = activityBounds(candidate, frames);
  if (candidate.activity && !activity) return null;
  return {
    candidate,
    contextStart: activity?.start ?? Math.max(0, candidate.start_frame - 30),
    contextEnd: activity?.end ?? Math.min(frames, candidate.end_frame + 30),
    selectedStart: candidate.start_frame,
    selectedEnd: candidate.end_frame,
  };
}

/** Snapshot the established range; subsequent worker updates never move this cut. */
export function selectEstablishedActivity(range: VisualRange): VisualRange {
  return {
    ...range,
    selectedStart: range.candidate.activity?.start_frame ?? range.contextStart,
    selectedEnd: range.candidate.activity?.end_frame ?? range.contextEnd,
  };
}

export function moveVisualHandle(
  range: VisualRange,
  handle: "in" | "out",
  frame: number,
): VisualRange {
  if (!Number.isFinite(frame)) return range;
  const target = Math.round(frame);
  return handle === "in"
    ? {
        ...range,
        selectedStart: Math.max(
          range.contextStart,
          Math.min(target, range.selectedEnd - 1),
        ),
      }
    : {
        ...range,
        selectedEnd: Math.max(
          range.selectedStart + 1,
          Math.min(target, range.contextEnd),
        ),
      };
}
