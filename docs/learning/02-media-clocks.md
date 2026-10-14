# Why an editor needs one clock

A saved selection is an asset ID plus integer in/out frames. At 30 fps, frames
15 through 44 occupy one second: `(45 - 15) / 30`. The out point is exclusive.
Those numbers are useful only if the editing copy actually has a stable frame
clock, starts where the app expects, and keeps sound aligned with the image.

## Shared origin, separate streams

Suppose a camera file's first video frame has timestamp 4.2 seconds and a whistle
has timestamp 4.7 seconds. If the first video frame becomes editing time zero,
the whistle belongs at 0.5 seconds (frame 15). Subtract 4.2 from both streams.
Starting audio and video independently at zero would erase their intended offset.

Audio before the chosen video origin must be trimmed; audio starting later needs
leading silence. Codec padding can also affect encoded duration. Looking only at
an MP4's displayed length will not prove that the whistle and the visual action
still occur together.

## Geometry is another coordinate system

A 160-by-90 image with pixels twice as wide as they are tall displays at 32:9.
Simply labeling those pixels square makes it display at 16:9 and squeezes the
picture. Conversion must first preserve the displayed geometry by resizing, then
write square pixels. Rotation metadata can also change which axis is horizontal.

## Test the output independently

The media checks in [test_media_correctness.py](../../tests/test_media_correctness.py)
generate known color markers and sound cues, then independently decode frames,
timestamps and audio samples. A test that repeats the production duration-rounding
formula could reproduce the same mistake and still pass.

Try this exercise:

1. Predict the output duration for ranges `[0, 10)`, `[29, 30)`, and `[10, 20)`.
2. Find the test's five selected ranges, calculate their total separately, then
   compare it with the frame-count and timestamp-spacing assertions.
3. Explain why a correct total count alone cannot prove correct cut order or sound.
4. Read the change in `server/media.py` and identify which operation preserves
   geometry and which preserves the shared clock.

Run the bounded generated-media checks from the repository root with
`.venv/bin/pytest -q tests/test_media_correctness.py`. These fixtures establish
specific engineering properties; actual camera footage and Resolve still need
their own acceptance check.
