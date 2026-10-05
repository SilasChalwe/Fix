# FIX — Watermark & Video Asset Toolkit

FIX is a local-first desktop video-processing application for creative professionals, media teams, video editors, designers, photographers, content producers, and developers.

The current build provides visual watermark removal, watermark overlay/replacement, embedded cover replacement, reusable video-region selections, configurable watermark duration, and FFmpeg/FFprobe-based media processing.

## Current Features

- Open local video files.
- Seek to a frame using the position slider.
- Draw one or more reusable selections on the video.
- Move an existing selection by dragging it.
- Remove watermark regions with FFmpeg `delogo`.
- Replace embedded cover/thumbnail artwork.
- Load a watermark image and preview it inside the existing selection.
- Choose how many seconds the watermark should appear.
- Start the watermark from the currently selected video time.
- Add the new watermark without deleting an existing watermark underneath it.
- Re-encode only the affected keyframe/GOP interval for watermark overlay where practical.
- Stream-copy unchanged sections.
- Restore source cover artwork, metadata, chapters and compatible attachments after localized watermark editing.
- Process media locally.

## Platform Support

FIX uses one shared codebase.

- **Linux:** currently verified desktop runtime.
- **Windows:** contributors are welcome for platform-neutral work; full desktop runtime/packaging support is planned under M5.
- **macOS:** contributors are welcome for platform-neutral work; full desktop runtime/packaging support is planned under M5.

Operating-system support is infrastructure/packaging work, not a media plugin. Do not create Windows/macOS copies of the media engine or plugin architecture.

See [docs/PLATFORM_SUPPORT.md](docs/PLATFORM_SUPPORT.md) for the current support policy.

## Architecture Contract

The repository structure is defined. Contributors must not invent a second project structure.

New user-facing media operations are plugins by default.

```text
Fix/
├── app.py
├── run.sh
├── requirements.txt
├── LICENSE.txt
├── README.md
├── .gitignore
│
├── src/
│   └── fix/
│       ├── main.py
│       ├── core/
│       │   ├── models.py
│       │   ├── plugin.py
│       │   ├── registry.py
│       │   ├── executor.py
│       │   └── errors.py
│       ├── media/
│       │   ├── ffmpeg.py
│       │   ├── ffprobe.py
│       │   └── validation.py
│       ├── ui/
│       │   ├── main_window.py
│       │   └── video_canvas.py
│       └── plugins/
│           ├── remove_watermark/
│           ├── watermark_overlay/
│           └── cover_art/
│
├── tests/
├── docs/
├── assets/
└── scripts/
    └── check_dependencies.py
```

## Plugin-Based Design

The project uses a plugin + adapter model.

```text
GTK UI
  |
  v
OperationContext
  |
  v
Plugin Registry
  |
  v
Plugin
  |
  v
Plugin Adapter
  |
  v
OperationPlan
  |
  v
Core Executor
  |
  +--> shared FFmpeg / FFprobe services
  |
  v
Validation / Result
```

Every media feature should use:

```text
src/fix/plugins/<plugin_name>/
├── __init__.py
├── plugin.py
└── adapter.py
```

A plugin identifies the capability.

Its adapter validates shared application state and converts that state into an `OperationPlan`.

Plugins must not create their own coordinate system, plugin registry, application state, or unmanaged subprocess architecture.

## Shared Selection State

Selections are global application state.

Conceptually:

```python
selections = [
    Selection(x, y, width, height),
]
```

A selection drawn in Remove Watermark remains the same selection when the user switches to Replace Watermark.

Choosing a watermark image does not create another rectangle.

A second rectangle exists only when the user intentionally draws another one.

## Media Processing Model

For a short watermark overlay:

```text
unchanged beginning
        |
        | stream copy
        v
affected keyframe / GOP interval
        |
        | encode required pixels
        v
unchanged ending
        |
        | stream copy
        v
restore metadata / cover
        |
        v
validated media
```

The overlay operation modifies the source in place only after temporary processing succeeds.

Watermark removal and cover replacement produce separate output files by default.

## Technology

- Python
- GTK 4 / PyGObject
- Cairo / GDK
- OpenCV
- FFmpeg
- FFprobe

## Running

The currently verified desktop workflow is Linux and uses the system Python installation.

```bash
chmod +x run.sh
./run.sh
```

Or:

```bash
/usr/bin/python3 app.py
```

Windows/macOS contributors should follow [docs/PLATFORM_SUPPORT.md](docs/PLATFORM_SUPPORT.md) for platform-neutral contribution guidance. Do not assume the Linux launcher represents full cross-platform runtime support.

## Dependency Check

```bash
/usr/bin/python3 scripts/check_dependencies.py
```

Typical Ubuntu packages include:

```text
python3-gi
gir1.2-gtk-4.0
python3-gi-cairo
python3-cairo
python3-opencv
ffmpeg
```

The application does not silently download dependencies at startup.

## Contributor Rules

1. Follow the repository structure.
2. New media features are plugins by default.
3. Shared infrastructure belongs in `core/` or `media/`.
4. GTK presentation belongs in `ui/`.
5. Do not create another selection-state system.
6. Do not duplicate the FFmpeg/FFprobe engine inside plugins or per operating system.
7. Keep platform-specific code at the launch/setup/packaging/platform-integration boundary where practical.
8. Do not commit client media, credentials, private keys, tokens, or confidential assets.
9. Add tests for new processing behavior.
10. Keep changes limited to the assigned workstream.
11. Update documentation when a plugin or platform-support contract changes.

## Contributor Roadmap

Contributor work is phase-gated. See [ROADMAP.md](ROADMAP.md) and roadmap issue #3 before starting work.

Only the first incomplete milestone is active for implementation. Later milestones remain blocked until the previous gate is complete.

## Development Workstreams

Contributors may work on:

- GTK desktop UI;
- FFmpeg/FFprobe media engine;
- plugin development;
- computer vision;
- codec compatibility;
- metadata preservation;
- testing and QA;
- packaging;
- documentation;
- creative workflow validation.

## License

FIX is licensed under the MIT License. See [LICENSE.txt](LICENSE.txt) for the full license text.
