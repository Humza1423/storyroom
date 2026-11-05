import { useEffect, useRef, useState, type RefObject } from "react";
import { Film, Pause, Play } from "lucide-react";
import type { Moment, Selection, VisualCandidate } from "../../types";
import {
  activityBounds,
  moveVisualHandle,
  selectEstablishedActivity,
  type VisualRange,
} from "./visualRange";
import { canAdvancePlaybackRange } from "./playback";
import {
  activityPresentation,
  type ActivityInspectionJob,
} from "../library/activityPresentation";

export function Player({
  preview,
  video,
  advance,
  assembly,
  visualRange,
  sourceFrames,
  onVisualRangeChange,
  inspectionJob,
}: {
  preview: Moment | Selection | VisualCandidate | null;
  video: RefObject<HTMLVideoElement | null>;
  advance: () => void;
  assembly: boolean;
  visualRange?: VisualRange | null;
  sourceFrames: number;
  onVisualRangeChange?: (range: VisualRange) => void;
  inspectionJob?: ActivityInspectionJob;
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
  const presentation = visualRange
    ? activityPresentation(
        visualRange.candidate,
        inspectionJob,
        visualRange.selectedEnd - visualRange.selectedStart,
      )
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
    setReview(
      visualRange && activity
        ? { id: visualRange.candidate.id, mode: "activity" }
        : null,
    );
    // Evidence updates may expand the range, but must not change the review mode.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [preview?.asset_id, preview?.id]);

  useEffect(() => {
    // A worker can change the playable activity without replacing the video.
    // Seeking alone does not pause it; keep actual playback and controls aligned.
    const element = video.current;
    element?.pause();
    activeRangeKey.current = rangeKey;
    advanced.current = false;
    prepared.current = false;
    playAfterSeek.current = assembly;
    setElapsed(0);
    setPlayhead(startFrame);
    setPlaying(false);
    if (element?.readyState && preview) prepare(element);
    // Metadata handles a new source; this also prepares an existing video after
    // its frame bounds change. Assembly playback resumes explicitly in prepare.
    // eslint-disable-next-line react-hooks/exhaustive-deps
    return () => {
      if (activeRangeKey.current === rangeKey) activeRangeKey.current = "";
    };
  }, [preview?.asset_id, preview?.id, assembly, rangeKey]);

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
              key={`${preview.asset_id}:${preview.id}`}
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
            <span>
              {activity
                ? "Suggested cut · AI proposal"
                : "AI match range · approximate"}
            </span>
            <span>
              {(visualRange.candidate.start_frame / 30).toFixed(1)}–
              {(visualRange.candidate.end_frame / 30).toFixed(1)}s
            </span>
          </div>
          {presentation && (
            <div
              className="activity-status"
              aria-label="Activity inspection status"
            >
              <strong className="activity-status-label">
                {presentation.statusLabel}
              </strong>
              {activity && (
                <p className="activity-established-range">
                  Established activity · {frameTimecode(activity.start)}–
                  {frameTimecode(activity.end)}
                  <br />
                  {(activity.end - activity.start) / 30 ===
                  Math.floor((activity.end - activity.start) / 30)
                    ? (activity.end - activity.start) / 30
                    : ((activity.end - activity.start) / 30).toFixed(2)}
                  s · {activity.end - activity.start} frames
                </p>
              )}
              {presentation.duration && <p>{presentation.duration}</p>}
              <p>{presentation.inspection}</p>
            </div>
          )}
          <p>
            {reviewingFullSource
              ? "Full source video · not verified. Review the entire imported clip; the AI match and your selected cut stay marked below."
              : reviewingActivity
                ? presentation?.complete
                  ? "Activity range · AI identified. This view does not change your selected cut."
                  : "Activity range · partially inspected. Its beginning or end may still be unresolved."
                : activity
                  ? "Selected cut preview. Adjust the cut anywhere inside the established activity."
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
              {reviewingActivity ? "Preview selected cut" : "Review activity"}
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
              ? activity
                ? "Return to selected cut"
                : "Return to match preview"
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
              : activity
                ? "Scrub activity"
                : "Scrub nearby footage"}{" "}
            · {(playhead / 30).toFixed(1)}s
            <input
              aria-label={
                reviewingFullSource
                  ? "Scrub full source video"
                  : activity
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
          <p
            className="selected-frame-summary"
            aria-label="Selected cut frame summary"
          >
            Start {frameTimecode(visualRange.selectedStart)} · frame{" "}
            {visualRange.selectedStart}
            <br />
            End {frameTimecode(visualRange.selectedEnd)} · frame{" "}
            {visualRange.selectedEnd} (exclusive)
            <br />
            Duration{" "}
            {(
              (visualRange.selectedEnd - visualRange.selectedStart) /
              30
            ).toFixed(2)}
            s · {visualRange.selectedEnd - visualRange.selectedStart} frames
          </p>
          {reviewingFullSource ? (
            <p className="full-source-note">
              Viewing only—the selected cut has not changed. Return to the cut
              preview to adjust its in and out points.
            </p>
          ) : (
            <>
              {activity && (
                <button
                  type="button"
                  className="secondary full-source-toggle"
                  onClick={() => {
                    video.current?.pause();
                    onVisualRangeChange(selectEstablishedActivity(visualRange));
                  }}
                >
                  {presentation?.complete
                    ? "Select full activity"
                    : "Select activity found so far"}
                </button>
              )}
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
              <label className="visual-frame-entry">
                Start frame
                <FrameNumberInput
                  aria-label="Selected cut start frame number"
                  min={visualRange.contextStart}
                  max={visualRange.selectedEnd - 1}
                  value={visualRange.selectedStart}
                  onCommit={(frame) => {
                    video.current?.pause();
                    onVisualRangeChange(
                      moveVisualHandle(visualRange, "in", frame),
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
              <label className="visual-frame-entry">
                End frame · exclusive
                <FrameNumberInput
                  aria-label="Selected cut end frame number"
                  min={visualRange.selectedStart + 1}
                  max={visualRange.contextEnd}
                  value={visualRange.selectedEnd}
                  onCommit={(frame) => {
                    video.current?.pause();
                    onVisualRangeChange(
                      moveVisualHandle(visualRange, "out", frame),
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

function frameTimecode(frame: number) {
  const seconds = Math.floor(frame / 30);
  return [
    Math.floor(seconds / 3600),
    Math.floor(seconds / 60) % 60,
    seconds % 60,
    frame % 30,
  ]
    .map((value) => String(value).padStart(2, "0"))
    .join(":");
}

/** Let a person finish typing before clamping: "659" must not become "151" after its first digit. */
function FrameNumberInput({
  value,
  min,
  max,
  onCommit,
  "aria-label": label,
}: {
  value: number;
  min: number;
  max: number;
  onCommit: (frame: number) => void;
  "aria-label": string;
}) {
  const [draft, setDraft] = useState(String(value));
  useEffect(() => setDraft(String(value)), [value]);
  return (
    <input
      aria-label={label}
      type="number"
      min={min}
      max={max}
      step="1"
      value={draft}
      onChange={(event) => setDraft(event.target.value)}
      onBlur={() => {
        const parsed = Number(draft);
        const frame =
          draft.trim() && Number.isFinite(parsed)
            ? Math.max(min, Math.min(max, Math.round(parsed)))
            : value;
        setDraft(String(frame));
        onCommit(frame);
      }}
      onKeyDown={(event) => {
        if (event.key === "Enter") event.currentTarget.blur();
      }}
    />
  );
}
