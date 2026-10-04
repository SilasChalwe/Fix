from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from fix.core.errors import PluginValidationError
from fix.core.models import MediaInfo, OperationContext, Selection
from fix.plugins.watermark_overlay.adapter import WatermarkOverlayAdapter


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


def test_rejects_missing_watermark_image_path(tmp_path):
    source = tmp_path / "source.mp4"
    source.write_bytes(b"video")
    missing_watermark = tmp_path / "missing.png"
    context = OperationContext(
        source=source,
        media=make_media(source),
        selections=(Selection(10, 10, 100, 100),),
        asset=missing_watermark,
        duration_seconds=2.0,
    )

    with pytest.raises(
        PluginValidationError,
        match="Choose a watermark image first",
    ):
        WatermarkOverlayAdapter().build_plan(context)


def test_rejects_empty_selections(tmp_path):
    source = tmp_path / "source.mp4"
    watermark = tmp_path / "watermark.png"
    source.write_bytes(b"video")
    watermark.write_bytes(b"image")
    context = OperationContext(
        source=source,
        media=make_media(source),
        asset=watermark,
        duration_seconds=2.0,
    )

    with pytest.raises(
        PluginValidationError,
        match="Draw at least one selection first",
    ):
        WatermarkOverlayAdapter().build_plan(context)


def test_builds_plan_for_well_formed_context(tmp_path):
    source = tmp_path / "source.mp4"
    watermark = tmp_path / "watermark.png"
    source.write_bytes(b"video")
    watermark.write_bytes(b"image")
    context = OperationContext(
        source=source,
        media=make_media(source),
        selections=(Selection(10, 10, 100, 100),),
        asset=watermark,
        duration_seconds=2.0,
    )

    plan = WatermarkOverlayAdapter().build_plan(context)

    assert plan.label == "Add / Replace Watermark"
    assert plan.output == source
    assert plan.replace_source is True
    assert callable(plan.runner)
