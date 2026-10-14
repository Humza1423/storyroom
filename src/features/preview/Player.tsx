import { useEffect, useRef, type RefObject } from "react";
import { Film } from "lucide-react";
import type { Moment, Selection, VisualCandidate } from "../../types";
export function Player({
  preview,
  video,
  advance,
}: {
  preview: Moment | Selection | VisualCandidate | null;
  video: RefObject<HTMLVideoElement | null>;
  advance: () => void;
}) {
  const advanced = useRef(false);
  useEffect(() => {
    advanced.current = false;
  }, [preview]);
  function finishRange() {
    if (advanced.current) return;
    advanced.current = true;
    advance();
  }
  return (
    <div className="player">
      {preview ? (
        <video
          ref={video}
          key={preview.asset_id}
          controls
          preload="auto"
          playsInline
          src={`/api/assets/${preview.asset_id}/proxy`}
          onPlay={() => {
            advanced.current = false;
          }}
          onTimeUpdate={() => {
            if (
              video.current &&
              video.current.currentTime >= preview.end_frame / 30
            )
              finishRange();
          }}
          onEnded={finishRange}
        />
      ) : (
        <div>
          <Film size={32} />
          <p>
            Select a moment
            <br />
            to take a closer look.
          </p>
        </div>
      )}
    </div>
  );
}
