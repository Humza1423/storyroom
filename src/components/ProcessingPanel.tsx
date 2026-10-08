import { X, Download } from "lucide-react";
import type { Job } from "../types";
export function ProcessingPanel({
  jobs,
  onClose,
  onAction,
}: {
  jobs: Job[];
  onClose: () => void;
  onAction: (id: string, action: "retry" | "cancel") => void;
}) {
  return (
    <section className="jobs-panel">
      <div className="panel-heading">
        <h2>Processing & exports</h2>
        <button
          className="icon"
          onClick={() => onClose()}
          aria-label="Close processing"
        >
          <X size={16} />
        </button>
      </div>
      {!jobs.length && <p>No work queued yet.</p>}
      {jobs.map((j) => (
        <div className="job" key={j.id}>
          <span className={"job-dot " + j.status} />
          <div>
            <strong>
              {j.kind} <small>{j.status}</small>
            </strong>
            <p>{j.message}</p>
            {j.status === "running" && <progress max={1} value={j.progress} />}
          </div>
          {["failed", "cancelled"].includes(j.status) && (
            <button
              className="secondary"
              onClick={() => onAction(j.id, "retry")}
            >
              Retry
            </button>
          )}
          {["running", "queued"].includes(j.status) && (
            <button
              className="text-button"
              onClick={() => onAction(j.id, "cancel")}
            >
              Cancel
            </button>
          )}
          {j.result?.url && (
            <a className="secondary" href={j.result.url}>
              <Download size={13} />{" "}
              {j.kind === "export" ? "Resolve XML" : "Preview MP4"}
            </a>
          )}
          {j.kind === "export" && j.status === "done" && (
            <a
              className="text-button"
              href={`/api/jobs/${j.id}/download?format=json`}
            >
              Story notes
            </a>
          )}
        </div>
      ))}
    </section>
  );
}
