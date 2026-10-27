import type { Job, VisualCandidate } from "../../types";

export type ActivityInspectionJob = Pick<Job, "id" | "status" | "message">;

const seconds = (frames: number) => Number((frames / 30).toFixed(2)).toString();

/** Duration support, observed extent and worker outcome are independent facts. */
export function activityPresentation(
  candidate: VisualCandidate,
  job?: ActivityInspectionJob,
  selectedFrames = candidate.end_frame - candidate.start_frame,
) {
  const activity = candidate.activity;
  if (!activity) return null;
  const available = activity.end_frame - activity.start_frame;
  const stopped =
    !activity.complete && !!job && ["failed", "cancelled"].includes(job.status);
  const checking =
    !activity.complete && !!job && ["queued", "running"].includes(job.status);
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
    } else if (activity.complete) {
      duration = `Requested ${requested} seconds. Found ${found} seconds of this activity. ${selectedFrames === available ? `The full ${found} seconds are selected.` : `${selected} seconds selected.`}`;
    } else {
      duration = `Requested ${requested} seconds. ${found} seconds confirmed${stopped ? "" : " so far"}. ${selected} seconds selected. Requested duration is not yet confirmed.`;
    }
  }
  return {
    duration,
    inspection: activity.complete
      ? "Activity extent inspected. Review the movement’s beginning and finish."
      : stopped
        ? `Inspection stopped${job?.status === "cancelled" ? " (cancelled)" : ""}. Confirmed footage remains available; the activity’s beginning or end is unresolved.${job?.message ? ` ${job.message}` : ""}`
        : checking
          ? "Checking more footage. The activity’s beginning or end is still unresolved."
          : "Activity partially inspected. Its beginning or end is unresolved.",
  };
}
