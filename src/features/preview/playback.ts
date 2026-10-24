export type PlaybackRangeCompletion = {
  eventRangeKey: string;
  activeRangeKey: string;
  eventVideo: object | null;
  activeVideo: object | null;
  alreadyAdvanced: boolean;
};

/** Ignore delayed completion events from a video range that is no longer active. */
export function canAdvancePlaybackRange(event: PlaybackRangeCompletion) {
  return (
    event.eventRangeKey !== "" &&
    event.eventRangeKey === event.activeRangeKey &&
    event.eventVideo !== null &&
    event.eventVideo === event.activeVideo &&
    !event.alreadyAdvanced
  );
}
