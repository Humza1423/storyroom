# Real footage for the first manual test

Source pages inspected 2026-10-07. These are freely licensed videos, rather than
"open-source" software. No video has been downloaded, played through, inspected
with ffprobe, imported, or evaluated in Storyroom in this documentation task.
Metadata below is reported by the file pages and rounded. License checks establish
a useful starting set; they do not establish model accuracy or editor compatibility.

## Starter set

All four are exercise demonstrations attributed to Taco Fleur / Cavemantraining,
listed as the uploader's own work and licensed CC BY-SA 4.0. Each page has an
Original file download link and its own license/author information.

| Source page | Reported length | Reported dimensions / size | First test purpose |
| --- | --- | --- | --- |
| [Jumping jacks and burpees](https://commons.wikimedia.org/wiki/File:Jumping_jacks_and_burpees.webm) | 45 s | 640×480 / 6.24 MB | Distinguish two activities within a clip |
| [Double kettlebell clean and jerk](https://commons.wikimedia.org/wiki/File:Double_Kettlebell_Clean_and_Jerk.webm) | 29 s | 640×480 / 3.73 MB | Repetition, candidate ranges, and precise manual trims |
| [Kettlebell swing, hip hinge style](https://commons.wikimedia.org/wiki/File:Kettlebell_Swing_Hip_Hinge_Style.webm) | 61 s | 640×480 / 7.46 MB | Longer-clip chunking later and broad action selection |
| [Kettlebell swing, hip hinge zoom](https://commons.wikimedia.org/wiki/File:Kettlebell_Swing_Hip_Hinge_Style_Zoom.webm) | 17 s | 640×480 / 2.16 MB | Technique-detail alternative and related visual content |

Together: approximately 2.5 minutes and 20 MB before conversion, well within the
project's duration/file-count limits. Related swing clips must remain in one footage
group for any later held-out ranking evaluation. Different files are not automatically
independent shoots. This collection is too small for the three-group/20-query benchmark.

## License and provenance

The [CC BY-SA 4.0 license summary](https://creativecommons.org/licenses/by-sa/4.0/)
permits sharing and adaptation, including commercial use, with attribution, a
license link, and notice of changes; distributed adaptations use the same or a
compatible license. Preserve media attribution separately from the MIT application
code. Do not label a published demo montage made from these clips as MIT-only media.

For every download record title, author, Commons page and original download URL,
license URL, page revision/permanent link, access date, byte count, SHA-256, original
codec/audio/dimensions, and conversion/extraction details. Save the actual manifest
beside local media under `data/evaluation/`, excluded from Git. Link the source and
license in any shared demonstration and credit Taco Fleur / Cavemantraining.

Start with local workflow evaluation. Do not enable the app's cloud-analysis or
training flags merely because an asset appears in this list; make those decisions
for the later authorized operation and applicable provider terms. Custom training is
outside this exercise; there are no fabricated permissions, labels, or model results.

## Preparation after foundation completion

1. Download Original file from each Commons page into
   `data/evaluation/cavemantraining/originals/`; keep originals unchanged.
2. Inspect with ffprobe and record actual properties. Originals are WebM/VP8, while
   the app currently accepts SDR H.264 MP4. Make H.264/AAC, yuv420p, 30-fps MP4
   input copies in a separate `inputs/` folder. Preserve elapsed duration and audio
   when present; do not invent a soundtrack for silent inputs. Keep original size;
   upscaling 480p cannot recover detail. FFmpeg conversion is preparation outside
   Storyroom, not evidence that WebM imports are supported.
3. Record conversion as a change in the provenance manifest. Import only MP4 inputs.
4. Review every clip and assign plain descriptions manually; no AI is necessary
   to test keyword search, sections, trimming, persistence, playback, and export.

Suggested brief: "Make a 20–30 second exercise montage: start with movement,
show a technique detail, build toward the kettlebell lift, finish with a clean
repetition." Avoid implying these separately recorded demos document one real session.

Suggested manual checks:

- Use at least three sources in custom sections; place one source twice with
  different trim ranges. Save, restart, and verify exact boundaries/order.
- Retrieve manually described movements by keyword; an absent exercise returns no
  relevant result. This evaluates the manual search path, not AI understanding.
- Render and compare duration to the sum of frame ranges divided by 30. Check audio
  and silent spans. Export and import XML into Resolve; record its version and
  cut/order/audio/media-reference results, with a one-frame cut tolerance.
- For a later AI test, review timestamped positive queries such as finding jumping
  jacks versus burpees, two kettlebells versus a swing, and a detail shot. Verify that
  those events are actually visible before adding ground truth. Include absent
  actions. Do not claim exact action success or fitness coaching from model output.

## What this set cannot establish

These are clean, already composed exercise demonstrations at modest resolution.
They test real pixels and plumbing, but not the central challenge of messy raw
footage, competing takes, setup/recovery, camera movement, or story discovery.
After this works, use a permissioned short phone shoot with those characteristics
and at least two further independent footage sets for retrieval evaluation.

An alternative found during research was
[Half rack resistance exercise workout](https://commons.wikimedia.org/wiki/File:Half_rack_resistance_exercise_workout.webm)
by FitnessScape, reported as 2:54 at 720p under CC BY 3.0. Its page explicitly says
the externally sourced license has not yet been reviewed by a Commons reviewer.
Keep it out of the starter set until that source/license is independently confirmed.
