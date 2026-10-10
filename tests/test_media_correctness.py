"""Generated media with independent decoded-pixel, frame-clock and PCM oracles.

These tests exercise FFmpeg, not provider APIs. Source geometry/timing is designed
below; expected output never comes from Storyroom's duration-rounding helper.
"""

import json
import subprocess

import numpy as np
import opentimelineio as otio
import pytest

from server import config, media
from server.exporter import export_timeline
from conftest import create_ready


def ffmpeg(*args):
    return subprocess.run(
        ["ffmpeg", "-nostdin", "-v", "error", "-y", *map(str, args)],
        check=True,
        capture_output=True,
        timeout=40,
    ).stdout


def inspect(path, frames=False):
    args = ["ffprobe", "-v", "error", "-count_frames", "-show_streams", "-show_format"]
    if frames:
        args += [
            "-select_streams",
            "v:0",
            "-show_frames",
            "-show_entries",
            "frame=best_effort_timestamp_time",
        ]
    result = subprocess.run(
        [*args, "-of", "json", str(path)], check=True, capture_output=True, timeout=30
    )
    return json.loads(result.stdout)


def video_stream(path):
    return next(s for s in inspect(path)["streams"] if s["codec_type"] == "video")


def pixels(path):
    stream = video_stream(path)
    raw = ffmpeg(
        "-i",
        path,
        "-an",
        "-fps_mode",
        "passthrough",
        "-pix_fmt",
        "rgb24",
        "-f",
        "rawvideo",
        "pipe:1",
    )
    return np.frombuffer(raw, dtype=np.uint8).reshape(
        -1, stream["height"], stream["width"], 3
    )


def pcm(path):
    raw = ffmpeg("-i", path, "-vn", "-ac", "1", "-ar", "48000", "-f", "s16le", "pipe:1")
    return np.frombuffer(raw, dtype="<i2").astype(float) / 32768


def make_video(
    path,
    *,
    size="160x90",
    rate=30,
    duration=1.2,
    vf=None,
    audio=None,
    input_video_offset=0,
    input_audio_offset=0,
    output_offset=None,
):
    args = []
    if input_video_offset:
        args += ["-itsoffset", str(input_video_offset)]
    args += ["-f", "lavfi", "-i", f"color=black:s={size}:r={rate}:d={duration}"]
    if audio is not None:
        if input_audio_offset:
            args += ["-itsoffset", str(input_audio_offset)]
        args += ["-f", "lavfi", "-i", audio]
    if vf:
        args += ["-vf", vf]
    args += [
        "-c:v",
        "libx264",
        "-preset",
        "ultrafast",
        "-threads",
        "2",
        "-pix_fmt",
        "yuv420p",
        "-fps_mode",
        "passthrough",
    ]
    if audio is not None:
        args += ["-c:a", "aac", "-ar", "48000"]
    if output_offset is not None:
        args += ["-output_ts_offset", str(output_offset)]
    ffmpeg(*args, path)
    return path


QUADRANTS = (
    "drawbox=x=0:y=0:w=iw/2:h=ih/2:color=red:t=fill,"
    "drawbox=x=iw/2:y=0:w=iw/2:h=ih/2:color=lime:t=fill,"
    "drawbox=x=0:y=ih/2:w=iw/2:h=ih/2:color=blue:t=fill,"
    "drawbox=x=iw/2:y=ih/2:w=iw/2:h=ih/2:color=yellow:t=fill"
)
COLORS = np.array([[255, 0, 0], [0, 255, 0], [0, 0, 255], [255, 255, 0]])


def corner_colors(frame):
    h, w = frame.shape[:2]
    samples = np.array(
        [
            frame[h // 4, w // 4],
            frame[h // 4, 3 * w // 4],
            frame[3 * h // 4, w // 4],
            frame[3 * h // 4, 3 * w // 4],
        ]
    )
    return np.argmin(
        ((samples[:, None].astype(float) - COLORS) ** 2).sum(axis=2), axis=1
    ).tolist()


def assert_clock(path, expected_count):
    stream = video_stream(path)
    frames = inspect(path, frames=True)["frames"]
    pts = np.array([float(f["best_effort_timestamp_time"]) for f in frames])
    assert int(stream["nb_read_frames"]) == expected_count
    assert len(pts) == expected_count
    # Six decimal places in ffprobe output introduce < 1 microsecond rounding.
    assert pts[0] == pytest.approx(0, abs=0.001)
    np.testing.assert_allclose(np.diff(pts), 1 / 30, atol=0.000002)
    assert float(stream["duration"]) == pytest.approx(expected_count / 30, abs=1 / 30)


@pytest.mark.parametrize(
    "shape,rotation,expected_shape,expected_colors",
    [
        ("160x90", False, (160, 90), [0, 1, 2, 3]),
        ("90x160", False, (90, 160), [0, 1, 2, 3]),
        ("160x90", True, (90, 160), [1, 3, 0, 2]),
    ],
)
def test_geometry_and_decoded_orientation(
    tmp_path, shape, rotation, expected_shape, expected_colors
):
    source = make_video(tmp_path / "source.mp4", size=shape, duration=0.2, vf=QUADRANTS)
    if rotation:
        rotated = tmp_path / "rotated.mp4"
        ffmpeg("-i", source, "-c", "copy", "-metadata:s:v:0", "rotate=90", rotated)
        if not any(
            s.get("rotation") == 90
            for s in video_stream(rotated).get("side_data_list", [])
        ):
            # FFmpeg 9 removed the legacy rotate-tag remux behavior. Older
            # supported FFmpeg versions use the metadata path above.
            ffmpeg("-display_rotation:v:0", "90", "-i", source, "-c", "copy", rotated)
        assert any(
            s.get("rotation") == 90
            for s in video_stream(rotated).get("side_data_list", [])
        )
        source = rotated
    edit, proxy = tmp_path / "edit.mp4", tmp_path / "proxy.mp4"
    media.encode(source, edit)
    media.encode(edit, proxy, proxy=True)
    for path in [edit, proxy]:
        stream = video_stream(path)
        assert stream["sample_aspect_ratio"] == "1:1"
        assert stream["width"] / stream["height"] == pytest.approx(
            expected_shape[0] / expected_shape[1], abs=0.003
        )
        assert corner_colors(pixels(path)[0]) == expected_colors
        assert not any(s.get("rotation") for s in stream.get("side_data_list", []))
    assert (video_stream(edit)["width"], video_stream(edit)["height"]) == expected_shape


def test_non_square_pixels_preserve_display_aspect(tmp_path):
    source = make_video(
        tmp_path / "source.mp4", duration=0.2, vf=f"{QUADRANTS},setsar=2"
    )
    edit = tmp_path / "edit.mp4"
    media.encode(source, edit)
    stream = video_stream(edit)
    assert stream["sample_aspect_ratio"] == "1:1"
    assert stream["width"] / stream["height"] == pytest.approx(32 / 9, abs=0.025)
    assert corner_colors(pixels(edit)[0]) == [0, 1, 2, 3]
    assert max(stream["width"], stream["height"]) <= 1920
    assert min(stream["width"], stream["height"]) <= 1080


@pytest.mark.parametrize("rate", [24, 30, 60, "vfr"])
def test_normalization_has_independently_counted_constant_frames(tmp_path, rate):
    # Keep frames 0..11, then alternate frames12..34 of a36-frame clock.
    # The final held frame spans the same1.2s interval, with real unequal PTS.
    vf = "select='if(lt(n,12),1,not(mod(n,2)))'" if rate == "vfr" else None
    source = make_video(
        tmp_path / "source.mp4", rate=30 if rate == "vfr" else rate, vf=vf
    )
    if rate == "vfr":
        pts = [
            float(f["best_effort_timestamp_time"])
            for f in inspect(source, True)["frames"]
        ]
        assert len(set(round(t, 3) for t in np.diff(pts))) > 1
    edit = tmp_path / "edit.mp4"
    media.encode(source, edit)
    count = int(video_stream(edit)["nb_read_frames"])
    assert_clock(edit, count)
    assert (
        abs(count / 30 - float(video_stream(source)["duration"])) <= 1 / 30 + 0.000001
    )
    assert media.probe(edit)["frames"] == count


@pytest.mark.parametrize(
    "video_offset,audio_offset,output_offset,tone_start",
    [
        (0, 0.2, None, 0.3),
        (0, 0.2, 4, 0.3),
        (0.2, 0, None, 0.7),
    ],
)
def test_audio_and_video_keep_shared_clock(
    tmp_path, video_offset, audio_offset, output_offset, tone_start
):
    audio = (
        f"aevalsrc=0.5*sin(2*PI*1000*t)*between(t\\,{tone_start}\\,{tone_start + 0.1})"
        ":s=48000:d=1.2"
    )
    source = make_video(
        tmp_path / "source.mp4",
        vf="drawbox=width=iw:height=ih:color=white:t=fill:enable='gte(n,15)'",
        audio=audio,
        input_video_offset=video_offset,
        input_audio_offset=audio_offset,
        output_offset=output_offset,
    )
    # Check the generated oracle before using it: a visual frame number is
    # independent of the input clock shift, and audio retains its chosen delay.
    source_pts = [
        float(f["best_effort_timestamp_time"]) for f in inspect(source, True)["frames"]
    ]
    source_marker = np.flatnonzero(pixels(source).mean(axis=(1, 2, 3)) > 150)[0]
    assert source_pts[source_marker] - source_pts[0] == pytest.approx(0.5, abs=0.001)
    edit = tmp_path / "edit.mp4"
    media.encode(source, edit)
    assert_clock(edit, 36)
    visual = np.flatnonzero(pixels(edit).mean(axis=(1, 2, 3)) > 150)[0] / 30
    sound = np.flatnonzero(np.abs(pcm(edit)) > 0.1)[0] / 48000
    assert visual == pytest.approx(0.5, abs=1 / 30)
    assert sound == pytest.approx(visual, abs=1 / 30)


def test_worker_saves_decoded_normalized_frame_count(client, tmp_path):
    source = make_video(tmp_path / "source.mp4", rate=24)
    pid, aid = create_ready(client, source)
    asset = client.get(f"/api/projects/{pid}").json()["assets"][0]
    decoded_count = int(
        video_stream(config.asset_dir(aid) / "edit.mp4")["nb_read_frames"]
    )
    assert asset["frames"] == decoded_count
    assert asset["duration"] == pytest.approx(decoded_count / 30, abs=0.000001)


def test_repeated_final_frame_cuts_audio_silence_and_xml(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DATA", tmp_path)
    folder = config.asset_dir("color")
    folder.mkdir(parents=True)
    # Red0..9, green10..19, blue20..29: cut-order expectations are independent.
    vf = (
        "drawbox=width=iw:height=ih:color=red:t=fill:enable='lt(n,10)',"
        "drawbox=width=iw:height=ih:color=lime:t=fill:enable='between(n,10,19)',"
        "drawbox=width=iw:height=ih:color=blue:t=fill:enable='gte(n,20)'"
    )
    make_video(
        folder / "edit.mp4",
        duration=1,
        vf=vf,
        audio="sine=frequency=1000:sample_rate=48000:duration=1",
    )
    silent_folder = config.asset_dir("silent")
    silent_folder.mkdir(parents=True)
    make_video(
        silent_folder / "edit.mp4",
        size="90x160",
        duration=1,
        vf="drawbox=width=iw:height=ih:color=yellow:t=fill",
    )
    assets = {
        "color": {"id": "color", "name": "colors.mp4", "frames": 30, "has_audio": True},
        "silent": {
            "id": "silent",
            "name": "portrait.mp4",
            "frames": 30,
            "has_audio": False,
        },
    }
    ranges = [
        ("color", 20, 30),
        ("silent", 0, 15),
        ("color", 0, 10),
        ("color", 29, 30),
        ("color", 10, 20),
    ]
    board = [
        {
            "title": "Practice",
            "selections": [
                {"asset_id": aid, "start_frame": start, "end_frame": end}
                for aid, start, end in ranges
            ],
        }
    ]
    dest = tmp_path / "render.mp4"
    media.render(board, assets, dest)
    stream = video_stream(dest)
    # Demand exact frame count, uninterrupted spacing and correct source cuts.
    frames = inspect(dest, frames=True)["frames"]
    pts = np.array([float(f["best_effort_timestamp_time"]) for f in frames])
    assert int(stream["nb_read_frames"]) == 46
    assert abs(pts[0]) <= 1 / 30
    np.testing.assert_allclose(np.diff(pts), 1 / 30, atol=0.000002)
    decoded = pixels(dest)
    labels = [corner_colors(decoded[i])[0] for i in [0, 9, 25, 34, 35, 36, 45]]
    assert labels == [2, 2, 0, 0, 2, 1, 1]
    # Portrait stays narrow with black side bars rather than being stretched.
    portrait = decoded[15]
    assert portrait[:, :400].mean() < 5
    assert portrait[:, 880:].mean() < 5
    assert portrait[360, 640, :2].min() > 180
    audio = pcm(dest)
    assert np.max(np.abs(audio[int(0.45 * 48000) : int(0.7 * 48000)])) < 0.01
    for start, end in [(0.1, 0.2), (0.92, 1.04), (1.3, 1.4)]:
        assert (
            np.sqrt(np.mean(audio[int(start * 48000) : int(end * 48000)] ** 2)) > 0.02
        )
    # Locate both sides of the silent placement in10ms PCM energy windows.
    # One-frame tolerance allows AAC edge ringing and that window quantization.
    windows = audio[: len(audio) // 480 * 480].reshape(-1, 480)
    audible = np.sqrt(np.mean(windows**2, axis=1)) > 0.01
    first_silence = np.flatnonzero(~audible)[0] / 100
    first_return = np.flatnonzero(audible[50:])[0] / 100 + 0.5
    assert first_silence == pytest.approx(10 / 30, abs=1 / 30)
    assert first_return == pytest.approx(25 / 30, abs=1 / 30)
    # At most oneAAC packet of trailing decoded padding fits inside oneframe.
    assert abs(len(audio) / 48000 - 46 / 30) <= 1 / 30
    xml = tmp_path / "assembly.xml"
    export_timeline("Practice", board, assets, xml)
    timeline = otio.adapters.read_from_file(str(xml), adapter_name="fcp_xml")
    video = list(timeline.video_tracks()[0])
    assert [
        (c.source_range.start_time.value, c.source_range.duration.value) for c in video
    ] == [(start, end - start) for _, start, end in ranges]
    assert [c.media_reference.target_url for c in video] == [
        (config.asset_dir(aid) / "edit.mp4").as_uri() for aid, _, _ in ranges
    ]
    audio_items = list(timeline.audio_tracks()[0])
    assert isinstance(audio_items[1], otio.schema.Gap)
    assert [item.duration().value for item in audio_items] == [
        end - start for _, start, end in ranges
    ]
    assert timeline.duration().value == 46


@pytest.mark.parametrize("kind", ["corrupt", "codec", "hdr", "renamed_mov"])
def test_real_unsupported_inputs_are_rejected(client, tmp_path, kind):
    source = tmp_path / "unsupported.mp4"
    if kind == "corrupt":
        payload = b"this is not a video"
    else:
        args = [
            "-f",
            "lavfi",
            "-i",
            "color=red:s=160x90:r=30:d=0.2",
            "-c:v",
            "mpeg4" if kind == "codec" else "libx264",
            "-threads",
            "2",
        ]
        if kind == "hdr":
            args += [
                "-bsf:v",
                "h264_metadata=transfer_characteristics=16:colour_primaries=9:matrix_coefficients=9",
            ]
        if kind == "renamed_mov":
            args += ["-f", "mov"]
        ffmpeg(*args, source)
        if kind == "hdr":
            assert video_stream(source)["color_transfer"] == "smpte2084"
        elif kind == "renamed_mov":
            assert inspect(source)["format"]["tags"]["major_brand"].strip() == "qt"
        payload = source.read_bytes()
    pid = client.post("/api/projects", json={"name": "Rejected input"}).json()["id"]
    response = client.post(
        f"/api/projects/{pid}/import", files={"file": ("unsupported.mp4", payload)}
    )
    assert response.status_code == 400, response.text
    assert response.json()["detail"]
    assert client.get(f"/api/projects/{pid}").json()["assets"] == []


@pytest.mark.parametrize("operation", ["render", "export"])
def test_missing_editing_media_names_asset(tmp_path, monkeypatch, operation):
    monkeypatch.setattr(config, "DATA", tmp_path)
    assets = {
        "missing": {
            "id": "missing",
            "name": "missing-training.mp4",
            "has_audio": False,
            "frames": 30,
        }
    }
    board = [
        {
            "title": "Practice",
            "selections": [{"asset_id": "missing", "start_frame": 0, "end_frame": 10}],
        }
    ]
    with pytest.raises(ValueError, match="missing-training.mp4"):
        if operation == "render":
            media.render(board, assets, tmp_path / "render.mp4")
        else:
            export_timeline("Practice", board, assets, tmp_path / "assembly.xml")
