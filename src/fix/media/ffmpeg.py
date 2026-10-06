from __future__ import annotations

import os
import subprocess
import tempfile
from pathlib import Path

from fix.core.errors import MediaProcessingError
from fix.core.models import MediaInfo, ProgressCallback, Selection
from .ffprobe import keyframes, probe_media


def run_command(
    cmd: list[str],
    progress: ProgressCallback,
    fraction: float,
    label: str,
) -> None:
    progress(fraction, label)
    result = subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    if result.returncode != 0:
        raise MediaProcessingError(
            result.stderr[-4000:].strip()
            or f"{label} failed."
        )


def encoding_args(media: MediaInfo) -> list[str]:
    codec = media.video_codec.lower()

    bitrate = media.video_bitrate
    if not bitrate and media.duration > 0:
        # Conservative approximation of source video bitrate from file size.
        total_bps = int((media.size_bytes * 8) / media.duration)
        bitrate = max(250_000, int(total_bps * 0.90))

    if codec in {"hevc", "h265"}:
        args = ["-c:v:0", "libx265", "-preset", "medium"]
    else:
        args = ["-c:v:0", "libx264", "-preset", "medium"]

    if bitrate:
        args += [
            "-b:v:0", str(bitrate),
            "-maxrate:v:0", str(int(bitrate * 1.15)),
            "-bufsize:v:0", str(int(bitrate * 2.0)),
        ]
    else:
        args += ["-crf", "22"]

    return args


def _attached_picture_maps(media: MediaInfo) -> list[str]:
    args: list[str] = []
    for index in media.attached_picture_streams:
        args += ["-map", f"0:{index}"]
    return args


def _attached_picture_codecs(media: MediaInfo) -> list[str]:
    args: list[str] = []
    # Output video stream 0 is the processed main video.
    for out_index, _ in enumerate(media.attached_picture_streams, start=1):
        args += [
            f"-c:v:{out_index}", "copy",
            f"-disposition:v:{out_index}", "attached_pic",
        ]
    return args


def _delogo_chain(
    selections: tuple[Selection, ...],
    width: int,
    height: int,
) -> str:
    chain: list[str] = []
    previous = "[0:v:0]"

    for idx, selection in enumerate(selections):
        pad = 2
        x = max(1, selection.x - pad)
        y = max(1, selection.y - pad)
        right = min(width - 1, selection.x + selection.width + pad)
        bottom = min(height - 1, selection.y + selection.height + pad)
        w = max(2, right - x)
        h = max(2, bottom - y)
        output = "[v]" if idx == len(selections) - 1 else f"[d{idx}]"
        chain.append(
            f"{previous}"
            f"delogo=x={x}:y={y}:w={w}:h={h}:show=0"
            f"{output}"
        )
        previous = output

    return ";".join(chain)


def remove_watermark(
    source: Path,
    output: Path,
    selections: tuple[Selection, ...],
    media: MediaInfo,
    progress: ProgressCallback,
) -> Path:
    if not selections:
        raise MediaProcessingError("No watermark selection was provided.")

    output.parent.mkdir(parents=True, exist_ok=True)
    filter_complex = _delogo_chain(
        selections,
        media.width,
        media.height,
    )

    cmd = [
        "ffmpeg", "-y",
        "-hide_banner", "-loglevel", "error",
        "-i", str(source),
        "-filter_complex", filter_complex,
        "-map", "[v]",
        "-map", "0:a?",
        "-map", "0:s?",
        "-map", "0:t?",
        *_attached_picture_maps(media),
        *encoding_args(media),
        "-c:a", "copy",
        "-c:s", "copy",
        "-c:t", "copy",
        *_attached_picture_codecs(media),
        "-map_metadata", "0",
        "-map_chapters", "0",
        str(output),
    ]

    run_command(cmd, progress, 0.10, "Removing watermark…")
    progress(1.0, f"Saved: {output.name}")
    return output


def replace_cover(
    source: Path,
    cover: Path,
    output: Path,
    media: MediaInfo,
    progress: ProgressCallback,
) -> Path:
    output.parent.mkdir(parents=True, exist_ok=True)

    cmd = [
        "ffmpeg", "-y",
        "-hide_banner", "-loglevel", "error",
        "-i", str(source),
        "-i", str(cover),
        "-map", "0:v:0",
        "-map", "0:a?",
        "-map", "0:s?",
        "-map", "0:t?",
        "-map", "1:v:0",
        "-c:v:0", "copy",
        "-c:a", "copy",
        "-c:s", "copy",
        "-c:t", "copy",
        "-c:v:1", "mjpeg",
        "-disposition:v:1", "attached_pic",
        "-map_metadata", "0",
        "-map_chapters", "0",
        str(output),
    ]

    run_command(cmd, progress, 0.15, "Replacing embedded cover…")
    progress(1.0, f"Saved: {output.name}")
    return output


def trim_video(
    source: Path,
    output: Path,
    start_seconds: float,
    end_seconds: float,
    media: MediaInfo,
    progress: ProgressCallback,
) -> Path:
    """Trim accurately by copying only when the start is keyframe-aligned.

    A keyframe-aligned start uses stream copy for a fast, exact cut. Other
    starts re-encode only the video stream while copying audio, subtitles,
    attachments, metadata, and chapters.
    """
    output.parent.mkdir(parents=True, exist_ok=True)

    common = [
        "ffmpeg", "-y",
        "-hide_banner", "-loglevel", "error",
        "-i", str(source),
        "-ss", f"{start_seconds:.6f}",
        "-t", f"{end_seconds - start_seconds:.6f}",
    ]

    progress(0.03, "Checking keyframe alignment…")
    keyframe_aligned = any(
        abs(timestamp - start_seconds) <= 1e-6
        for timestamp in keyframes(source)
    )

    if keyframe_aligned:
        cmd = [
            *common,
            "-map", "0",
            "-map_metadata", "0",
            "-map_chapters", "0",
            "-c", "copy",
            str(output),
        ]
        run_command(cmd, progress, 0.10, "Copying keyframe-aligned streams…")
    else:
        cmd = [
            "ffmpeg", "-y",
            "-hide_banner", "-loglevel", "error",
            "-fflags", "+genpts",
            "-i", str(source),
            "-ss", f"{start_seconds:.6f}",
            "-t", f"{end_seconds - start_seconds:.6f}",
            *encoding_args(media),
            "-bf", "0",
            "-c:a", "copy",
            "-c:s", "copy",
            "-c:t", "copy",
            *_attached_picture_codecs(media),
            "-use_editlist", "0",
            str(output),
        ]
        run_command(cmd, progress, 0.20, "Re-encoding video for accuracy…")

    progress(1.0, f"Saved: {output.name}")
    return output


def _keyframe_window(
    source: Path,
    duration: float,
    edit_start: float,
    edit_end: float,
) -> tuple[float, float]:
    values = keyframes(source)

    if not values:
        # Safe fallback: encode a small window around the requested interval.
        return max(0.0, edit_start - 2.0), min(duration, edit_end + 2.0)

    before = [t for t in values if t <= edit_start]
    after = [t for t in values if t >= edit_end]

    key_start = max(before) if before else 0.0
    key_end = min(after) if after else duration

    if key_end <= key_start:
        key_end = min(duration, edit_end + 2.0)

    return max(0.0, key_start), min(duration, key_end)


def _overlay_filter(
    selections: tuple[Selection, ...],
    local_start: float,
    local_end: float,
) -> str:
    filters: list[str] = []
    count = len(selections)

    if count == 1:
        selection = selections[0]
        filters.append(
            f"[1:v]"
            f"scale={selection.width}:{selection.height}"
            f"[wm0]"
        )
        filters.append(
            f"[0:v:0][wm0]"
            f"overlay={selection.x}:{selection.y}:"
            f"enable='between(t,{local_start:.6f},{local_end:.6f})':"
            f"shortest=1"
            f"[v]"
        )
        return ";".join(filters)

    split_outputs = "".join(f"[wms{i}]" for i in range(count))
    filters.append(f"[1:v]split={count}{split_outputs}")

    for i, selection in enumerate(selections):
        filters.append(
            f"[wms{i}]"
            f"scale={selection.width}:{selection.height}"
            f"[wm{i}]"
        )

    previous = "[0:v:0]"
    for i, selection in enumerate(selections):
        output = "[v]" if i == count - 1 else f"[stage{i}]"
        filters.append(
            f"{previous}[wm{i}]"
            f"overlay={selection.x}:{selection.y}:"
            f"enable='between(t,{local_start:.6f},{local_end:.6f})':"
            f"shortest=1"
            f"{output}"
        )
        previous = output

    return ";".join(filters)


def overlay_watermark_local(
    source: Path,
    watermark: Path,
    selections: tuple[Selection, ...],
    media: MediaInfo,
    edit_start: float,
    edit_duration: float,
    progress: ProgressCallback,
) -> Path:
    if not selections:
        raise MediaProcessingError("No watermark selection was provided.")
    if edit_duration <= 0:
        raise MediaProcessingError("Watermark duration must be greater than zero.")

    edit_start = max(0.0, min(edit_start, media.duration))
    edit_end = min(media.duration, edit_start + edit_duration)

    if edit_end <= edit_start:
        raise MediaProcessingError("The selected time is at the end of the video.")

    progress(0.03, "Inspecting keyframes…")
    key_start, key_end = _keyframe_window(
        source,
        media.duration,
        edit_start,
        edit_end,
    )

    suffix = source.suffix.lower()
    if suffix not in {".mkv", ".mp4", ".mov"}:
        suffix = ".mkv"

    with tempfile.TemporaryDirectory(
        prefix=".pulse_edit_",
        dir=str(source.parent),
    ) as td_name:
        td = Path(td_name)
        before = td / f"before{suffix}"
        middle = td / f"middle{suffix}"
        after = td / f"after{suffix}"
        assembled = td / f"assembled{suffix}"
        restored = td / f"restored{suffix}"
        concat_file = td / "parts.txt"

        parts: list[Path] = []

        if key_start > 0.001:
            cmd = [
                "ffmpeg", "-y",
                "-hide_banner", "-loglevel", "error",
                "-i", str(source),
                "-t", f"{key_start:.6f}",
                "-map", "0:v:0",
                "-map", "0:a?",
                "-map", "0:s?",
                "-c", "copy",
                "-avoid_negative_ts", "make_zero",
                str(before),
            ]
            run_command(
                cmd,
                progress,
                0.12,
                "Copying unchanged beginning…",
            )
            parts.append(before)

        segment_duration = max(0.001, key_end - key_start)
        local_start = edit_start - key_start
        local_end = edit_end - key_start
        filter_complex = _overlay_filter(
            selections,
            local_start,
            local_end,
        )

        cmd = [
            "ffmpeg", "-y",
            "-hide_banner", "-loglevel", "error",
            "-ss", f"{key_start:.6f}",
            "-t", f"{segment_duration:.6f}",
            "-i", str(source),
            "-loop", "1",
            "-framerate", f"{max(media.fps, 1.0):.6f}",
            "-i", str(watermark),
            "-filter_complex", filter_complex,
            "-map", "[v]",
            "-map", "0:a?",
            "-map", "0:s?",
            *encoding_args(media),
            "-pix_fmt", "yuv420p",
            "-c:a", "copy",
            "-c:s", "copy",
            "-t", f"{segment_duration:.6f}",
            str(middle),
        ]

        run_command(
            cmd,
            progress,
            0.32,
            "Encoding only the affected section…",
        )
        parts.append(middle)

        if key_end < media.duration - 0.001:
            cmd = [
                "ffmpeg", "-y",
                "-hide_banner", "-loglevel", "error",
                "-ss", f"{key_end:.6f}",
                "-i", str(source),
                "-map", "0:v:0",
                "-map", "0:a?",
                "-map", "0:s?",
                "-c", "copy",
                "-avoid_negative_ts", "make_zero",
                str(after),
            ]
            run_command(
                cmd,
                progress,
                0.62,
                "Copying unchanged ending…",
            )
            parts.append(after)

        concat_file.write_text(
            "".join(f"file '{part.name}'\n" for part in parts),
            encoding="utf-8",
        )

        cmd = [
            "ffmpeg", "-y",
            "-hide_banner", "-loglevel", "error",
            "-f", "concat",
            "-safe", "0",
            "-i", str(concat_file),
            "-map", "0:v:0",
            "-map", "0:a?",
            "-map", "0:s?",
            "-c", "copy",
            str(assembled),
        ]

        run_command(
            cmd,
            progress,
            0.78,
            "Joining edited section…",
        )

        # Restore the source's attached cover, attachments, metadata and chapters.
        restore_cmd = [
            "ffmpeg", "-y",
            "-hide_banner", "-loglevel", "error",
            "-i", str(assembled),
            "-i", str(source),
            "-map", "0:v:0",
            "-map", "0:a?",
            "-map", "0:s?",
        ]

        # Attached picture video streams from the original source.
        for stream_index in media.attached_picture_streams:
            restore_cmd += ["-map", f"1:{stream_index}"]

        # MKV or container attachments from the original source.
        for stream_index in media.attachment_streams:
            restore_cmd += ["-map", f"1:{stream_index}"]

        restore_cmd += [
            "-map_metadata", "1",
            "-map_chapters", "1",
            "-c", "copy",
            str(restored),
        ]

        run_command(
            restore_cmd,
            progress,
            0.90,
            "Restoring cover and metadata…",
        )

        original_mode = source.stat().st_mode
        os.chmod(restored, original_mode)
        os.replace(restored, source)

    progress(1.0, "Watermark overlay complete.")
    return source
