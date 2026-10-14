import { useSortable } from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import { GripVertical, ArrowUp, ArrowDown, X } from "lucide-react";
import type { Asset, Moment, Selection, Section } from "../../types";
import { timecode } from "../../lib/timecode";

export function ClipRow({
  clip,
  asset,
  active,
  onSelect,
  onRemove,
  onMove,
}: {
  clip: Selection;
  asset?: Asset;
  active: boolean;
  onSelect: () => void;
  onRemove: () => void;
  onMove: (n: number) => void;
}) {
  const { attributes, listeners, setNodeRef, transform, transition } =
    useSortable({ id: clip.id, data: { selection: clip } });
  return (
    <div
      ref={setNodeRef}
      style={{ transform: CSS.Transform.toString(transform), transition }}
      className={"clip-row " + (active ? "selected" : "")}
    >
      <button
        className="icon drag"
        {...attributes}
        {...listeners}
        aria-label="Reorder clip"
      >
        <GripVertical size={14} />
      </button>
      <button className="clip-main" onClick={onSelect}>
        <img src={`/api/assets/${clip.asset_id}/thumbnail`} alt="" />
        <span>
          <strong>{asset?.name}</strong>
          <small>
            {timecode(clip.start_frame)} → {timecode(clip.end_frame)}
          </small>
        </span>
      </button>
      <button
        className="icon tiny"
        onClick={() => onMove(-1)}
        aria-label="Move clip earlier"
      >
        <ArrowUp size={12} />
      </button>
      <button
        className="icon tiny"
        onClick={() => onMove(1)}
        aria-label="Move clip later"
      >
        <ArrowDown size={12} />
      </button>
      <button className="icon" onClick={onRemove} aria-label="Remove clip">
        <X size={13} />
      </button>
    </div>
  );
}
