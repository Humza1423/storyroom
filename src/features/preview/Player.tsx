import { useEffect, useRef, useState, type RefObject } from "react";
import { Film, Pause, Play } from "lucide-react";
import type { Moment, Selection, VisualCandidate } from "../../types";
import { moveVisualHandle, type VisualRange } from "./visualRange";

export function Player({
  preview,
  video,
  advance,
  assembly,
  visualRange,
  onVisualRangeChange,
}: {
  preview: Moment | Selection | VisualCandidate | null;
  video: RefObject<HTMLVideoElement | null>;
  advance: () => void;
  assembly: boolean;
  visualRange?: VisualRange | null;
  onVisualRangeChange?: (range: VisualRange) => void;
}) {
  const advanced = useRef(false);
  const prepared = useRef(false);
  const playAfterSeek = useRef(false);
  const [elapsed, setElapsed] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [playhead, setPlayhead] = useState(0);
  const startFrame = visualRange?.selectedStart ?? preview?.start_frame ?? 0;
  const endFrame = visualRange?.selectedEnd ?? preview?.end_frame ?? 0;
  const start = startFrame / 30;
  const duration = Math.max(0, (endFrame - startFrame) / 30);

  useEffect(() => {
    advanced.current = false;
    prepared.current = false;
    playAfterSeek.current = assembly;
    setElapsed(0);
    setPlayhead(startFrame);
    setPlaying(false);
    const element = video.current;
    if (element?.readyState && preview) prepare(element);
    // The video element is keyed by the original range below. Its metadata
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

  return <>
    <div className={`player assembly-player${preview ? "" : " empty-player"}`}>
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
            onPlay={() => { advanced.current = false; setPlaying(true); }}
            onPause={() => setPlaying(false)}
            onTimeUpdate={() => {
              if (!prepared.current || !video.current) return;
              const time = video.current.currentTime;
              setPlayhead(Math.round(time * 30));
              setElapsed(Math.max(0, Math.min(duration, time - start)));
              if (!video.current.paused && time >= endFrame / 30 - 1 / 120) finishRange();
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
                  } else if (element.currentTime < start - 1 / 120 ||
                             element.currentTime >= endFrame / 30 - 1 / 120 ||
                             elapsed >= duration - 0.05) {
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
                  setPlayhead(Math.round((start + Number(event.target.value)) * 30));
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
    {preview && visualRange && onVisualRangeChange && (
      <div className="visual-range-editor" aria-label="Preview and adjust visual match">
        <div className="visual-range-labels">
          <span>AI match range · approximate</span>
          <span>{(visualRange.candidate.start_frame / 30).toFixed(1)}–{(visualRange.candidate.end_frame / 30).toFixed(1)}s</span>
        </div>
        <p>Nearby footage · not verified. Scrub to check what happens before and after the match.</p>
        <div className="visual-context-track" aria-hidden="true">
          <div className="visual-match-band" style={{
            left: `${100 * (visualRange.candidate.start_frame - visualRange.contextStart) / (visualRange.contextEnd - visualRange.contextStart)}%`,
            width: `${100 * (visualRange.candidate.end_frame - visualRange.candidate.start_frame) / (visualRange.contextEnd - visualRange.contextStart)}%`,
          }} />
          <div className="visual-selected-band" style={{
            left: `${100 * (visualRange.selectedStart - visualRange.contextStart) / (visualRange.contextEnd - visualRange.contextStart)}%`,
            width: `${100 * (visualRange.selectedEnd - visualRange.selectedStart) / (visualRange.contextEnd - visualRange.contextStart)}%`,
          }} />
        </div>
        <label className="visual-range-control">Scrub nearby footage · {(playhead / 30).toFixed(1)}s
          <input aria-label="Scrub nearby footage" type="range" min={visualRange.contextStart} max={visualRange.contextEnd - 1} step="1"
            value={Math.max(visualRange.contextStart, Math.min(playhead, visualRange.contextEnd - 1))}
            onChange={(event) => {
              const frame = Number(event.target.value);
              video.current?.pause();
              if (video.current) video.current.currentTime = frame / 30;
              setPlayhead(frame);
            }} />
        </label>
        <div className="visual-range-labels"><span>Your selected cut</span><span>{(visualRange.selectedStart / 30).toFixed(1)}–{(visualRange.selectedEnd / 30).toFixed(1)}s</span></div>
        <label className="visual-range-control">In · frame {visualRange.selectedStart}
          <input aria-label="Selected cut in frame" type="range" min={visualRange.contextStart} max={visualRange.selectedEnd - 1} step="1"
            value={visualRange.selectedStart} onChange={(event) => {
              video.current?.pause();
              onVisualRangeChange(moveVisualHandle(visualRange, "in", Number(event.target.value)));
            }} />
        </label>
        <label className="visual-range-control">Out · frame {visualRange.selectedEnd} (exclusive)
          <input aria-label="Selected cut out frame" type="range" min={visualRange.selectedStart + 1} max={visualRange.contextEnd} step="1"
            value={visualRange.selectedEnd} onChange={(event) => {
              video.current?.pause();
              onVisualRangeChange(moveVisualHandle(visualRange, "out", Number(event.target.value)));
            }} />
        </label>
      </div>
    )}
  </>;
}
