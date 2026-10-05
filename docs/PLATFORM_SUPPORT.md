# Platform Support

FIX uses one shared codebase across all operating systems.

## Current support status

| Platform | Contributor work | Full desktop runtime |
| --- | --- | --- |
| Linux | Supported | Currently verified |
| Windows | Supported for platform-neutral work | Planned under M5 |
| macOS | Supported for platform-neutral work | Planned under M5 |

Windows and macOS contributors may work now on platform-neutral areas such as:

- `src/fix/core/`
- `src/fix/media/`
- `src/fix/plugins/`
- tests and validation
- FFmpeg/FFprobe behavior
- codec and metadata compatibility
- documentation

## Architecture rule

Operating-system support is not a media plugin.

Do not create:

- a Windows media plugin;
- a macOS media plugin;
- a second FFmpeg/FFprobe engine for another OS;
- separate copies of FIX core/media/plugin code for each platform.

Platform-specific code should stay at the launch, dependency-discovery, setup, packaging, and OS-integration boundary where practical.

## Current runtime

Linux is the currently verified desktop runtime. The existing `run.sh` and `/usr/bin/python3` workflow are Linux-specific.

Windows/macOS contributors should use their local Python environment plus FFmpeg/FFprobe for platform-neutral development. The full GTK application should not be advertised as officially supported on Windows or macOS until the relevant M5 platform work is complete and independently validated.

Active contributor-enablement work is tracked in issue #16.

## Planned M5 platform work

- #17 — Windows development, runtime and packaging support
- #18 — macOS development, runtime and packaging support
- #19 — Linux/Windows/macOS validation matrix
- #20 — Cross-platform 1.0 release artifacts and installation docs
