# Fresh Gemini validation footage

Prepared 2026-10-25. Eight distinct source items from three collections were
downloaded, converted and visually reviewed before model evaluation. These are
new source items relative to the preceding twelve-video study; this is a small
validation sample, not proof of accuracy across all video.

| Input | Source / creator | Rights | Prepared content observed |
|---|---|---|---|
| f01 | [Football Tennis](https://commons.wikimedia.org/wiki/File:Football_Tennis.webm), PK17 Football | [CC BY 3.0](https://creativecommons.org/licenses/by/3.0/) | 30s: players passing/kicking on grass, brief camera cuts and pauses |
| f02 | [EuroGames badminton](https://commons.wikimedia.org/wiki/File:Badmington_Competition_EuroGames_2_2023_in_Wankdork,_Bern.webm), Hyruspex | [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/) | 30s: indoor doubles play with pauses between exchanges |
| f03 | [Normal Base Push-Up](https://www.dvidshub.net/video/590723/follow-me-fitness-normal-base-push-up), Cpl. David Delgadillo / USMC | [US government public domain; DVIDS notice](https://www.dvidshub.net/about/copyright) | Source 8–38s: standing instructors and side/front demonstrations, repeated push-ups |
| f04 | [Volleyball Tournament announcement](https://www.dvidshub.net/video/975720/spangdahlem-blue-page-250902-volleyball-tournament), A1C Jessica Mun / USAF | [US government public domain; DVIDS notice](https://www.dvidshub.net/about/copyright) | 15s: announcement graphics only; **no actual volleyball** |
| f05 | [Horses running in a pasture](https://commons.wikimedia.org/wiki/File:Horses_running_in_a_pasture.webm), Field of Dreams | [CC BY 3.0](https://creativecommons.org/licenses/by/3.0/) | 30s: horses running/trotting and grazing in a field |
| f06 | [Noodle cooking](https://commons.wikimedia.org/wiki/File:Noodle_cooking_1_2020-05-18.webm), FASTILY | [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/) | 20.33s: pasta boiling in pot, no visible stirring person or spoon |
| f07 | [BIM badminton](https://commons.wikimedia.org/wiki/File:BIM_badminton.webm), PeaceSeekers | [CC0 1.0](https://creativecommons.org/publicdomain/zero/1.0/) | 2.63s: man demonstrating sign language; **no physical badminton play** |
| f08 | [PACE True Color globe](https://svs.gsfc.nasa.gov/31365/), NASA / Marit Jentoft-Nilsen (GST) | [NASA media guidelines](https://www.nasa.gov/nasa-brand-center/images-and-media/) | 30s: animated rotating Earth; no spacecraft or exercising astronauts |

Commons license pages were inspected individually. DVIDS item's public-domain
notice and creator were checked against its page (volleyball also against its
Commons mirror). NASA page credits and media guidance were inspected. NASA and
DVIDS are usage notices, not invented CC licenses. Preserve credits and avoid
implying endorsement. The license details do not imply every possible third-party
or personality right is covered. No Pexels content is used for AI evaluation.

## Reproduce preparation

```sh
.venv/bin/python scripts/prepare_gemini_validation.py
```

The script downloads one source at a time into ignored
`data/evaluation/gemini-fresh/raw`, retains it unchanged, and creates separate
opaque f01–f08 H.264/30fps/yuv420p inputs at no more than 1280×720. It preserves
existing audio with AAC and adds none to silent sources. Its local provenance
manifest records exact source URLs, download bytes, SHA-256 of original and input,
FFprobe output, access date and conversion commands. It creates 1fps contact
sheets. The football kicks and push-ups were additionally inspected at 4fps.
These annotations have approximate ±0.5s boundaries and still need real playback
review for action completeness/coherent cut judgments.

All eight preparations completed successfully. The script's `--help` also passed.
No media or generated manifests are committed, and this preparation makes no
Gemini calls. Missing files can be prepared individually with `--only f01` etc.

## Frozen evaluation key

`data/evaluation/gemini-fresh/answer-key-frozen-v1.json` contains 24 prewritten
queries: **16 positives, eight hard negatives**. It was frozen after viewing the
footage and before any model search on it:

```text
SHA-256 28d46f70d6c21d56aaa95d469616136f8c2d883c9e05aeb1d1b78f65d4ad10b3
```

Positive examples include complete football kicks, a complete push-up, broad
badminton/horse/cooking activity, sign gestures, and explicit 20-second requests.
The key labels individual complete moves separately from continuous footage and
records requested durations independently of semantic presence. Hard negatives
include volleyball play despite the announcement slate, stirring despite boiling
pasta, boxing/kicking a heavy bag, curls, a dog chasing a ball, exercising
astronauts, basketball scoring and knitting.

The query key references opaque **source IDs**, not database asset IDs. Import
the eight prepared files into a fresh isolated project, then retain a separate
mapping of source ID → imported asset ID for evaluation. Do not rewrite the frozen
key or supply source titles, labels or filenames as Gemini relevance evidence.
Do not tune on this set after seeing results; subsequent changes need a new test.

No search quality results are claimed by this source-preparation checkpoint.
