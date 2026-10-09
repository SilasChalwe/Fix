from __future__ import annotations

import json
import subprocess
from pathlib import Path

from fix.core.errors import MediaProcessingError
from fix.core.models import MediaInfo


def _run_json(args: list[str]) -> dict:
    result = subprocess.run(
        args,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    if result.returncode != 0:
        raise MediaProcessingError(
            result.stderr.strip() or "FFprobe failed."
        )
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise MediaProcessingError("FFprobe returned invalid JSON.") from exc


def _fps(value: str | None) -> float:
    if not value:
        return 0.0
    if "/" in value:
        n, d = value.split("/", 1)
        try:
            d_val = float(d)
            return float(n) / d_val if d_val else 0.0
        except ValueError:
            return 0.0
    try:
        return float(value)
    except ValueError:
        return 0.0


def probe_media(path: Path) -> MediaInfo:
    data = _run_json([
        "ffprobe",
        "-v", "error",
        "-show_streams",
        "-show_format",
        "-of", "json",
        str(path),
    ])

    streams = data.get("streams", [])
    video_stream = None
    additional_videos: list[int] = []
    attached_pictures: list[int] = []
    attachments: list[int] = []

    for stream in streams:
        codec_type = stream.get("codec_type")
        index = stream.get("index")
        disposition = stream.get("disposition") or {}

        if (
            codec_type == "video"
            and disposition.get("attached_pic", 0) == 1
        ):
            if index is not None:
                attached_pictures.append(int(index))
            continue

        if codec_type == "video":
            if video_stream is None:
                video_stream = stream
            elif index is not None:
                additional_videos.append(int(index))

        if codec_type == "attachment" and index is not None:
            attachments.append(int(index))

    if video_stream is None:
        raise MediaProcessingError("No primary video stream was found.")

    fmt = data.get("format") or {}

    duration = float(
        video_stream.get("duration")
        or fmt.get("duration")
        or 0.0
    )

    bitrate_raw = (
        video_stream.get("bit_rate")
        or fmt.get("bit_rate")
    )
    try:
        bitrate = int(bitrate_raw) if bitrate_raw else None
    except (TypeError, ValueError):
        bitrate = None

    return MediaInfo(
        path=path,
        duration=duration,
        width=int(video_stream.get("width") or 0),
        height=int(video_stream.get("height") or 0),
        fps=_fps(
            video_stream.get("avg_frame_rate")
            or video_stream.get("r_frame_rate")
        ),
        video_codec=str(video_stream.get("codec_name") or ""),
        video_bitrate=bitrate,
        size_bytes=path.stat().st_size,
        additional_video_streams=tuple(additional_videos),
        attached_picture_streams=tuple(attached_pictures),
        attachment_streams=tuple(attachments),
    )


def keyframes(path: Path) -> list[float]:
    result = subprocess.run(
        [
            "ffprobe",
            "-v", "error",
            "-select_streams", "v:0",
            "-skip_frame", "nokey",
            "-show_frames",
            "-show_entries", "frame=best_effort_timestamp_time",
            "-of", "csv=p=0",
            str(path),
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    if result.returncode != 0:
        raise MediaProcessingError(
            result.stderr.strip() or "Could not inspect keyframes."
        )

    values: list[float] = []
    for line in result.stdout.splitlines():
        text = line.strip().strip(",")
        if not text:
            continue
        try:
            values.append(float(text.split(",")[0]))
        except ValueError:
            continue
    return values
