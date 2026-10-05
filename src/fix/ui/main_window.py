from __future__ import annotations

import threading
from pathlib import Path

import cv2
import gi
gi.require_version("Gtk", "4.0")

from gi.repository import Gtk, Gdk, GdkPixbuf, GLib, Pango

from fix.core.executor import OperationExecutor
from fix.core.models import OperationContext, Selection
from fix.media.ffprobe import probe_media
from fix.plugins import build_registry
from .video_canvas import VideoCanvas


class MainWindow(Gtk.ApplicationWindow):
    def __init__(self, application):
        super().__init__(application=application)
        self.set_title("FIX — Watermark & Video Asset Toolkit")
        self.set_default_size(1400, 860)
        self._install_css()

        self.registry = build_registry()
        self.executor = OperationExecutor()

        self.video_path: Path | None = None
        self.media = None
        self.selections: list[Selection] = []
        self.processing = False

        self.cover_path: Path | None = None
        self.watermark_path: Path | None = None
        self.remove_output: Path | None = None
        self.cover_output: Path | None = None

        header = Gtk.HeaderBar()
        header.add_css_class("app-header")
        title = Gtk.Label(label="🎬  FIX — Watermark & Video Asset Toolkit")
        title.add_css_class("app-title")
        header.set_title_widget(title)
        self.set_titlebar(header)

        root = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=0,
        )
        root.add_css_class("app-root")
        self.set_child(root)

        source_bar = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            spacing=14,
        )
        source_bar.add_css_class("source-bar")
        source_bar.set_margin_top(14)
        source_bar.set_margin_bottom(14)
        source_bar.set_margin_start(18)
        source_bar.set_margin_end(18)
        root.append(source_bar)

        open_button = Gtk.Button(label="▱  Open Video")
        open_button.add_css_class("primary")
        open_button.connect("clicked", self._open_video)
        source_bar.append(open_button)

        self.video_name = Gtk.Label(label="No video selected")
        self.video_name.set_xalign(0)
        self.video_name.set_hexpand(True)
        self.video_name.set_ellipsize(Pango.EllipsizeMode.END)
        self.video_name.add_css_class("file-name")
        source_bar.append(self.video_name)

        self.media_badge = Gtk.Label(label="No media")
        self.media_badge.add_css_class("media-badge")
        source_bar.append(self.media_badge)

        workspace = Gtk.Paned(
            orientation=Gtk.Orientation.HORIZONTAL,
        )
        workspace.set_vexpand(True)
        workspace.set_position(860)
        workspace.set_resize_start_child(True)
        workspace.set_shrink_start_child(True)
        workspace.set_resize_end_child(False)
        workspace.set_shrink_end_child(True)
        root.append(workspace)

        left = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=12,
        )
        left.set_margin_start(18)
        left.set_margin_end(10)
        left.set_margin_top(10)
        left.set_margin_bottom(10)

        canvas_card = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=0,
        )
        canvas_card.add_css_class("video-card")
        canvas_card.set_vexpand(True)
        left.append(canvas_card)

        self.canvas = VideoCanvas(self._selection_changed)
        self.canvas.set_vexpand(True)
        canvas_card.append(self.canvas)

        transport = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            spacing=10,
        )
        transport.add_css_class("transport")
        transport.set_margin_top(8)
        transport.set_margin_bottom(8)
        transport.set_margin_start(10)
        transport.set_margin_end(10)
        canvas_card.append(transport)

        show_frame = Gtk.Button(label="▶")
        show_frame.add_css_class("round-control")
        show_frame.set_tooltip_text("Show the frame at the selected time")
        show_frame.connect("clicked", self._show_frame)
        transport.append(show_frame)

        self.time_label = Gtk.Label(label="00:00.0 / 00:00.0")
        self.time_label.add_css_class("time-label")
        transport.append(self.time_label)

        self.time_scale = Gtk.Scale.new_with_range(
            Gtk.Orientation.HORIZONTAL,
            0.0,
            1.0,
            0.1,
        )
        self.time_scale.set_hexpand(True)
        self.time_scale.set_draw_value(False)
        self.time_scale.connect(
            "value-changed",
            self._time_changed,
        )
        transport.append(self.time_scale)

        workspace.set_start_child(left)

        sidebar = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=0,
        )
        sidebar.set_size_request(420, -1)
        sidebar.add_css_class("sidebar")
        sidebar.set_margin_start(6)
        sidebar.set_margin_end(18)
        sidebar.set_margin_top(10)
        sidebar.set_margin_bottom(10)

        self.stack = Gtk.Stack()
        self.stack.set_transition_type(
            Gtk.StackTransitionType.CROSSFADE
        )
        self.stack.connect(
            "notify::visible-child-name",
            self._tab_changed,
        )

        switcher = Gtk.StackSwitcher()
        switcher.set_stack(self.stack)
        switcher.set_hexpand(True)
        switcher.add_css_class("operation-tabs")
        sidebar.append(switcher)

        controls_scroll = Gtk.ScrolledWindow()
        controls_scroll.set_policy(
            Gtk.PolicyType.NEVER,
            Gtk.PolicyType.AUTOMATIC,
        )
        controls_scroll.set_vexpand(True)
        controls_scroll.set_child(self.stack)
        sidebar.append(controls_scroll)

        self._build_remove_tab()
        self._build_cover_tab()
        self._build_overlay_tab()
        workspace.set_end_child(sidebar)

        timeline = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=8,
        )
        timeline.add_css_class("timeline-card")
        timeline.set_margin_start(18)
        timeline.set_margin_end(18)
        timeline.set_margin_top(4)
        timeline.set_margin_bottom(10)
        root.append(timeline)

        timeline_header = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            spacing=10,
        )
        timeline.append(timeline_header)

        timeline_title = Gtk.Label(label="◷  Timeline")
        timeline_title.set_xalign(0)
        timeline_title.set_hexpand(True)
        timeline_title.add_css_class("section-title")
        timeline_header.append(timeline_title)

        frame_button = Gtk.Button(label="Show Frame")
        frame_button.connect("clicked", self._show_frame)
        timeline_header.append(frame_button)

        timeline_scroll = Gtk.ScrolledWindow()
        timeline_scroll.set_policy(
            Gtk.PolicyType.AUTOMATIC,
            Gtk.PolicyType.NEVER,
        )
        timeline_scroll.set_min_content_height(82)
        timeline.append(timeline_scroll)

        self.timeline_strip = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            spacing=6,
        )
        self.timeline_strip.set_margin_top(2)
        self.timeline_strip.set_margin_bottom(2)
        self.timeline_strip.set_margin_start(2)
        self.timeline_strip.set_margin_end(2)
        timeline_scroll.set_child(self.timeline_strip)

        placeholder = Gtk.Label(
            label="Open a video to build the timeline preview"
        )
        placeholder.add_css_class("muted")
        placeholder.set_margin_start(12)
        placeholder.set_margin_top(24)
        self.timeline_strip.append(placeholder)

        self.progress = Gtk.ProgressBar()
        self.progress.add_css_class("progress-line")
        root.append(self.progress)

        status_bar = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            spacing=12,
        )
        status_bar.add_css_class("status-bar")
        status_bar.set_margin_start(18)
        status_bar.set_margin_end(18)
        status_bar.set_margin_top(10)
        status_bar.set_margin_bottom(12)
        root.append(status_bar)

        self.status = Gtk.Label(label="●  Ready.")
        self.status.set_xalign(0)
        self.status.set_hexpand(True)
        self.status.add_css_class("status-text")
        status_bar.append(self.status)

        self.status_meta = Gtk.Label(label="No video loaded")
        self.status_meta.add_css_class("muted")
        status_bar.append(self.status_meta)

    def _install_css(self) -> None:
        css = b"""
        window, .app-root {
            background: #0b0f17;
            color: #f4f6fb;
        }

        headerbar.app-header {
            background: #111620;
            color: #f8f8fb;
            border-bottom: 1px solid #262d39;
            min-height: 54px;
        }

        .app-title {
            font-weight: bold;
            font-size: 16px;
        }

        .source-bar {
            background: #0f141e;
            border-bottom: 1px solid #202735;
        }

        .file-name {
            color: #edf0f5;
            font-size: 14px;
        }

        .media-badge {
            background: #151b27;
            color: #dce1eb;
            border: 1px solid #262f3e;
            border-radius: 12px;
            padding: 10px 14px;
        }

        button {
            color: #f7f7fb;
            background: #171e2a;
            border: 1px solid #2a3342;
            border-radius: 10px;
            padding: 9px 13px;
        }

        button:hover {
            background: #202938;
        }

        button.primary {
            color: white;
            font-weight: bold;
            background-image: linear-gradient(to right, #8c164f, #b11e69);
            border-color: #b11e69;
        }

        button.primary:hover {
            background-image: linear-gradient(to right, #a31b5c, #c52777);
        }

        button.danger-soft {
            background: #161b26;
            color: #ff6da7;
        }

        .video-card, .card, .timeline-card {
            background: #101620;
            border: 1px solid #222b39;
            border-radius: 16px;
        }

        .video-card {
            padding: 0;
        }

        .transport {
            background: #0e141e;
            border-top: 1px solid #222b39;
        }

        .round-control {
            border-radius: 999px;
            min-width: 36px;
            min-height: 36px;
            padding: 4px;
        }

        .time-label {
            color: #eef1f6;
            font-variant-numeric: tabular-nums;
        }

        .sidebar {
            background: #0d121b;
            border: 1px solid #202836;
            border-radius: 16px;
        }

        .operation-tabs {
            background: #101620;
            border-bottom: 1px solid #252e3c;
            padding: 6px;
        }

        .operation-tabs button {
            border: 0;
            border-radius: 9px;
            background: transparent;
            padding: 10px 12px;
        }

        .operation-tabs button:checked {
            background-image: linear-gradient(to right, #7f174a, #a41b60);
            color: white;
        }

        .card {
            padding: 14px;
        }

        .section-title {
            color: #ffffff;
            font-weight: bold;
            font-size: 15px;
        }

        .muted {
            color: #9ca5b4;
        }

        .selection-chip {
            background-image: linear-gradient(to right, #6d173f, #54152f);
            border: 1px solid #87204f;
            border-radius: 13px;
            padding: 12px;
        }

        .timeline-card {
            padding: 12px;
        }

        .timeline-thumb {
            background: #111823;
            border: 1px solid #2a3444;
            border-radius: 9px;
            padding: 2px;
        }

        .timeline-thumb:hover {
            border-color: #e24586;
        }

        .status-bar {
            background: #0f141e;
        }

        .status-text {
            color: #dce5ef;
        }

        .progress-line trough {
            min-height: 3px;
            background: #171e2a;
        }

        .progress-line progress {
            background-image: linear-gradient(to right, #8c164f, #d13a82);
        }

        scale trough {
            background: #343d4e;
            min-height: 5px;
            border-radius: 999px;
        }

        scale highlight {
            background: #a71f61;
            border-radius: 999px;
        }

        scale slider {
            background: #ffffff;
            border: 2px solid #b5276b;
            min-width: 13px;
            min-height: 13px;
            border-radius: 999px;
        }

        spinbutton, dropdown {
            background: #171e2a;
            color: #f6f7fb;
            border: 1px solid #2a3342;
            border-radius: 9px;
        }
        """
        provider = Gtk.CssProvider()
        provider.load_from_data(css)
        display = Gdk.Display.get_default()
        if display is not None:
            Gtk.StyleContext.add_provider_for_display(
                display,
                provider,
                Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
            )

    @staticmethod
    def _card() -> Gtk.Box:
        box = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=10,
        )
        box.add_css_class("card")
        box.set_margin_top(10)
        box.set_margin_bottom(4)
        box.set_margin_start(10)
        box.set_margin_end(10)
        return box

    @staticmethod
    def _section_title(text: str) -> Gtk.Label:
        label = Gtk.Label(label=text)
        label.set_xalign(0)
        label.add_css_class("section-title")
        return label

    def _build_remove_tab(self):
        page = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=6,
        )

        selections = self._card()
        header = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            spacing=8,
        )
        title = self._section_title("▱  Selections")
        title.set_hexpand(True)
        header.append(title)

        clear_button = Gtk.Button(label="Clear All")
        clear_button.add_css_class("danger-soft")
        clear_button.connect("clicked", self._clear_selections)
        header.append(clear_button)
        selections.append(header)

        help_text = Gtk.Label(
            label="Draw one or more areas on the video to remove watermarks."
        )
        help_text.set_xalign(0)
        help_text.set_wrap(True)
        help_text.add_css_class("muted")
        selections.append(help_text)

        selection_chip = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=3,
        )
        selection_chip.add_css_class("selection-chip")
        selections.append(selection_chip)

        self.selection_summary = Gtk.Label(label="No selections yet")
        self.selection_summary.set_xalign(0)
        self.selection_summary.add_css_class("section-title")
        selection_chip.append(self.selection_summary)

        self.selection_coords = Gtk.Label(
            label="Draw directly on the video preview."
        )
        self.selection_coords.set_xalign(0)
        self.selection_coords.add_css_class("muted")
        selection_chip.append(self.selection_coords)

        output = self._card()
        output.append(self._section_title("Output"))
        choose = Gtk.Button(label="Choose Save Location")
        choose.connect("clicked", self._choose_remove_output)
        output.append(choose)

        self.remove_output_label = Gtk.Label(label="Automatic")
        self.remove_output_label.set_xalign(0)
        self.remove_output_label.set_wrap(True)
        self.remove_output_label.add_css_class("muted")
        output.append(self.remove_output_label)

        action = Gtk.Button(label="▶  Remove Watermark")
        action.add_css_class("primary")
        action.connect("clicked", self._start_remove)
        output.append(action)

        page.append(selections)
        page.append(output)

        self.stack.add_titled(
            page,
            "remove",
            "Remove Watermark",
        )

    def _build_cover_tab(self):
        page = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=6,
        )

        asset = self._card()
        asset.append(self._section_title("Thumbnail / Cover"))

        choose = Gtk.Button(label="Choose Cover Image")
        choose.connect("clicked", self._choose_cover)
        asset.append(choose)

        self.cover_label = Gtk.Label(label="No cover selected")
        self.cover_label.set_xalign(0)
        self.cover_label.set_wrap(True)
        self.cover_label.add_css_class("muted")
        asset.append(self.cover_label)

        output = self._card()
        output.append(self._section_title("Output"))

        output_button = Gtk.Button(label="Choose Save Location")
        output_button.connect("clicked", self._choose_cover_output)
        output.append(output_button)

        self.cover_output_label = Gtk.Label(label="Automatic")
        self.cover_output_label.set_xalign(0)
        self.cover_output_label.set_wrap(True)
        self.cover_output_label.add_css_class("muted")
        output.append(self.cover_output_label)

        action = Gtk.Button(label="▶  Replace Thumbnail / Cover")
        action.add_css_class("primary")
        action.connect("clicked", self._start_cover)
        output.append(action)

        page.append(asset)
        page.append(output)

        self.stack.add_titled(
            page,
            "cover",
            "Thumbnail / Cover",
        )

    def _build_overlay_tab(self):
        page = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=6,
        )

        asset = self._card()
        asset.append(self._section_title("Replace Watermark"))

        help_text = Gtk.Label(
            label=(
                "The current selection is reused. Choosing an image "
                "does not create another rectangle."
            )
        )
        help_text.set_xalign(0)
        help_text.set_wrap(True)
        help_text.add_css_class("muted")
        asset.append(help_text)

        choose = Gtk.Button(label="Choose Watermark Image")
        choose.connect("clicked", self._choose_watermark)
        asset.append(choose)

        self.watermark_label = Gtk.Label(label="No watermark selected")
        self.watermark_label.set_xalign(0)
        self.watermark_label.set_wrap(True)
        self.watermark_label.add_css_class("muted")
        asset.append(self.watermark_label)

        duration_row = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            spacing=8,
        )
        duration_label = Gtk.Label(label="Watermark duration")
        duration_label.set_hexpand(True)
        duration_label.set_xalign(0)
        duration_row.append(duration_label)

        self.watermark_duration = Gtk.SpinButton.new_with_range(
            0.1,
            3600.0,
            0.5,
        )
        self.watermark_duration.set_value(1.0)
        self.watermark_duration.set_digits(1)
        duration_row.append(self.watermark_duration)
        duration_row.append(Gtk.Label(label="seconds"))
        asset.append(duration_row)

        action = Gtk.Button(label="▶  Add / Replace Watermark")
        action.add_css_class("primary")
        action.connect("clicked", self._start_overlay)
        asset.append(action)

        page.append(asset)

        self.stack.add_titled(
            page,
            "overlay",
            "Replace Watermark",
        )

    def _clear_timeline(self) -> None:
        child = self.timeline_strip.get_first_child()
        while child is not None:
            next_child = child.get_next_sibling()
            self.timeline_strip.remove(child)
            child = next_child

    def _rebuild_timeline(self) -> None:
        self._clear_timeline()
        if not self.video_path or self.media is None:
            return

        cap = cv2.VideoCapture(str(self.video_path))
        duration = max(float(self.media.duration), 0.1)
        sample_count = 9

        try:
            for index in range(sample_count):
                timestamp = duration * index / max(sample_count - 1, 1)
                cap.set(
                    cv2.CAP_PROP_POS_MSEC,
                    timestamp * 1000.0,
                )
                ok, frame = cap.read()
                if not ok or frame is None:
                    continue

                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                height, width = rgb.shape[:2]
                data = GLib.Bytes.new(rgb.tobytes())
                pixbuf = GdkPixbuf.Pixbuf.new_from_bytes(
                    data,
                    GdkPixbuf.Colorspace.RGB,
                    False,
                    8,
                    width,
                    height,
                    width * 3,
                )
                thumb = pixbuf.scale_simple(
                    132,
                    74,
                    GdkPixbuf.InterpType.BILINEAR,
                )

                image = Gtk.Image.new_from_pixbuf(thumb)
                button = Gtk.Button()
                button.add_css_class("timeline-thumb")
                button.set_child(image)
                button.set_tooltip_text(self._fmt_time(timestamp))
                button.connect(
                    "clicked",
                    self._timeline_jump,
                    timestamp,
                )
                self.timeline_strip.append(button)
        finally:
            cap.release()

    def _timeline_jump(self, button, timestamp: float) -> None:
        self.time_scale.set_value(timestamp)
        self._show_frame()

    def _message(self, text: str) -> None:
        self.status.set_text(text)

    @staticmethod
    def _fmt_time(value: float) -> str:
        value = max(0.0, value)
        minutes = int(value // 60)
        seconds = value - minutes * 60
        return f"{minutes:02d}:{seconds:04.1f}"

    def _time_changed(self, scale) -> None:
        current = float(scale.get_value())
        duration = self.media.duration if self.media else 0.0
        self.time_label.set_text(
            f"{self._fmt_time(current)} / {self._fmt_time(duration)}"
        )

    def _selection_changed(self, values: list[Selection]) -> None:
        self.selections = list(values)
        if values:
            last = values[-1]
            self.selection_summary.set_text(
                f"Selection {len(values)}"
                if len(values) == 1
                else f"{len(values)} selections"
            )
            self.selection_coords.set_text(
                f"X: {last.x}   Y: {last.y}   "
                f"W: {last.width}   H: {last.height}"
            )
            self.status.set_text(
                f"●  Ready — {len(values)} selection(s)"
            )
        else:
            self.selection_summary.set_text("No selections yet")
            self.selection_coords.set_text(
                "Draw directly on the video preview."
            )
            self.status.set_text("●  Ready — no selections")

    def _clear_selections(self, button=None) -> None:
        self.canvas.set_selections([])
        self._selection_changed([])

    def _tab_changed(self, stack, _param) -> None:
        self.canvas.set_preview_visible(
            stack.get_visible_child_name() == "overlay"
        )

    def _open_video(self, button) -> None:
        dialog = Gtk.FileChooserNative.new(
            "Open Video",
            self,
            Gtk.FileChooserAction.OPEN,
            "_Open",
            "_Cancel",
        )

        video_filter = Gtk.FileFilter()
        video_filter.set_name("Video files")
        for pattern in (
            "*.mp4", "*.mkv", "*.mov",
            "*.avi", "*.webm", "*.m4v",
        ):
            video_filter.add_pattern(pattern)
        dialog.add_filter(video_filter)

        def response(dlg, response_id):
            if response_id == Gtk.ResponseType.ACCEPT:
                file = dlg.get_file()
                path = file.get_path() if file else None
                if path:
                    try:
                        self._load_video(Path(path))
                    except Exception as exc:
                        self._message(str(exc))
            dlg.destroy()

        dialog.connect("response", response)
        dialog.show()

    def _load_video(self, path: Path) -> None:
        self.media = probe_media(path)
        self.video_path = path
        self.video_name.set_text(path.name)

        self.time_scale.set_range(0.0, max(self.media.duration, 0.1))
        self.time_scale.set_value(0.0)

        media_type = path.suffix.lstrip(".").upper() or "VIDEO"
        self.media_badge.set_text(
            f"{self.media.width} × {self.media.height}   |   "
            f"{self._fmt_time(self.media.duration)}   |   {media_type}"
        )
        self.status_meta.set_text(
            f"Video: {self.media.width}×{self.media.height}   |   "
            f"Duration: {self._fmt_time(self.media.duration)}"
        )

        self.remove_output = None
        self.cover_output = None
        self.remove_output_label.set_text("Automatic")
        self.cover_output_label.set_text("Automatic")

        self._clear_selections()
        self._show_frame()
        self._rebuild_timeline()
        self.status.set_text(
            f"●  Ready — {path.name}"
        )

    def _show_frame(self, button=None) -> None:
        if not self.video_path:
            self._message("Open a video first.")
            return

        cap = cv2.VideoCapture(str(self.video_path))
        cap.set(
            cv2.CAP_PROP_POS_MSEC,
            float(self.time_scale.get_value()) * 1000.0,
        )
        ok, frame = cap.read()
        cap.release()

        if not ok or frame is None:
            self._message("Could not read the selected video frame.")
            return

        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        height, width = rgb.shape[:2]
        rowstride = width * 3
        data = GLib.Bytes.new(rgb.tobytes())
        pixbuf = GdkPixbuf.Pixbuf.new_from_bytes(
            data,
            GdkPixbuf.Colorspace.RGB,
            False,
            8,
            width,
            height,
            rowstride,
        )
        self.canvas.set_frame(pixbuf, width, height)

    def _choose_image(self, title, callback) -> None:
        dialog = Gtk.FileChooserNative.new(
            title,
            self,
            Gtk.FileChooserAction.OPEN,
            "_Open",
            "_Cancel",
        )

        image_filter = Gtk.FileFilter()
        image_filter.set_name("Image files")
        for pattern in ("*.png", "*.jpg", "*.jpeg", "*.webp", "*.bmp"):
            image_filter.add_pattern(pattern)
        dialog.add_filter(image_filter)

        def response(dlg, response_id):
            if response_id == Gtk.ResponseType.ACCEPT:
                file = dlg.get_file()
                path = file.get_path() if file else None
                if path:
                    callback(Path(path))
            dlg.destroy()

        dialog.connect("response", response)
        dialog.show()

    def _choose_cover(self, button) -> None:
        def selected(path: Path):
            self.cover_path = path
            self.cover_label.set_text(path.name)
        self._choose_image("Choose Cover Image", selected)

    def _choose_watermark(self, button) -> None:
        def selected(path: Path):
            self.watermark_path = path
            self.watermark_label.set_text(path.name)
            self.canvas.set_watermark_preview(str(path))
            self.status.set_text(
                "Watermark preview loaded into the existing selection(s)."
                if self.selections
                else "Watermark selected. Draw a selection when ready."
            )
        self._choose_image("Choose Watermark Image", selected)

    def _choose_save_path(
        self,
        title: str,
        suggested: Path | None,
        callback,
    ) -> None:
        dialog = Gtk.FileChooserNative.new(
            title,
            self,
            Gtk.FileChooserAction.SAVE,
            "_Save",
            "_Cancel",
        )
        if suggested is not None:
            dialog.set_current_name(suggested.name)

        def response(dlg, response_id):
            if response_id == Gtk.ResponseType.ACCEPT:
                file = dlg.get_file()
                path = file.get_path() if file else None
                if path:
                    callback(Path(path))
            dlg.destroy()

        dialog.connect("response", response)
        dialog.show()

    def _default_output(self, suffix: str) -> Path:
        assert self.video_path is not None
        return self.video_path.with_name(
            f"{self.video_path.stem}{suffix}{self.video_path.suffix}"
        )

    def _choose_remove_output(self, button) -> None:
        suggested = (
            self._default_output("_watermark_removed")
            if self.video_path
            else None
        )

        def selected(path: Path):
            self.remove_output = path
            self.remove_output_label.set_text(str(path))

        self._choose_save_path(
            "Save Removed-Watermark Video",
            suggested,
            selected,
        )

    def _choose_cover_output(self, button) -> None:
        suggested = (
            self._default_output("_cover_replaced")
            if self.video_path
            else None
        )

        def selected(path: Path):
            self.cover_output = path
            self.cover_output_label.set_text(str(path))

        self._choose_save_path(
            "Save Cover-Replaced Video",
            suggested,
            selected,
        )

    def _context(
        self,
        *,
        output: Path | None = None,
        asset: Path | None = None,
        duration: float | None = None,
    ) -> OperationContext:
        if not self.video_path or self.media is None:
            raise RuntimeError("Open a video first.")

        return OperationContext(
            source=self.video_path,
            media=self.media,
            selections=tuple(self.selections),
            output=output,
            start_seconds=float(self.time_scale.get_value()),
            duration_seconds=duration,
            asset=asset,
        )

    def _start_remove(self, button) -> None:
        if not self.video_path:
            self._message("Open a video first.")
            return

        output = self.remove_output or self._default_output(
            "_watermark_removed"
        )

        try:
            context = self._context(output=output)
            adapter = self.registry.get(
                "remove_watermark"
            ).create_adapter()
            plan = adapter.build_plan(context)
        except Exception as exc:
            self._message(str(exc))
            return

        self._run_plan(plan)

    def _start_cover(self, button) -> None:
        if not self.video_path:
            self._message("Open a video first.")
            return

        output = self.cover_output or self._default_output(
            "_cover_replaced"
        )

        try:
            context = self._context(
                output=output,
                asset=self.cover_path,
            )
            adapter = self.registry.get(
                "cover_art"
            ).create_adapter()
            plan = adapter.build_plan(context)
        except Exception as exc:
            self._message(str(exc))
            return

        self._run_plan(plan)

    def _start_overlay(self, button) -> None:
        try:
            context = self._context(
                asset=self.watermark_path,
                duration=float(
                    self.watermark_duration.get_value()
                ),
            )
            adapter = self.registry.get(
                "watermark_overlay"
            ).create_adapter()
            plan = adapter.build_plan(context)
        except Exception as exc:
            self._message(str(exc))
            return

        self._run_plan(plan, reload_after=True)

    def _run_plan(self, plan, reload_after=False) -> None:
        if self.processing:
            self._message("Another operation is already running.")
            return

        self.processing = True
        self.progress.set_fraction(0.0)
        self.status.set_text(plan.label)

        def progress_callback(fraction, text):
            GLib.idle_add(
                self._set_progress,
                float(fraction),
                str(text),
            )

        def worker():
            try:
                result = self.executor.execute(
                    plan,
                    progress_callback,
                )
                GLib.idle_add(
                    self._finish_plan,
                    result,
                    reload_after,
                )
            except Exception as exc:
                GLib.idle_add(
                    self._fail_plan,
                    str(exc),
                )

        threading.Thread(
            target=worker,
            daemon=True,
        ).start()

    def _set_progress(self, fraction: float, text: str):
        self.progress.set_fraction(
            max(0.0, min(1.0, fraction))
        )
        self.status.set_text(text)
        return False

    def _finish_plan(self, result: Path, reload_after: bool):
        self.processing = False
        self.progress.set_fraction(1.0)
        self.status.set_text(f"Completed: {result}")

        if reload_after and self.video_path:
            try:
                self.media = probe_media(self.video_path)
                self._show_frame()
            except Exception:
                pass

        return False

    def _fail_plan(self, message: str):
        self.processing = False
        self.progress.set_fraction(0.0)
        self.status.set_text(f"Failed: {message}")
        return False
