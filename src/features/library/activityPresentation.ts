import type { Job, VisualCandidate } from "../../types";

export type ActivityInspectionJob = Pick<Job, "id" | "status" | "message">;

const seconds = (frames: number) => Number((frames / 30).toFixed(2)).toString();

function inspectionReason(message: string) {
  const reasons: Record<string, string> = {
    "Inspection is unrelated to its retrieved anchor":
      "The next inspection found a different moment, so the original footage was kept.",
    "Inspection seconds outside supplied video":
      "The AI returned timing outside the video it was shown.",
    "No verified continuity across this activity boundary.":
      "Could not confirm that the next footage continues this activity.",
    "Activity inspection made no progress; retained partial activity.":
      "Could not establish more of this activity. Your confirmed footage was kept.",
  };
  return reasons[message] ?? message;
}

/** Duration support, observed extent and worker outcome are independent facts. */
export function activityPresentation(
  candidate: VisualCandidate,
  job?: ActivityInspectionJob,
  selectedFrames = candidate.end_frame - candidate.start_frame,
) {
  const activity = candidate.activity;
  if (!activity) return null;
  const available = activity.end_frame - activity.start_frame;
  const boundaryConflict =
    activity.boundary_conflict_before || activity.boundary_conflict_after;
  const complete = activity.complete && !boundaryConflict;
  const stopped =
    !complete && !!job && ["failed", "cancelled"].includes(job.status);
  const checking =
    !complete && !!job && ["queued", "running"].includes(job.status);
  let duration: string | null = null;
  if (activity.requested_frames !== null) {
    const requested = seconds(activity.requested_frames);
    const selected = seconds(selectedFrames);
    const found = seconds(available);
    if (available >= activity.requested_frames) {
      duration =
        selectedFrames === activity.requested_frames
          ? `Requested ${requested} seconds. ${selected} seconds selected.`
          : `Requested ${requested} seconds. ${requested} seconds supported. ${selected} seconds selected.`;
    } else if (complete) {
      duration = `Requested ${requested} seconds. Found ${found} seconds of this activity. ${selectedFrames === available ? `The full ${found} seconds are selected.` : `${selected} seconds selected.`}`;
    } else {
      duration = `Requested ${requested} seconds. ${found} seconds confirmed${stopped ? "" : " so far"}. ${selected} seconds selected. Requested duration is not yet confirmed.`;
    }
  }
  const inspection = complete
    ? "Activity extent inspected. Review the movement’s beginning and finish."
    : stopped
      ? `Inspection stopped${job?.status === "cancelled" ? " (cancelled)" : ""}. Confirmed footage remains available; the activity’s beginning or end is unresolved.${job?.message ? ` ${inspectionReason(job.message)}` : ""}`
      : checking
        ? "Checking more footage. The activity’s beginning or end is still unresolved."
        : "Activity partially inspected. Its beginning or end is unresolved.";
  return {
    duration,
    inspection: `${boundaryConflict ? "Action found; its beginning or end needs another look. " : ""}${inspection}`,
  };
}
