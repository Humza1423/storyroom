from pathlib import Path
import opentimelineio as otio
from . import config


def export_timeline(name, board, assets, dest):
    timeline = otio.schema.Timeline(name=name)
    video = otio.schema.Track(name="Story assembly", kind=otio.schema.TrackKind.Video)
    audio = otio.schema.Track(name="Source audio", kind=otio.schema.TrackKind.Audio)
    timeline.tracks.extend([video, audio])
    count = 0
    for section in board:
        for selection in section["selections"]:
            asset = assets[selection["asset_id"]]
            path = config.asset_dir(asset["id"]) / "edit.mp4"
            if not path.exists():
                raise ValueError(
                    f"Missing editing copy: {asset['name']}. Retry its import job."
                )
            start, end = selection["start_frame"], selection["end_frame"]
            span = otio.opentime.TimeRange(
                otio.opentime.RationalTime(start, 30),
                otio.opentime.RationalTime(end - start, 30),
            )
            ref = otio.schema.ExternalReference(
                target_url=path.as_uri(),
                available_range=otio.opentime.TimeRange(
                    otio.opentime.RationalTime(0, 30),
                    otio.opentime.RationalTime(asset["frames"], 30),
                ),
            )
            clip = otio.schema.Clip(
                name=f"{section['title']} · {asset['name']}",
                media_reference=ref,
                source_range=span,
            )
            clip.metadata["storyroom"] = {
                "note": selection.get("note", ""),
                "section": section["title"],
            }
            video.append(clip)
            if asset["has_audio"]:
                audio.append(clip.deepcopy())
            else:
                audio.append(
                    otio.schema.Gap(
                        source_range=otio.opentime.TimeRange(
                            otio.opentime.RationalTime(0, 30), span.duration
                        )
                    )
                )
            count += 1
    if not count:
        raise ValueError("Choose at least one clip before exporting.")
    otio.adapters.write_to_file(timeline, str(dest), adapter_name="fcp_xml")
    otio.adapters.write_to_file(
        timeline, str(Path(dest).with_suffix(".otio")), adapter_name="otio_json"
    )
