from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from fix.plugins import build_registry


def test_builtin_plugins_are_registered():
    registry = build_registry()
    ids = {plugin.metadata.plugin_id for plugin in registry.all()}
    assert {
        "remove_watermark",
        "watermark_overlay",
        "cover_art",
        "trim",
    } <= ids
