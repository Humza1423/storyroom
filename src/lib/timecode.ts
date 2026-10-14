export const timecode = (f: number) =>
  `${Math.floor(f / 1800)
    .toString()
    .padStart(2, "0")}:${Math.floor((f / 30) % 60)
    .toString()
    .padStart(2, "0")}:${Math.round(f % 30)
    .toString()
    .padStart(2, "0")}`;
