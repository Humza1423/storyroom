# Using Storyroom

Storyroom helps you find useful ranges in existing footage, arrange them into
Storybins, and hand a first cut to DaVinci Resolve. The four numbered buttons at
the top of a project jump to each part of the workspace. **How to use** opens a
short version of this guide inside the app.

## 1. Footage

Create a project, then click **Import** and choose MP4 clips. Wait until they
say **ready**. Storyroom keeps the source files unchanged and makes local
editing/playback copies. **Activity** shows background preparation and any
errors; you can close the browser while the local worker continues.

Each imported clip appears under **Clips & permissions**. Its settings button
records the source and what you have permission to do with it. Cloud analysis
is off for a clip until you explicitly allow it. Do not grant that permission
for private footage or footage whose rights you have not checked.

## 2. Find moments

Pick the search mode before typing a query:

| Mode | What it searches | Setup |
| --- | --- | --- |
| Keyword | Filenames and saved descriptions | None; works offline |
| Description AI | AI-written descriptions of footage | Optional cloud-analysis setup |
| Visual AI | Video samples represented as embeddings | Permission for each clip, then **Estimate & index permitted clips** |

For Visual AI, review the estimate and privacy notice before you confirm
indexing. This sends permitted proxy samples to Gemini. Once indexing finishes,
search for visible actions, such as `jumping jacks`. **Quick add to Storybin**
or drag a result to save its approximate AI match range unchanged. Choose
**Preview & adjust** to inspect up to one second of nearby footage on each
side. The nearby footage is **not verified**; it may contain another action.
Scrub it, move the keyboard-accessible in/out sliders, play your selected cut,
then choose **Add selected cut to Storybin**. Only your chosen frame boundaries
are saved. The AI match and nearby preview are temporary, and no new AI request
or video file is made while adjusting.

Keyword results showing an entire clip do **not** prove the app recognized its
contents. To test visual search, select **Visual AI** explicitly.

## 3. Storybins

Click **Add story section** to create a Storybin, such as “Warm-up,” “Technique,”
or “Best effort.” Click a bin to make it the destination for a search result.
The search panel names the current destination. You can also drag results into
a bin. A clip can appear more than once with different ranges.

Click a clip already in a bin to edit **In · frame** and **Out · frame** in the
Player, then **Apply changes**. Storyroom uses 30 frames per second: frames
`30 → 90` keep seconds 1–3. The out frame is excluded. Drag clips or use their
reorder controls to change the cut order. Board changes save automatically; the
undo button reverses the last saved board change.

## 4. Player and export

**Play assembly** plays the selected ranges in order. Its scrubber shows time
*within the current selected range* even though the browser streams the full
proxy file underneath. It does not create or alter an MP4.

**Render preview** creates a new cut MP4 for review. **Export to Resolve**
creates an editable cuts-only timeline that references Storyroom's local
editing copies. Open **Activity** to download the finished MP4 or Resolve XML.
Keep the referenced editing copies in place when importing that XML into
DaVinci Resolve. If Resolve says media is offline, grant it access to
Storyroom's media folder and relink/import again.

## If something looks wrong

- No Visual AI results: check that clips are ready, have cloud-analysis
  permission, and completed visual indexing. Also try a different query; the
  current model can miss fast actions or return similar-looking false positives.
- The 4K Pexels demo project is marked demo/workflow only. Its clips are not
  approved for AI indexing, so use rights-cleared footage in another project
  when testing Visual AI.
- An inaccurate range: use **Preview & adjust** before adding, or trim the placed selection afterward.
  Record the bad result rather than assuming a similarity score means it is right.
- A missing project: projects belong to the local server's `STORYROOM_DATA`
  folder. A different or temporary data folder is a different workspace.
- A button stays busy: open **Activity** for the actual job state and error.

The optional AI development budget shown in the app is a **local spending
guardrail**, not a subscription or a bill. Google billing, if enabled, is
separate.
