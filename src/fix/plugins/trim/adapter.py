from __future__ import annotations

import math
from pathlib import Path

from fix.core.errors import PluginValidationError
from fix.core.models import OperationContext, OperationPlan
from fix.core.plugin import PluginAdapter
from fix.media.ffmpeg import trim_video
from fix.media.validation import validate_output


class TrimAdapter(PluginAdapter):
    def _end_seconds(self, context: OperationContext) -> float | None:
        try:
            if context.end_seconds is not None:
                return float(context.end_seconds)
            option_end = context.options.get("end_seconds")
            if option_end is not None:
                return float(option_end)
            if context.duration_seconds is not None:
                return context.start_seconds + float(context.duration_seconds)
        except (TypeError, ValueError):
            return None
        return None

    def validate(self, context: OperationContext) -> None:
        if not context.source.exists():
            raise PluginValidationError("Source video does not exist.")
        if context.output is None:
            raise PluginValidationError("Output path is required.")
        if Path(context.output) == context.source:
            raise PluginValidationError("Trim output must be a new file.")

        end_seconds = self._end_seconds(context)
        if (
            not math.isfinite(context.start_seconds)
            or end_seconds is None
            or not math.isfinite(end_seconds)
        ):
            raise PluginValidationError(
                "Trim start and end times must be finite numbers."
            )
        if context.start_seconds < 0:
            raise PluginValidationError("Trim start time cannot be negative.")
        if end_seconds <= context.start_seconds:
            raise PluginValidationError(
                "Trim end time must be greater than the start time."
            )
        if context.start_seconds >= context.media.duration:
            raise PluginValidationError(
                "Trim start time must be inside the video duration."
            )

    def build_plan(self, context: OperationContext) -> OperationPlan:
        self.validate(context)
        output = Path(context.output)
        # End times beyond the video duration are silently clamped to the video duration.
        end_seconds = min(
            float(self._end_seconds(context)),
            context.media.duration,
        )

        def runner(progress):
            result = trim_video(
                source=context.source,
                output=output,
                start_seconds=float(context.start_seconds),
                end_seconds=end_seconds,
                media=context.media,
                progress=progress,
            )
            validate_output(result)
            return result

        return OperationPlan(
            label="Trim Video",
            runner=runner,
            output=output,
        )
