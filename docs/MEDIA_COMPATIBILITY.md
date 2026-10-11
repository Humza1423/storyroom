# Media compatibility check — 2026-10-11

This is a bounded engineering check, not a claim of general camera support.
Storyroom still accepts only SDR H.264 MP4 up to 1080p. Four *test profiles*
were derived from one licensed real sports video, then imported into an isolated
Storyroom project and one cuts-only timeline in DaVinci Resolve 21.1.1 (free,
macOS). The earlier four 640×480 Cavemantraining clips are a separate, narrower
real-footage check in [STATUS](STATUS.md).

## Source and reproducibility

- Source: [Runners.webm](https://commons.wikimedia.org/wiki/File:Runners.webm),
  by Evworo; [permanent page revision](https://commons.wikimedia.org/w/index.php?title=File:Runners.webm&oldid=633673187).
- License: [CC BY-SA 3.0](https://creativecommons.org/licenses/by-sa/3.0/).
  The local transcodes are modified test copies, not independent camera sources.
- Original URL: <https://upload.wikimedia.org/wikipedia/commons/7/7e/Runners.webm>.
  Accessed 2026-10-11; 16,857,178 bytes; SHA-256
  `2cd586c29b196bb594fb08a2af1855d82c3dd41e628ee572be6136bcd0455ad2`.
  ffprobe: VP8 1920×1080 video, Vorbis audio, 22.487 s WebM.
- Conversion/test environment: macOS, FFmpeg 9.0.1. Originals, derivatives,
  isolated SQLite database, render, and XML remain under ignored
  `data/evaluation/compatibility/`; none are committed or redistributed.
  The original's SHA-256 matched after the workflow.

The conversion commands used FFmpeg/libx264, two threads, `veryfast`, CRF 23,
`yuv420p`, and `+faststart`. The 24 fps landscape input used seconds 1–7,
`fps=24,scale=1920:1080,setsar=1`, with AAC 48 kHz stereo. The 60 fps silent
portrait input used seconds 7–13,
`crop=608:1080:656:0,scale=720:1280,fps=60,setsar=1` and `-an`. The silent
VFR input used seconds 14–20, 1280×720, `fps=30` followed by variable output
timestamps (`setpts` changed from a 30 fps to a 20 fps segment), and
`-fps_mode vfr`; its stream averaged about 25.3 fps. A fourth input copied the
24 fps landscape file with a 90° display-rotation tag. This last test confirms
the tag is honored; because it was attached to already-upright pixels, its
picture intentionally appears sideways and does **not** prove real phone footage
will appear upright. The exact local files and SHA-256 values are in the ignored
evaluation directory.

## Result matrix

| Profile | Storyroom preparation | Render | Resolve 21.1.1 after folder access |
| --- | --- | --- | --- |
| 1920×1080, 24 fps, AAC | Ready; 179 normalized 30 fps frames | First 90-frame cut, audible | Correct landscape picture and audio lane |
| 720×1280, 60 fps, silent | Ready; 180 normalized frames | Second 90-frame cut, padded to 16:9 | Correct portrait picture; no source-audio lane |
| 1280×720, variable frame rate, silent | Ready; 179 normalized frames | Third 90-frame cut | Correct landscape picture; no source-audio lane |
| 1920×1080 with 90° rotation metadata, AAC | Ready; normalized to 1080×1920, 179 frames | Fourth 90-frame cut, portrait padding | Rotation visibly honored; audio lane present |
| Original VP8/Vorbis WebM | HTTP 400, `file_invalid` | Not applicable | Not a Storyroom-supported input |
| H.264 QuickTime MOV | HTTP 400, `file_invalid` | Not applicable | Not a Storyroom-supported input |
| HEVC MP4 derivative | **Not determined:** import stopped at disk-space preflight | Not run | Not tested; code policy rejects HEVC |

The saved four-section board selected 90 frames from each ready asset, for a
360-frame/12.000-second assembly. Independent ffprobe inspection found 360
decoded video frames and 12.000-second video/audio durations in the review MP4.
Visual samples at 1.5, 4.5, 7.5, and 10.5 seconds showed the intended sequence.
One-second audio windows measured about -37 and -49 dB mean on the two
audio-backed sections and about -91 dB (AAC near-silence) on the two silent
sections. Those numbers check presence/absence, not perceptual sound quality.

## Resolve handoff finding

The first four-clip XML import said **4 of 4 clips were not yet found**. A
single-clip XML showed the same problem; changing `file:///` to
`file://localhost/` in a diagnostic copy did not fix it. Directly importing the
same `edit.mp4` in Resolve exposed the actual boundary: **Grant Access To
Folder?** Granting Resolve access to this evaluation project's `media/` parent
folder and re-importing the original, unchanged four-clip XML loaded all four
sources. In the actual Resolve viewer, the four pictures appeared at their
respective cuts (including portrait, VFR-derived, and rotated variants). The
timeline read 00:00:12:00 at 30 fps, with audio only under the first and fourth
cuts. The test project was saved as **Storyroom Mixed Media Compatibility**.

This shows a macOS Resolve folder-permission/onboarding gap, not an observed
encoder or XML-timing defect. The export panel and setup guide now explain the
access step. The four media files are all named `edit.mp4` in different asset
directories; this test did not mislink them, but portable relinking remains
unimplemented and should be separately tested before claiming it works.

The machine fell from about 3.7 GiB to 2.6 GiB free during this session, so a
later HEVC import received Storyroom's 3 GB minimum-free-space error before codec
validation. That is a capacity limitation in this environment, not evidence of
HEVC compatibility. No user files were removed to force the test through.

## What this does not prove

No genuine phone-captured VFR or rotation-tagged source, 4K, HDR/10-bit,
HEVC, ProRes/MOV workflow, external-drive relinking, Windows/Linux install, or
Resolve version beyond 21.1.1 was validated here. The profile matrix uses one
source scene, so it cannot measure retrieval quality or general visual handling.
The next media test should use distinct permissioned camera recordings only
where an observed failure or target user need justifies expanding the accepted
format boundary. AI search can proceed on the verified H.264 manual path without
claiming broader media support.
