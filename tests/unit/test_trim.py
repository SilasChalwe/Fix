from pathlib import Path
import sys
import subprocess
from unittest.mock import patch

import pytest

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from fix.core.models import MediaInfo, OperationContext
from fix.media.ffmpeg import encoding_args, trim_video
from fix.plugins.trim.adapter import TrimAdapter


def media_info(source: Path, duration: float = 10.0) -> MediaInfo:
    return MediaInfo(
        path=source,
        duration=duration,
        width=1280,
        height=720,
        fps=30.0,
        video_codec="h264",
        video_bitrate=1_000_000,
        size_bytes=1000,
    )


def test_encoding_args_selects_libx265_for_hevc():
    media = MediaInfo(
        path=Path("source.mp4"),
        duration=10.0,
        width=1280,
        height=720,
        fps=30.0,
        video_codec="hevc",
        video_bitrate=1_000_000,
        size_bytes=1000,
    )

    args = encoding_args(media)

    assert "libx265" in args
    assert "libx264" not in args


def test_trim_command_uses_output_side_seeking(tmp_path):
    source = tmp_path / "source.mp4"
    output = tmp_path / "trimmed.mp4"
    source.write_bytes(b"source")
    media = media_info(source)
    completed = subprocess.CompletedProcess(
        args=["ffmpeg"],
        returncode=0,
        stdout="",
        stderr="",
    )

    with (
        patch(
            "fix.media.ffmpeg.probe_media",
            return_value=media,
        ) as mocked_probe,
        patch(
            "fix.media.ffmpeg.keyframes",
            return_value=[0.0, 2.0, 4.0, 6.0],
        ),
        patch(
            "fix.media.ffmpeg.subprocess.run",
            return_value=completed,
        ) as mocked_run,
    ):
        probed_media = mocked_probe(source)
        trim_video(
            source=source,
            output=output,
            start_seconds=2.0,
            end_seconds=8.0,
            media=probed_media,
            progress=lambda fraction, label: None,
        )

    mocked_probe.assert_called_once_with(source)
    command = mocked_run.call_args.args[0]
    assert command.index("-i") < command.index("-ss")
    assert command.index("-i") < command.index("-t")
    assert command[command.index("-t") + 1] == "6.000000"
    assert "-to" not in command
    assert "-avoid_negative_ts" not in command


def test_trim_command_no_audio_filter_on_reencode_path(tmp_path):
    source = tmp_path / "source.mp4"
    output = tmp_path / "trimmed.mp4"
    source.write_bytes(b"source")
    media = media_info(source)
    completed = subprocess.CompletedProcess(
        args=["ffmpeg"],
        returncode=0,
        stdout="",
        stderr="",
    )

    with (
        patch(
            "fix.media.ffmpeg.probe_media",
            return_value=media,
        ) as mocked_probe,
        patch(
            "fix.media.ffmpeg.keyframes",
            return_value=[0.0, 2.0, 4.0],
        ),
        patch(
            "fix.media.ffmpeg.subprocess.run",
            return_value=completed,
        ) as mocked_run,
    ):
        probed_media = mocked_probe(source)
        trim_video(
            source=source,
            output=output,
            start_seconds=1.337,
            end_seconds=8.337,
            media=probed_media,
            progress=lambda fraction, label: None,
        )

    mocked_probe.assert_called_once_with(source)
    command = mocked_run.call_args.args[0]
    assert "-af" not in command
    assert command[command.index("-c:a") + 1] == "copy"
    assert "libx264" in command
    assert "-shortest" not in command



def test_trim_restores_attached_picture_and_attachment_streams(tmp_path):
    source = tmp_path / "source.mkv"
    output = tmp_path / "trimmed.mkv"
    source.write_bytes(b"source")
    media = MediaInfo(
        path=source,
        duration=10.0,
        width=1280,
        height=720,
        fps=30.0,
        video_codec="h264",
        video_bitrate=1_000_000,
        size_bytes=1000,
        attached_picture_streams=(3,),
        attachment_streams=(4,),
    )
    completed = subprocess.CompletedProcess(
        args=["ffmpeg"],
        returncode=0,
        stdout="",
        stderr="",
    )

    with patch(
        "fix.media.ffmpeg.subprocess.run",
        return_value=completed,
    ) as mocked_run:
        trim_video(
            source=source,
            output=output,
            start_seconds=2.0,
            end_seconds=8.0,
            media=media,
            progress=lambda fraction, label: None,
        )

    assert mocked_run.call_count == 2
    trim_command = mocked_run.call_args_list[0].args[0]
    restore_command = mocked_run.call_args_list[1].args[0]

    assert "libx264" in trim_command
    assert "-shortest" not in trim_command
    assert ["-map", "1:3"] == restore_command[
        restore_command.index("1:3") - 1:
        restore_command.index("1:3") + 1
    ]
    assert ["-map", "1:4"] == restore_command[
        restore_command.index("1:4") - 1:
        restore_command.index("1:4") + 1
    ]
    assert restore_command[
        restore_command.index("-map_metadata") + 1
    ] == "1"
    assert restore_command[
        restore_command.index("-map_chapters") + 1
    ] == "0"
    disposition_index = restore_command.index("-disposition:v:1")
    assert restore_command[disposition_index + 1] == "attached_pic"

def test_valid_trim_range_builds_new_output_plan(tmp_path):
    source = tmp_path / "source.mp4"
    source.write_bytes(b"source")
    output = tmp_path / "trimmed.mp4"
    context = OperationContext(
        source=source,
        media=media_info(source),
        output=output,
        start_seconds=2.5,
        end_seconds=7.25,
    )

    plan = TrimAdapter().build_plan(context)

    assert plan.output == output
    assert plan.replace_source is False


def test_trim_end_exceeding_duration_is_silently_clamped(tmp_path, monkeypatch):
    """End times beyond the video duration are silently clamped."""
    source = tmp_path / "source.mp4"
    source.write_bytes(b"source")
    output = tmp_path / "trimmed.mp4"
    calls = {}

    def fake_trim_video(**kwargs):
        calls.update(kwargs)
        kwargs["output"].write_bytes(b"trimmed")
        return kwargs["output"]

    monkeypatch.setattr(
        "fix.plugins.trim.adapter.trim_video",
        fake_trim_video,
    )
    monkeypatch.setattr(
        "fix.plugins.trim.adapter.validate_output",
        lambda path: None,
    )

    plan = TrimAdapter().build_plan(OperationContext(
        source=source,
        media=media_info(source, duration=10.0),
        output=output,
        start_seconds=8.0,
        end_seconds=15.0,
    ))
    plan.runner(lambda fraction, label: None)

    assert calls["start_seconds"] == 8.0
    assert calls["end_seconds"] == 10.0
