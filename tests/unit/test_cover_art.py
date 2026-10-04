from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from fix.core.errors import PluginValidationError
from fix.core.models import MediaInfo, OperationContext
from fix.plugins.cover_art.adapter import CoverArtAdapter


def make_media(path: Path) -> MediaInfo:
    return MediaInfo(
        path=path,
        duration=10.0,
        width=1280,
        height=720,
        fps=30.0,
        video_codec="h264",
        video_bitrate=1_000_000,
        size_bytes=1000,
    )


def test_rejects_missing_cover_image_path(tmp_path):
    source = tmp_path / "source.mp4"
    source.write_bytes(b"video")
    context = OperationContext(
        source=source,
        media=make_media(source),
        asset=tmp_path / "missing.png",
        output=tmp_path / "output.mp4",
    )

    with pytest.raises(PluginValidationError, match="Choose a cover image first"):
        CoverArtAdapter().build_plan(context)


def test_rejects_missing_video_path(tmp_path):
    source = tmp_path / "missing.mp4"
    cover = tmp_path / "cover.jpg"
    cover.write_bytes(b"image")
    context = OperationContext(
        source=source,
        media=make_media(source),
        asset=cover,
        output=tmp_path / "output.mp4",
    )

    with pytest.raises(PluginValidationError, match="Source video does not exist"):
        CoverArtAdapter().build_plan(context)


def test_builds_plan_for_well_formed_context(tmp_path):
    source = tmp_path / "source.mp4"
    cover = tmp_path / "cover.jpg"
    output = tmp_path / "output.mp4"
    source.write_bytes(b"video")
    cover.write_bytes(b"image")
    context = OperationContext(
        source=source,
        media=make_media(source),
        asset=cover,
        output=output,
    )

    plan = CoverArtAdapter().build_plan(context)

    assert plan.label == "Thumbnail / Cover"
    assert plan.output == output
    assert plan.replace_source is False
    assert callable(plan.runner)
