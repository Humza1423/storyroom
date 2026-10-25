import { useEffect, useRef, useState, type RefObject } from "react";
import { Film, Pause, Play } from "lucide-react";
import type { Moment, Selection, VisualCandidate } from "../../types";
import {
  activityBounds,
  moveVisualHandle,
  type VisualRange,
} from "./visualRange";
import { canAdvancePlaybackRange } from "./playback";

export function Player({
  preview,
  video,
  advance,
  assembly,
  visualRange,
  sourceFrames,
  onVisualRangeChange,
}: {
  preview: Moment | Selection | VisualCandidate | null;
  video: RefObject<HTMLVideoElement | null>;
  advance: () => void;
  assembly: boolean;
  visualRange?: VisualRange | null;
  sourceFrames: number;
  onVisualRangeChange?: (range: VisualRange) => void;
}) {
  const advanced = useRef(false);
  const prepared = useRef(false);
  const playAfterSeek = useRef(false);
  const activeRangeKey = useRef("");
  const [elapsed, setElapsed] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [playhead, setPlayhead] = useState(0);
  const [review, setReview] = useState<{
    id: string;
    mode: "activity" | "source";
  } | null>(null);
  const activity = visualRange
    ? activityBounds(visualRange.candidate, sourceFrames)
    : null;
  const reviewingFullSource =
    !!visualRange &&
    review?.id === visualRange.candidate.id &&
    review.mode === "source";
  const reviewingActivity =
    !!activity &&
    !!visualRange &&
    review?.id === visualRange.candidate.id &&
    review.mode === "activity";
  const reviewing = reviewingFullSource || reviewingActivity;
  const playbackLabel = reviewingFullSource
    ? "full source video"
    : reviewingActivity
      ? "activity"
      : "selected range";
  const contextStart = reviewingFullSource
    ? 0
    : reviewingActivity
      ? activity!.start
      : (visualRange?.contextStart ?? 0);
  const contextEnd = reviewingFullSource
    ? sourceFrames
    : reviewingActivity
      ? activity!.end
      : (visualRange?.contextEnd ?? sourceFrames);
  const startFrame = reviewing
    ? contextStart
    : (visualRange?.selectedStart ?? preview?.start_frame ?? 0);
  const endFrame = reviewing
    ? contextEnd
    : (visualRange?.selectedEnd ?? preview?.end_frame ?? 0);
  const start = startFrame / 30;
  const duration = Math.max(0, (endFrame - startFrame) / 30);
  const rangeKey = preview
    ? `${assembly ? "assembly" : "preview"}:${preview.asset_id}:${preview.id}:${startFrame}:${endFrame}:${reviewingFullSource ? "full-source" : reviewingActivity ? "activity" : "selected-range"}`
    : "";

  useEffect(() => {
    setReview(null);
  }, [preview?.asset_id, preview?.id]);

  useEffect(() => {
    activeRangeKey.current = rangeKey;
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
    return () => {
      if (activeRangeKey.current === rangeKey) activeRangeKey.current = "";
    };
  }, [
    preview?.asset_id,
    preview?.start_frame,
    preview?.end_frame,
    preview?.id,
    assembly,
    rangeKey,
  ]);

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

  function finishRange(element: HTMLVideoElement) {
    if (
      !canAdvancePlaybackRange({
        eventRangeKey: rangeKey,
        activeRangeKey: activeRangeKey.current,
        eventVideo: element,
        activeVideo: video.current,
        alreadyAdvanced: advanced.current,
      })
    )
      return;
    advanced.current = true;
    setElapsed(duration);
    video.current?.pause();
    advance();
  }

  return (
    <>
      <div
        className={`player assembly-player${preview ? "" : " empty-player"}`}
      >
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
              onPlay={(event) => {
                if (
                  !canAdvancePlaybackRange({
                    eventRangeKey: rangeKey,
                    activeRangeKey: activeRangeKey.current,
                    eventVideo: event.currentTarget,
                    activeVideo: video.current,
                    alreadyAdvanced: false,
                  })
                )
                  return;
                advanced.current = false;
                setPlaying(true);
              }}
              onPause={(event) => {
                if (
                  event.currentTarget === video.current &&
                  activeRangeKey.current === rangeKey
                )
                  setPlaying(false);
              }}
              onTimeUpdate={(event) => {
                const element = event.currentTarget;
                if (
                  !prepared.current ||
                  element !== video.current ||
                  activeRangeKey.current !== rangeKey
                )
                  return;
                const time = element.currentTime;
                setPlayhead(Math.round(time * 30));
                setElapsed(Math.max(0, Math.min(duration, time - start)));
                if (!element.paused && time >= endFrame / 30 - 1 / 120)
                  finishRange(element);
              }}
              onEnded={(event) => finishRange(event.currentTarget)}
            />
            <div className="assembly-controls">
              <button
                type="button"
                aria-label={
                  playing
                    ? `Pause ${playbackLabel}`
                    : elapsed >= duration - 0.05
                      ? `Replay ${playbackLabel}`
                      : `Play ${playbackLabel}`
                }
                onClick={() => {
                  const element = video.current;
                  if (!element) return;
                  if (!element.paused) {
                    element.pause();
                  } else if (
                    element.currentTime < start - 1 / 120 ||
                    element.currentTime >= endFrame / 30 - 1 / 120 ||
                    elapsed >= duration - 0.05
                  ) {
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
                aria-label={
                  reviewingFullSource
                    ? "Position in full source video"
                    : reviewingActivity
                      ? "Position in activity"
                      : "Position within selected clip"
                }
                type="range"
                min={0}
                max={duration}
                step={1 / 30}
                value={elapsed}
                onChange={(event) => {
                  if (video.current)
                    video.current.currentTime =
                      start + Number(event.target.value);
                  setElapsed(Number(event.target.value));
                  setPlayhead(
                    Math.round((start + Number(event.target.value)) * 30),
                  );
                }}
              />
              <span>
                {elapsed.toFixed(1)} / {duration.toFixed(1)}s
              </span>
            </div>
          </>
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
      {preview && visualRange && onVisualRangeChange && (
        <div
          className="visual-range-editor"
          aria-label="Preview and adjust visual match"
        >
          <div className="visual-range-labels">
            <span>AI match range · approximate</span>
            <span>
              {(visualRange.candidate.start_frame / 30).toFixed(1)}–
              {(visualRange.candidate.end_frame / 30).toFixed(1)}s
            </span>
          </div>
          <p>
            {reviewingFullSource
              ? "Full source video · not verified. Review the entire imported clip; the AI match and your selected cut stay marked below."
              : reviewingActivity
                ? visualRange.candidate.activity?.complete
                  ? "Activity range · AI identified. Review the activity around the suggested cut."
                  : "Activity range · partially inspected. Its beginning or end may still be unresolved."
                : "Nearby footage · not verified. Scrub to check what happens before and after the match."}
          </p>
          {activity && (
            <button
              type="button"
              className="secondary full-source-toggle"
              onClick={() => {
                video.current?.pause();
                setReview(
                  reviewingActivity
                    ? null
                    : { id: visualRange.candidate.id, mode: "activity" },
                );
              }}
            >
              {reviewingActivity
                ? "Return to suggested cut"
                : "Review activity"}
            </button>
          )}
          <button
            type="button"
            className="secondary full-source-toggle"
            onClick={() => {
              video.current?.pause();
              setReview(
                reviewingFullSource
                  ? null
                  : { id: visualRange.candidate.id, mode: "source" },
              );
            }}
          >
            {reviewingFullSource
              ? "Return to match preview"
              : "View full source video"}
          </button>
          <div className="visual-context-track" aria-hidden="true">
            <div
              className="visual-match-band"
              style={{
                left: `${(100 * (visualRange.candidate.start_frame - contextStart)) / (contextEnd - contextStart)}%`,
                width: `${(100 * (visualRange.candidate.end_frame - visualRange.candidate.start_frame)) / (contextEnd - contextStart)}%`,
              }}
            />
            <div
              className="visual-selected-band"
              style={{
                left: `${(100 * (visualRange.selectedStart - contextStart)) / (contextEnd - contextStart)}%`,
                width: `${(100 * (visualRange.selectedEnd - visualRange.selectedStart)) / (contextEnd - contextStart)}%`,
              }}
            />
          </div>
          <label className="visual-range-control">
            {reviewingFullSource
              ? "Scrub full source video"
              : reviewingActivity
                ? "Scrub activity"
                : "Scrub nearby footage"}{" "}
            · {(playhead / 30).toFixed(1)}s
            <input
              aria-label={
                reviewingFullSource
                  ? "Scrub full source video"
                  : reviewingActivity
                    ? "Scrub activity"
                    : "Scrub nearby footage"
              }
              type="range"
              min={contextStart}
              max={contextEnd - 1}
              step="1"
              value={Math.max(contextStart, Math.min(playhead, contextEnd - 1))}
              onChange={(event) => {
                const frame = Number(event.target.value);
                video.current?.pause();
                if (video.current) video.current.currentTime = frame / 30;
                setPlayhead(frame);
              }}
            />
          </label>
          <div className="visual-range-labels">
            <span>Your selected cut</span>
            <span>
              {(visualRange.selectedStart / 30).toFixed(1)}–
              {(visualRange.selectedEnd / 30).toFixed(1)}s
            </span>
          </div>
          {reviewing ? (
            <p className="full-source-note">
              Viewing only—the selected cut has not changed. Return to match
              preview to adjust its in and out points.
            </p>
          ) : (
            <>
              <label className="visual-range-control">
                In · frame {visualRange.selectedStart}
                <input
                  aria-label="Selected cut in frame"
                  type="range"
                  min={visualRange.contextStart}
                  max={visualRange.selectedEnd - 1}
                  step="1"
                  value={visualRange.selectedStart}
                  onChange={(event) => {
                    video.current?.pause();
                    onVisualRangeChange(
                      moveVisualHandle(
                        visualRange,
                        "in",
                        Number(event.target.value),
                      ),
                    );
                  }}
                />
              </label>
              <label className="visual-range-control">
                Out · frame {visualRange.selectedEnd} (exclusive)
                <input
                  aria-label="Selected cut out frame"
                  type="range"
                  min={visualRange.selectedStart + 1}
                  max={visualRange.contextEnd}
                  step="1"
                  value={visualRange.selectedEnd}
                  onChange={(event) => {
                    video.current?.pause();
                    onVisualRangeChange(
                      moveVisualHandle(
                        visualRange,
                        "out",
                        Number(event.target.value),
                      ),
                    );
                  }}
                />
              </label>
            </>
          )}
        </div>
      )}
    </>
  );
}
