import type { RefObject } from "react";
import { Film } from "lucide-react";
import type { Moment, Selection } from "../../types";
export function Player({
  preview,
  video,
  advance,
}: {
  preview: Moment | Selection | null;
  video: RefObject<HTMLVideoElement | null>;
  advance: () => void;
}) {
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
          onTimeUpdate={() => {
            if (
              video.current &&
              video.current.currentTime >= preview.end_frame / 30
            )
              advance();
          }}
          onEnded={advance}
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
