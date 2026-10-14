import { useEffect, useRef, useState, type RefObject } from "react";
import { Film, Pause, Play } from "lucide-react";
import type { Moment, Selection, VisualCandidate } from "../../types";

export function Player({
  preview,
  video,
  advance,
  assembly,
}: {
  preview: Moment | Selection | VisualCandidate | null;
  video: RefObject<HTMLVideoElement | null>;
  advance: () => void;
  assembly: boolean;
}) {
  const advanced = useRef(false);
  const prepared = useRef(false);
  const playAfterSeek = useRef(false);
  const [elapsed, setElapsed] = useState(0);
  const [playing, setPlaying] = useState(false);
  const start = (preview?.start_frame ?? 0) / 30;
  const duration = preview ? (preview.end_frame - preview.start_frame) / 30 : 0;

  useEffect(() => {
    advanced.current = false;
    prepared.current = false;
    playAfterSeek.current = assembly;
    setElapsed(0);
    setPlaying(false);
    const element = video.current;
    if (element?.readyState && preview) prepare(element);
    // The video element is keyed by the selected range below. Its metadata
    // callback is the normal path; this handles cached metadata as well.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [preview?.asset_id, preview?.start_frame, preview?.end_frame, preview?.id, assembly]);

  function prepare(element: HTMLVideoElement) {
    if (!preview || prepared.current) return;
    if (Math.abs(element.currentTime - start) < 0.025) {
      prepared.current = true;
      if (playAfterSeek.current) {
        playAfterSeek.current = false;
        element.play().catch(() => setPlaying(false));
      }
    } else {
      element.currentTime = start;
    }
  }

  function finishRange() {
    if (advanced.current) return;
    advanced.current = true;
    setElapsed(duration);
    video.current?.pause();
    advance();
  }

  return (
    <div className="player assembly-player">
      {preview ? (
        <>
          <video
            ref={video}
            key={`${preview.asset_id}:${preview.start_frame}:${preview.end_frame}:${preview.id}`}
            controls={false}
            preload="auto"
            playsInline
            src={`/api/assets/${preview.asset_id}/proxy`}
            onLoadedMetadata={(event) => prepare(event.currentTarget)}
            onSeeked={(event) => {
              if (!prepared.current) {
                prepared.current = true;
                if (playAfterSeek.current) {
                  playAfterSeek.current = false;
                  event.currentTarget.play().catch(() => setPlaying(false));
                }
              }
            }}
            onPlay={() => setPlaying(true)}
            onPause={() => setPlaying(false)}
            onTimeUpdate={() => {
              if (!prepared.current || !video.current) return;
              const time = video.current.currentTime;
              setElapsed(Math.max(0, Math.min(duration, time - start)));
              if (time >= preview.end_frame / 30 - 1 / 120) finishRange();
            }}
            onEnded={finishRange}
          />
          <div className="assembly-controls">
              <button
                type="button"
                aria-label={playing ? "Pause selected range" : elapsed >= duration - 0.05 ? "Replay selected range" : "Play selected range"}
                onClick={() => {
                  const element = video.current;
                  if (!element) return;
                  if (!element.paused) {
                    element.pause();
                  } else if (elapsed >= duration - 0.05) {
                    advanced.current = false;
                    prepared.current = false;
                    playAfterSeek.current = true;
                    setElapsed(0);
                    element.currentTime = start;
                  } else {
                    element.play().catch(() => setPlaying(false));
                  }
                }}
              >
                {playing ? <Pause size={15} /> : <Play size={15} />}
              </button>
              <input
                aria-label="Position within selected clip"
                type="range"
                min={0}
                max={duration}
                step={1 / 30}
                value={elapsed}
                onChange={(event) => {
                  if (video.current) video.current.currentTime = start + Number(event.target.value);
                  setElapsed(Number(event.target.value));
                }}
              />
              <span>{elapsed.toFixed(1)} / {duration.toFixed(1)}s</span>
          </div>
        </>
      ) : (
        <div>
          <Film size={32} />
          <p>Select a moment<br />to take a closer look.</p>
        </div>
      )}
    </div>
  );
}
