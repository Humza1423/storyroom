import { useDraggable } from "@dnd-kit/core";
import { CSS } from "@dnd-kit/utilities";
import { GripVertical, Play, Plus } from "lucide-react";
import type { Asset, VisualCandidate } from "../../types";

export function VisualCandidateCard({
  candidate,
  asset,
  onPreview,
  onAdd,
}: {
  candidate: VisualCandidate;
  asset?: Asset;
  onPreview: () => void;
  onAdd: () => void;
}) {
  const activity = candidate.activity;
  const previewLabel = activity ? "Preview suggested cut" : "Preview & adjust";
  const { attributes, listeners, setNodeRef, transform, isDragging } =
    useDraggable({
      id: "visual:" + candidate.id,
      data: { visualCandidate: candidate },
    });
  return (
    <article
      ref={setNodeRef}
      className={"moment-card " + (isDragging ? "dragging" : "")}
      style={{ transform: CSS.Translate.toString(transform) }}
    >
      <button
        className="thumbnail"
        onClick={onPreview}
        aria-label={`${previewLabel} visual match ${candidate.rank}`}
      >
        <img src={`/api/assets/${candidate.asset_id}/thumbnail`} alt="" />
        <span className="thumb-play">
          <Play size={14} />
        </span>
        <span className="duration">
          {((candidate.end_frame - candidate.start_frame) / 30).toFixed(1)}s
        </span>
      </button>
      <div className="moment-meta">
        <span className="source">VISUAL MATCH · #{candidate.rank}</span>
        <button
          className="icon drag"
          {...listeners}
          {...attributes}
          aria-label="Drag visual match"
        >
          <GripVertical size={15} />
        </button>
      </div>
      <button className="moment-title" onClick={onPreview}>
        {previewLabel}
      </button>
      <p className="filename" title={asset?.name}>
        {asset?.name} · {(candidate.start_frame / 30).toFixed(1)}–
        {(candidate.end_frame / 30).toFixed(1)}s
      </p>
      {activity && (
        <p className="filename">
          Activity · {(activity.start_frame / 30).toFixed(1)}–
          {(activity.end_frame / 30).toFixed(1)}s ·{" "}
          {((activity.end_frame - activity.start_frame) / 30).toFixed(1)}s
          {activity.complete ? " · fully inspected" : " · partially inspected"}
          {activity.requested_frames !== null &&
            (activity.duration_fulfilled
              ? ` · ${(activity.requested_frames / 30).toFixed(1)}s requested cut`
              : activity.complete
                ? ` · Less than ${(activity.requested_frames / 30).toFixed(1)}s available`
                : " · Requested duration not yet confirmed")}
        </p>
      )}
      <div className="card-actions">
        <button className="text-button" onClick={onAdd}>
          <Plus size={13} /> Quick add to Storybin
        </button>
      </div>
    </article>
  );
}
