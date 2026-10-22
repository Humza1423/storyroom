import type { VisualCandidate } from "../../types";

export type VisualRange = {
  candidate: VisualCandidate;
  contextStart: number;
  contextEnd: number;
  selectedStart: number;
  selectedEnd: number;
};

export function createVisualRange(candidate: VisualCandidate, frames: number): VisualRange | null {
  if (!Number.isInteger(frames) || !Number.isInteger(candidate.start_frame) ||
      !Number.isInteger(candidate.end_frame) || frames < 1 ||
      candidate.start_frame < 0 || candidate.start_frame >= candidate.end_frame ||
      candidate.end_frame > frames) return null;
  return {
    candidate,
    contextStart: Math.max(0, candidate.start_frame - 30),
    contextEnd: Math.min(frames, candidate.end_frame + 30),
    selectedStart: candidate.start_frame,
    selectedEnd: candidate.end_frame,
  };
}

export function moveVisualHandle(range: VisualRange, handle: "in" | "out", frame: number): VisualRange {
  if (!Number.isFinite(frame)) return range;
  const target = Math.round(frame);
  return handle === "in"
    ? { ...range, selectedStart: Math.max(range.contextStart, Math.min(target, range.selectedEnd - 1)) }
    : { ...range, selectedEnd: Math.max(range.selectedStart + 1, Math.min(target, range.contextEnd)) };
}
