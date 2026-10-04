from pathlib import Path
import sys
from unittest.mock import patch

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from fix.core.errors import MediaProcessingError
from fix.core.models import MediaInfo
from fix.media.validation import validate_output


def make_media(path: Path) -> MediaInfo:
    return MediaInfo(
        path=path,
        duration=5.0,
        width=320,
        height=240,
        fps=30.0,
        video_codec="h264",
        video_bitrate=500_000,
        size_bytes=100,
    )


def test_valid_video_path_passes_validation(tmp_path):
    video = tmp_path / "video.mp4"
    video.write_bytes(b"video")

    with patch(
        "fix.media.validation.probe_media",
        return_value=make_media(video),
    ):
        validate_output(video)


def test_nonexistent_path_fails_with_media_processing_error(tmp_path):
    missing = tmp_path / "missing.mp4"

    with pytest.raises(
        MediaProcessingError,
        match="Expected output file was not created",
    ):
        validate_output(missing)


def test_non_media_file_fails_with_media_processing_error(tmp_path):
    text_file = tmp_path / "not-media.txt"
    text_file.write_text("not a video", encoding="utf-8")

    with patch(
        "fix.media.validation.probe_media",
        side_effect=MediaProcessingError("No primary video stream was found."),
    ):
        with pytest.raises(
            MediaProcessingError,
            match="No primary video stream was found",
        ):
            validate_output(text_file)
