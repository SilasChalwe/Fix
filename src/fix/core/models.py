from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable


ProgressCallback = Callable[[float, str], None]


@dataclass(frozen=True)
class Selection:
    x: int
    y: int
    width: int
    height: int

    def as_tuple(self) -> tuple[int, int, int, int]:
        return self.x, self.y, self.width, self.height


@dataclass(frozen=True)
class MediaInfo:
    path: Path
    duration: float
    width: int
    height: int
    fps: float
    video_codec: str
    video_bitrate: int | None
    size_bytes: int
    attached_picture_streams: tuple[int, ...] = ()
    attachment_streams: tuple[int, ...] = ()


@dataclass
class OperationContext:
    source: Path
    media: MediaInfo
    selections: tuple[Selection, ...] = ()
    output: Path | None = None
    start_seconds: float = 0.0
    duration_seconds: float | None = None
    end_seconds: float | None = None
    asset: Path | None = None
    options: dict[str, Any] = field(default_factory=dict)


@dataclass
class OperationPlan:
    label: str
    runner: Callable[[ProgressCallback], Path]
    output: Path | None = None
    replace_source: bool = False
