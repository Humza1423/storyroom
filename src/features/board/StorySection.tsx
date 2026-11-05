import React from "react";
import { useDroppable } from "@dnd-kit/core";
import { ArrowUp, ArrowDown, X, Plus, Pencil } from "lucide-react";
import type { Section } from "../../types";

export function StorySection({
  section,
  index,
  active,
  onActivate,
  onRename,
  onRemove,
  onMove,
  children,
}: {
  section: Section;
  index: number;
  active: boolean;
  onActivate: () => void;
  onRename: () => void;
  onRemove: () => void;
  onMove: (n: number) => void;
  children: React.ReactNode;
}) {
  const { setNodeRef, isOver } = useDroppable({ id: "section:" + section.id });
  const duration =
    section.selections.reduce((n, c) => n + c.end_frame - c.start_frame, 0) /
    30;
  return (
    <section
      ref={setNodeRef}
      onClick={onActivate}
      className={
        "story-section " + (active ? "active " : "") + (isOver ? "over" : "")
      }
    >
      <header style={{ flexWrap: "wrap" }}>
        <span className="section-number">
          {String(index + 1).padStart(2, "0")}
        </span>
        <button
          type="button"
          className="section-heading"
          style={{ flex: "1 1 140px", overflowWrap: "anywhere" }}
          aria-label={`Select Storybin ${section.title}`}
          aria-pressed={active}
          onClick={(event) => {
            event.stopPropagation();
            onActivate();
          }}
        >
          <strong>{section.title}</strong>
          <small>
            {section.purpose || "Define what this part of the story should do."}
          </small>
        </button>
        <span className="section-length">{duration.toFixed(1)}s</span>
        <button
          type="button"
          className="icon"
          title="Edit Storybin"
          aria-label={`Edit Storybin ${section.title}`}
          onClick={(event) => {
            event.stopPropagation();
            onRename();
          }}
        >
          <Pencil size={13} />
        </button>
        <button
          className="icon"
          onClick={(e) => {
            e.stopPropagation();
            onMove(-1);
          }}
          aria-label="Move section earlier"
        >
          <ArrowUp size={13} />
        </button>
        <button
          className="icon"
          onClick={(e) => {
            e.stopPropagation();
            onMove(1);
          }}
          aria-label="Move section later"
        >
          <ArrowDown size={13} />
        </button>
        <button
          className="icon"
          onClick={(e) => {
            e.stopPropagation();
            onRemove();
          }}
          aria-label="Remove section"
        >
          <X size={14} />
        </button>
      </header>
      {children}
      {!section.selections.length && (
        <div className="section-drop">
          <Plus size={17} />
          <span>Drop a moment here, or add one from your footage</span>
        </div>
      )}
    </section>
  );
}
