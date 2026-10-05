from __future__ import annotations

import threading
from pathlib import Path

import cv2
import gi
gi.require_version("Gtk", "4.0")

from gi.repository import Gtk, GdkPixbuf, GLib

from fix.core.executor import OperationExecutor
from fix.core.models import OperationContext, Selection
from fix.media.ffprobe import probe_media
from fix.plugins import build_registry
from .video_canvas import VideoCanvas


class MainWindow(Gtk.ApplicationWindow):
    def __init__(self, application):
        super().__init__(application=application)
        self.set_title("FIX — Watermark & Video Asset Toolkit")
        self.set_default_size(1100, 820)

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

        root = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=10,
        )
        root.set_margin_top(12)
        root.set_margin_bottom(12)
        root.set_margin_start(12)
        root.set_margin_end(12)
        self.set_child(root)

        source_row = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            spacing=8,
        )
        root.append(source_row)

        open_button = Gtk.Button(label="Open Video")
        open_button.connect("clicked", self._open_video)
        source_row.append(open_button)

        self.video_name = Gtk.Label(label="No video selected")
        self.video_name.set_xalign(0)
        self.video_name.set_hexpand(True)
        source_row.append(self.video_name)

        self.time_scale = Gtk.Scale.new_with_range(
            Gtk.Orientation.HORIZONTAL,
            0.0,
            1.0,
            0.1,
        )
        self.time_scale.set_hexpand(True)
        self.time_scale.set_draw_value(False)
        root.append(self.time_scale)

        time_row = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            spacing=8,
        )
        root.append(time_row)

        show_frame = Gtk.Button(label="Show Frame")
        show_frame.connect("clicked", self._show_frame)
        time_row.append(show_frame)

        self.time_label = Gtk.Label(label="00:00.0 / 00:00.0")
        time_row.append(self.time_label)

        self.time_scale.connect(
            "value-changed",
            self._time_changed,
        )

        self.canvas = VideoCanvas(self._selection_changed)
        self.canvas.set_vexpand(True)
        root.append(self.canvas)

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
        root.append(switcher)

        controls_scroll = Gtk.ScrolledWindow()
        controls_scroll.set_policy(
            Gtk.PolicyType.NEVER,
            Gtk.PolicyType.AUTOMATIC,
        )
        controls_scroll.set_propagate_natural_height(True)
        controls_scroll.set_max_content_height(240)
        controls_scroll.set_child(self.stack)
        root.append(controls_scroll)

        self._build_remove_tab()
        self._build_cover_tab()
        self._build_overlay_tab()

        status_row = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            spacing=10,
        )
        root.append(status_row)

        self.progress = Gtk.ProgressBar()
        self.progress.set_hexpand(True)
        status_row.append(self.progress)

        self.status = Gtk.Label(label="Ready.")
        self.status.set_xalign(0)
        self.status.set_hexpand(True)
        root.append(self.status)

    def _build_remove_tab(self):
        box = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=8,
        )
        box.set_margin_top(10)

        box.append(Gtk.Label(
            label=(
                "Draw one or more selections on the video. "
                "The same selections are shared across all operations."
            ),
            xalign=0,
        ))

        row = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            spacing=8,
        )
        box.append(row)

        choose = Gtk.Button(label="Choose Save Location")
        choose.connect("clicked", self._choose_remove_output)
        row.append(choose)

        self.remove_output_label = Gtk.Label(label="Automatic")
        self.remove_output_label.set_xalign(0)
        self.remove_output_label.set_hexpand(True)
        row.append(self.remove_output_label)

        clear_button = Gtk.Button(label="Clear Selections")
        clear_button.connect("clicked", self._clear_selections)
        box.append(clear_button)

        action = Gtk.Button(label="Remove Watermark")
        action.connect("clicked", self._start_remove)
        box.append(action)

        self.stack.add_titled(
            box,
            "remove",
            "Remove Watermark",
        )

    def _build_cover_tab(self):
        box = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=8,
        )
        box.set_margin_top(10)

        row = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            spacing=8,
        )
        box.append(row)

        choose = Gtk.Button(label="Choose Cover Image")
        choose.connect("clicked", self._choose_cover)
        row.append(choose)

        self.cover_label = Gtk.Label(label="No cover selected")
        self.cover_label.set_xalign(0)
        self.cover_label.set_hexpand(True)
        row.append(self.cover_label)

        output_row = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            spacing=8,
        )
        box.append(output_row)

        output_button = Gtk.Button(label="Choose Save Location")
        output_button.connect("clicked", self._choose_cover_output)
        output_row.append(output_button)

        self.cover_output_label = Gtk.Label(label="Automatic")
        self.cover_output_label.set_xalign(0)
        self.cover_output_label.set_hexpand(True)
        output_row.append(self.cover_output_label)

        action = Gtk.Button(label="Replace Thumbnail / Cover")
        action.connect("clicked", self._start_cover)
        box.append(action)

        self.stack.add_titled(
            box,
            "cover",
            "Thumbnail / Cover",
        )

    def _build_overlay_tab(self):
        box = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=8,
        )
        box.set_margin_top(10)

        box.append(Gtk.Label(
            label=(
                "The current selection is reused. "
                "Choosing an image does not create another rectangle."
            ),
            xalign=0,
        ))

        row = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            spacing=8,
        )
        box.append(row)

        choose = Gtk.Button(label="Choose Watermark Image")
        choose.connect("clicked", self._choose_watermark)
        row.append(choose)

        self.watermark_label = Gtk.Label(label="No watermark selected")
        self.watermark_label.set_xalign(0)
        self.watermark_label.set_hexpand(True)
        row.append(self.watermark_label)

        duration_row = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            spacing=8,
        )
        box.append(duration_row)

        duration_row.append(Gtk.Label(label="Watermark duration"))
        self.watermark_duration = Gtk.SpinButton.new_with_range(
            0.1,
            3600.0,
            0.5,
        )
        self.watermark_duration.set_value(1.0)
        self.watermark_duration.set_digits(1)
        duration_row.append(self.watermark_duration)
        duration_row.append(Gtk.Label(label="seconds"))

        action = Gtk.Button(label="Add / Replace Watermark")
        action.connect("clicked", self._start_overlay)
        box.append(action)

        self.stack.add_titled(
            box,
            "overlay",
            "Replace Watermark",
        )

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
            self.status.set_text(
                f"{len(values)} selection(s). "
                f"Last: x={last.x}, y={last.y}, "
                f"w={last.width}, h={last.height}"
            )
        else:
            self.status.set_text("No selections.")

    def _clear_selections(self, button=None) -> None:
        self.selections = []
        self.canvas.set_selections([])
        self.status.set_text("Selections cleared.")

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

        self.remove_output = None
        self.cover_output = None
        self.remove_output_label.set_text("Automatic")
        self.cover_output_label.set_text("Automatic")

        self._clear_selections()
        self._show_frame()
        self.status.set_text(
            f"Loaded {path.name} — "
            f"{self.media.width}×{self.media.height}, "
            f"{self.media.video_codec}, "
            f"{self.media.duration:.1f}s"
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
