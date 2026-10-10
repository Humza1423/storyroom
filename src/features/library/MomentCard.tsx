import { useDraggable } from "@dnd-kit/core";
import { CSS } from "@dnd-kit/utilities";
import { Play, GripVertical, Plus, Settings2 } from "lucide-react";
import type { Asset, Moment, Selection, Section } from "../../types";
import { timecode } from "../../lib/timecode";

export function MomentCard({
  moment,
  asset,
  onPreview,
  onAdd,
  onLabel,
}: {
  moment: Moment;
  asset?: Asset;
  onPreview: () => void;
  onAdd: () => void;
  onLabel: () => void;
}) {
  const { attributes, listeners, setNodeRef, transform, isDragging } =
    useDraggable({ id: "moment:" + moment.id, data: { moment } });
  return (
    <article
      ref={setNodeRef}
      className={"moment-card " + (isDragging ? "dragging" : "")}
      style={{ transform: CSS.Translate.toString(transform) }}
    >
      <button
        className="thumbnail"
        onClick={onPreview}
        aria-label={"Preview " + moment.description}
      >
        <img src={`/api/assets/${moment.asset_id}/thumbnail`} alt="" />
        <span className="thumb-play">
          <Play size={14} />
        </span>
        <span className="duration">
          {((moment.end_frame - moment.start_frame) / 30).toFixed(1)}s
        </span>
      </button>
      <div className="moment-meta">
        <span className="source">
          {moment.source === "ai" ? "AI MOMENT" : "YOUR FOOTAGE"}
        </span>
        <button
          className="icon drag"
          {...listeners}
          {...attributes}
          aria-label="Drag moment"
        >
          <GripVertical size={15} />
        </button>
      </div>
      <button className="moment-title" onClick={onPreview}>
        {moment.description}
      </button>
      <p className="filename" title={asset?.name}>
        {asset?.name} · {timecode(moment.start_frame)}
      </p>
      {moment.uncertainty && (
        <p className="uncertainty">{moment.uncertainty}</p>
      )}
      <div className="card-actions">
        <button className="text-button" onClick={onAdd}>
          <Plus size={13} /> Add to section
        </button>
        <button
          className="icon"
          title="Label for training"
          aria-label="Label for training"
          onClick={onLabel}
        >
          <Settings2 size={13} />
        </button>
      </div>
    </article>
  );
}
