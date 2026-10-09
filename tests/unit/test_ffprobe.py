import json
import subprocess
from pathlib import Path
import sys
from unittest.mock import patch

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from fix.core.errors import MediaProcessingError
from fix.media.ffprobe import keyframes, probe_media


def probe_payload():
    return {
        "streams": [
            {
                "index": 0,
                "codec_type": "video",
                "codec_name": "h264",
                "width": 320,
                "height": 240,
                "duration": "4.5",
                "avg_frame_rate": "30/1",
                "bit_rate": "500000",
                "disposition": {"attached_pic": 0},
            },
            {"index": 1, "codec_type": "audio", "codec_name": "aac"},
            {
                "index": 2,
                "codec_type": "video",
                "codec_name": "h264",
                "width": 160,
                "height": 120,
                "disposition": {"attached_pic": 0},
            },
            {
                "index": 3,
                "codec_type": "video",
                "codec_name": "mjpeg",
                "disposition": {"attached_pic": 1},
            },
            {"index": 4, "codec_type": "attachment", "codec_name": "ttf"},
        ],
        "format": {"duration": "4.5"},
    }


def completed_probe(stdout: str, returncode: int = 0):
    return subprocess.CompletedProcess(
        args=["ffprobe"],
        returncode=returncode,
        stdout=stdout,
        stderr="",
    )


def test_probe_media_returns_float_duration_for_valid_media(tmp_path):
    media = tmp_path / "video.mp4"
    media.write_bytes(b"media")

    with patch(
        "fix.media.ffprobe.subprocess.run",
        return_value=completed_probe(json.dumps(probe_payload())),
    ):
        info = probe_media(media)

    assert isinstance(info.duration, float)
    assert info.duration == 4.5
    assert info.additional_video_streams == (2,)
    assert info.attached_picture_streams == (3,)
    assert info.attachment_streams == (4,)


def test_probe_media_raises_for_missing_file(tmp_path):
    missing = tmp_path / "missing.mp4"

    with patch(
        "fix.media.ffprobe.subprocess.run",
        return_value=completed_probe(
            "",
            returncode=1,
        ),
    ):
        with pytest.raises(MediaProcessingError, match="FFprobe failed"):
            probe_media(missing)


def test_keyframes_returns_non_empty_list_for_valid_media(tmp_path):
    media = tmp_path / "video.mp4"
    media.write_bytes(b"media")

    with patch(
        "fix.media.ffprobe.subprocess.run",
        return_value=completed_probe("0.000000\n2.000000\n"),
    ):
        frames = keyframes(media)

    assert frames == [0.0, 2.0]
    assert frames
