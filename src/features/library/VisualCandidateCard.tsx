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
        aria-label={`Preview & adjust visual match ${candidate.rank}`}
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
        Preview & adjust
      </button>
      <p className="filename" title={asset?.name}>
        {asset?.name} · {(candidate.start_frame / 30).toFixed(1)}–
        {(candidate.end_frame / 30).toFixed(1)}s
      </p>
      <div className="card-actions">
        <button className="text-button" onClick={onAdd}>
          <Plus size={13} /> Quick add to Storybin
        </button>
      </div>
    </article>
  );
}
