from __future__ import annotations

import gi
gi.require_version("Gtk", "4.0")

from gi.repository import Gtk, Gdk, GdkPixbuf

from fix.core.models import Selection


class VideoCanvas(Gtk.DrawingArea):
    def __init__(self, on_selection_changed):
        super().__init__()
        self.set_hexpand(True)
        self.set_vexpand(True)
        # Keep a useful initial canvas size without forcing the application
        # window to retain a large minimum width or height.
        self.set_content_width(320)
        self.set_content_height(180)

        self.frame_pixbuf: GdkPixbuf.Pixbuf | None = None
        self.frame_width = 0
        self.frame_height = 0

        self.selections: list[Selection] = []
        self.watermark_preview: GdkPixbuf.Pixbuf | None = None
        self.show_preview = False

        self.offset_x = 0.0
        self.offset_y = 0.0
        self.display_scale = 1.0
        self.draw_w = 0.0
        self.draw_h = 0.0

        self.drag_kind: str | None = None
        self.drag_start: tuple[float, float] | None = None
        self.drag_current: tuple[float, float] | None = None
        self.move_start: Selection | None = None
        self.move_index: int | None = None
        self.resize_handle: str | None = None

        self.on_selection_changed = on_selection_changed

        self.set_draw_func(self._draw)

        drag = Gtk.GestureDrag()
        drag.connect("drag-begin", self._drag_begin)
        drag.connect("drag-update", self._drag_update)
        drag.connect("drag-end", self._drag_end)
        self.add_controller(drag)

    def set_frame(
        self,
        pixbuf: GdkPixbuf.Pixbuf,
        width: int,
        height: int,
    ) -> None:
        self.frame_pixbuf = pixbuf
        self.frame_width = width
        self.frame_height = height
        self.queue_draw()

    def clear_frame(self) -> None:
        self.frame_pixbuf = None
        self.frame_width = 0
        self.frame_height = 0
        self.queue_draw()

    def set_selections(self, values: list[Selection]) -> None:
        self.selections = list(values)
        self.queue_draw()

    def set_watermark_preview(self, path: str | None) -> None:
        if not path:
            self.watermark_preview = None
            self.queue_draw()
            return
        try:
            self.watermark_preview = GdkPixbuf.Pixbuf.new_from_file(path)
        except Exception:
            self.watermark_preview = None
        self.queue_draw()

    def set_preview_visible(self, visible: bool) -> None:
        self.show_preview = visible
        self.queue_draw()

    def _fit_geometry(self, width: int, height: int) -> None:
        if self.frame_width <= 0 or self.frame_height <= 0:
            return

        scale = min(
            width / self.frame_width,
            height / self.frame_height,
        )
        self.display_scale = max(scale, 0.0001)
        self.draw_w = self.frame_width * self.display_scale
        self.draw_h = self.frame_height * self.display_scale
        self.offset_x = (width - self.draw_w) / 2.0
        self.offset_y = (height - self.draw_h) / 2.0

    def _inside_image(self, x: float, y: float) -> bool:
        return (
            self.offset_x <= x <= self.offset_x + self.draw_w
            and self.offset_y <= y <= self.offset_y + self.draw_h
        )

    def _screen_rect(self, selection: Selection):
        return (
            self.offset_x + selection.x * self.display_scale,
            self.offset_y + selection.y * self.display_scale,
            selection.width * self.display_scale,
            selection.height * self.display_scale,
        )

    @staticmethod
    def _handle_points(
        sx: float,
        sy: float,
        sw: float,
        sh: float,
    ) -> dict[str, tuple[float, float]]:
        cx = sx + sw / 2.0
        cy = sy + sh / 2.0
        return {
            "nw": (sx, sy),
            "n": (cx, sy),
            "ne": (sx + sw, sy),
            "e": (sx + sw, cy),
            "se": (sx + sw, sy + sh),
            "s": (cx, sy + sh),
            "sw": (sx, sy + sh),
            "w": (sx, cy),
        }

    def _draw(self, area, cr, width, height):
        cr.set_source_rgba(0.06, 0.07, 0.08, 1.0)
        cr.rectangle(0, 0, width, height)
        cr.fill()

        if self.frame_pixbuf is None:
            cr.set_source_rgba(1, 1, 1, 0.70)
            cr.select_font_face("Sans")
            cr.set_font_size(18)
            text = "Open a video to begin"
            ext = cr.text_extents(text)
            cr.move_to(
                (width - ext.width) / 2,
                (height + ext.height) / 2,
            )
            cr.show_text(text)
            return

        self._fit_geometry(width, height)

        cr.save()
        cr.translate(self.offset_x, self.offset_y)
        cr.scale(self.display_scale, self.display_scale)
        Gdk.cairo_set_source_pixbuf(cr, self.frame_pixbuf, 0, 0)
        cr.paint()
        cr.restore()

        for index, selection in enumerate(self.selections):
            sx, sy, sw, sh = self._screen_rect(selection)

            if self.show_preview and self.watermark_preview is not None:
                pw = self.watermark_preview.get_width()
                ph = self.watermark_preview.get_height()
                if pw > 0 and ph > 0:
                    cr.save()
                    cr.rectangle(sx, sy, sw, sh)
                    cr.clip()
                    cr.translate(sx, sy)
                    cr.scale(sw / pw, sh / ph)
                    Gdk.cairo_set_source_pixbuf(
                        cr,
                        self.watermark_preview,
                        0,
                        0,
                    )
                    cr.paint()
                    cr.restore()

            cr.set_source_rgba(1.0, 0.31, 0.60, 1.0)
            cr.set_line_width(2.5)
            cr.rectangle(sx, sy, sw, sh)
            cr.stroke()

            for hx, hy in self._handle_points(sx, sy, sw, sh).values():
                cr.set_source_rgba(1.0, 1.0, 1.0, 1.0)
                cr.arc(hx, hy, 6.0, 0, 6.283185307179586)
                cr.fill_preserve()
                cr.set_source_rgba(1.0, 0.31, 0.60, 1.0)
                cr.set_line_width(2.0)
                cr.stroke()

        if (
            self.drag_kind == "new"
            and self.drag_start
            and self.drag_current
        ):
            x1, y1 = self.drag_start
            x2, y2 = self.drag_current
            left = min(x1, x2)
            top = min(y1, y2)
            rw = abs(x2 - x1)
            rh = abs(y2 - y1)

            cr.set_source_rgba(1.0, 0.31, 0.60, 0.18)
            cr.rectangle(left, top, rw, rh)
            cr.fill_preserve()
            cr.set_source_rgba(1.0, 0.31, 0.60, 1.0)
            cr.set_line_width(2)
            cr.stroke()

    def _drag_begin(self, gesture, x, y):
        if self.frame_pixbuf is None or not self._inside_image(x, y):
            self.drag_kind = None
            self.drag_start = None
            self.drag_current = None
            self.move_start = None
            self.move_index = None
            self.resize_handle = None
            return

        for index in range(len(self.selections) - 1, -1, -1):
            sx, sy, sw, sh = self._screen_rect(self.selections[index])
            for handle, (hx, hy) in self._handle_points(
                sx,
                sy,
                sw,
                sh,
            ).items():
                if (x - hx) ** 2 + (y - hy) ** 2 <= 12 ** 2:
                    self.drag_kind = "resize"
                    self.resize_handle = handle
                    self.drag_start = (x, y)
                    self.drag_current = (x, y)
                    self.move_start = self.selections[index]
                    self.move_index = index
                    return

            if sx <= x <= sx + sw and sy <= y <= sy + sh:
                self.drag_kind = "move"
                self.resize_handle = None
                self.drag_start = (x, y)
                self.drag_current = (x, y)
                self.move_start = self.selections[index]
                self.move_index = index
                return

        self.drag_kind = "new"
        self.resize_handle = None
        self.drag_start = (x, y)
        self.drag_current = (x, y)
        self.move_start = None
        self.move_index = None
        self.queue_draw()

    def _drag_update(self, gesture, dx, dy):
        if self.drag_start is None:
            return

        if (
            self.drag_kind == "resize"
            and self.resize_handle is not None
            and self.move_start is not None
            and self.move_index is not None
        ):
            move_x = int(dx / self.display_scale)
            move_y = int(dy / self.display_scale)

            selection = self.move_start
            left = selection.x
            top = selection.y
            right = selection.x + selection.width
            bottom = selection.y + selection.height
            handle = self.resize_handle

            if "w" in handle:
                left += move_x
            if "e" in handle:
                right += move_x
            if "n" in handle:
                top += move_y
            if "s" in handle:
                bottom += move_y

            min_size = 2
            left = max(0, min(left, right - min_size))
            top = max(0, min(top, bottom - min_size))
            right = min(
                self.frame_width,
                max(right, left + min_size),
            )
            bottom = min(
                self.frame_height,
                max(bottom, top + min_size),
            )

            resized = Selection(
                int(left),
                int(top),
                int(right - left),
                int(bottom - top),
            )
            self.selections[self.move_index] = resized
            self.queue_draw()
            return

        if (
            self.drag_kind == "move"
            and self.move_start is not None
            and self.move_index is not None
        ):
            move_x = int(dx / self.display_scale)
            move_y = int(dy / self.display_scale)

            selection = self.move_start
            nx = max(
                0,
                min(
                    selection.x + move_x,
                    self.frame_width - selection.width,
                ),
            )
            ny = max(
                0,
                min(
                    selection.y + move_y,
                    self.frame_height - selection.height,
                ),
            )

            moved = Selection(
                nx,
                ny,
                selection.width,
                selection.height,
            )
            self.selections[self.move_index] = moved
            self.queue_draw()
            return

        x = self.drag_start[0] + dx
        y = self.drag_start[1] + dy
        x = min(max(x, self.offset_x), self.offset_x + self.draw_w)
        y = min(max(y, self.offset_y), self.offset_y + self.draw_h)
        self.drag_current = (x, y)
        self.queue_draw()

    def _drag_end(self, gesture, dx, dy):
        if self.drag_start is None:
            return

        if (
            self.drag_kind in {"move", "resize"}
            and self.move_index is not None
        ):
            self.drag_kind = None
            self.resize_handle = None
            self.drag_start = None
            self.drag_current = None
            self.move_start = None
            self.move_index = None
            self.on_selection_changed(list(self.selections))
            self.queue_draw()
            return

        x2 = self.drag_start[0] + dx
        y2 = self.drag_start[1] + dy

        x2 = min(max(x2, self.offset_x), self.offset_x + self.draw_w)
        y2 = min(max(y2, self.offset_y), self.offset_y + self.draw_h)

        x1, y1 = self.drag_start
        left = min(x1, x2)
        top = min(y1, y2)
        right = max(x1, x2)
        bottom = max(y1, y2)

        self.drag_kind = None
        self.drag_start = None
        self.drag_current = None

        if right - left < 8 or bottom - top < 8:
            self.queue_draw()
            return

        ix = int((left - self.offset_x) / self.display_scale)
        iy = int((top - self.offset_y) / self.display_scale)
        iw = int((right - left) / self.display_scale)
        ih = int((bottom - top) / self.display_scale)

        ix = max(0, min(ix, self.frame_width - 2))
        iy = max(0, min(iy, self.frame_height - 2))
        iw = max(2, min(iw, self.frame_width - ix))
        ih = max(2, min(ih, self.frame_height - iy))

        self.selections.append(Selection(ix, iy, iw, ih))
        self.on_selection_changed(list(self.selections))
        self.queue_draw()
