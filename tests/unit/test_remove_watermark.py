from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from fix.core.errors import PluginValidationError
from fix.core.models import MediaInfo, OperationContext, Selection
from fix.plugins.remove_watermark.adapter import RemoveWatermarkAdapter


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


def test_rejects_missing_video_path(tmp_path):
    source = tmp_path / "missing.mp4"
    context = OperationContext(
        source=source,
        media=make_media(source),
        selections=(Selection(10, 10, 100, 100),),
        output=tmp_path / "output.mp4",
    )

    with pytest.raises(PluginValidationError, match="Source video does not exist"):
        RemoveWatermarkAdapter().build_plan(context)


def test_rejects_empty_selections(tmp_path):
    source = tmp_path / "source.mp4"
    source.write_bytes(b"video")
    context = OperationContext(
        source=source,
        media=make_media(source),
        output=tmp_path / "output.mp4",
    )

    with pytest.raises(
        PluginValidationError,
        match="Draw at least one selection first",
    ):
        RemoveWatermarkAdapter().build_plan(context)


def test_builds_plan_for_well_formed_context(tmp_path):
    source = tmp_path / "source.mp4"
    output = tmp_path / "output.mp4"
    source.write_bytes(b"video")
    context = OperationContext(
        source=source,
        media=make_media(source),
        selections=(Selection(10, 10, 100, 100),),
        output=output,
    )

    plan = RemoveWatermarkAdapter().build_plan(context)

    assert plan.label == "Remove Watermark"
    assert plan.output == output
    assert plan.replace_source is False
    assert callable(plan.runner)
