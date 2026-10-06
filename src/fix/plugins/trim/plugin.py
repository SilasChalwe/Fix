from __future__ import annotations

from fix.core.plugin import FixPlugin, PluginMetadata
from .adapter import TrimAdapter


# UI NOTE: This plugin is backend-only in this PR.
# A dedicated GTK Trim tab will be added in a follow-up
# contribution under the GTK desktop UI workstream.
class TrimPlugin(FixPlugin):
    metadata = PluginMetadata(
        plugin_id="trim",
        name="Trim Video",
        version="1.0.0",
        description="Trim a video to a start and end time while preserving its media metadata.",
    )

    def create_adapter(self) -> TrimAdapter:
        return TrimAdapter()
