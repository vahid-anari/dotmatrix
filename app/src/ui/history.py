"""History: charts of the room's sensors and the display's brightness, over a day,
a week, a month or everything the phone has kept."""
import asyncio
import time

import flet as ft
import flet.canvas as cv

from core import history
from core.library import _storage_dir

from .widgets import muted

RANGES = (("day", "Day", 86400), ("week", "Week", 7 * 86400), ("month", "Month", 30 * 86400), ("all", "All", 0))
BLUE, ORANGE, GREEN, PURPLE, GOLD, GREY = "#3b82f6", "#f59e0b", "#22a06b", "#a855f7", "#d4a000", "#6b7280"


class Chart(ft.Column):
    """One chart: a title, the value under the finger, the lines, and time labels.
    `series` is a list of (points, colour); `fmt` turns a value into text; `ymap`
    maps a value onto the drawn scale (light uses a log scale)."""
    HEIGHT = 120

    def __init__(self, title: str, unit_fmt, ymap=lambda v: v, min_span: float = 1.0):
        readout = muted("", 13)
        canvas = cv.Canvas([], height=self.HEIGHT, expand=True, resize_interval=100)
        touch = ft.GestureDetector(content=canvas, drag_interval=30)
        super().__init__([ft.Row([ft.Text(title, size=15, weight=ft.FontWeight.W_600), readout],
                                 alignment=ft.MainAxisAlignment.SPACE_BETWEEN), touch], spacing=4)
        # (attributes after the control is set up: a flet control can't take them before)
        self.fmt, self.ymap, self.min_span = unit_fmt, ymap, min_span
        self.series: list[tuple[list, str, str]] = []  # (points, colour, name)
        self.span = (0.0, 1.0)
        self.cw = 0.0  # the canvas's width, once known
        self.cursor_x = None
        self.readout, self.canvas = readout, canvas
        canvas.on_resize = self._resized
        touch.on_tap_down = touch.on_pan_start = touch.on_pan_update = self._touch
        touch.on_pan_end = self._release

    def set(self, series, start: float, end: float):
        self.series = series
        self.span = (start, end)
        self.cursor_x = None
        self.readout.value = self._latest()
        self.draw()

    def _latest(self) -> str:
        for pts, _, name in self.series:
            if pts:
                return f"now {self.fmt(pts[-1][1])}" if len(self.series) == 1 else ""
        return "no readings"

    def _resized(self, e):
        self.cw = e.width
        self.draw()
        self.canvas.update()

    def _x(self, t):
        t0, t1 = self.span
        return (t - t0) / ((t1 - t0) or 1) * self.cw

    def draw(self):
        w, h, pad = self.cw, self.HEIGHT, 14
        shapes = []
        if w <= 0:
            self.canvas.shapes = shapes
            return
        vals = [self.ymap(v) for pts, _, _ in self.series for _, v in pts]
        lo, hi = history.nice_range(vals, min_span=self.min_span)
        y = lambda v: pad + (h - 2 * pad - 14) * (1 - (self.ymap(v) - lo) / ((hi - lo) or 1))
        grid = ft.Paint(color=ft.Colors.with_opacity(0.15, ft.Colors.ON_SURFACE), stroke_width=1)
        for t, label in history.ticks(*self.span):
            x = self._x(t)
            shapes.append(cv.Line(x, pad, x, h - 14, paint=grid))
            if x > w - 34:  # no room for it at the right edge
                continue
            shapes.append(cv.Text(x + 3, h - 13, label, style=ft.TextStyle(size=10, color=ft.Colors.ON_SURFACE_VARIANT)))
        # the top and bottom values of the scale, at the left
        for v_drawn, yy in ((hi, pad), (lo, h - pad - 14)):
            shapes.append(cv.Text(2, yy - 6, self._label(v_drawn), style=ft.TextStyle(size=10, color=ft.Colors.ON_SURFACE_VARIANT)))
        for pts, colour, _ in self.series:
            path, last_t = [], None
            gap = (self.span[1] - self.span[0]) / 60  # a longer gap than this breaks the line
            for t, v in pts:
                x, yy = self._x(t), y(v)
                if last_t is None or t - last_t > gap:
                    path.append(cv.Path.MoveTo(x, yy))
                else:
                    path.append(cv.Path.LineTo(x, yy))
                last_t = t
            shapes.append(cv.Path(path, paint=ft.Paint(color=colour, stroke_width=2, style=ft.PaintingStyle.STROKE,
                                                       stroke_join=ft.StrokeJoin.ROUND)))
        if self.cursor_x is not None:
            shapes.append(cv.Line(self.cursor_x, pad, self.cursor_x, h - 14,
                                  paint=ft.Paint(color=ft.Colors.ON_SURFACE, stroke_width=1)))
        self.canvas.shapes = shapes

    def _label(self, drawn: float) -> str:
        # Turn a drawn value back into the real one for light's log scale.
        if self.ymap is history.light_y:
            return f"{max(0.0, 10 ** drawn - 1):.0f}"
        v = f"{drawn:.0f}" if abs(drawn) >= 10 else f"{drawn:.1f}"
        return "0" if v in ("-0", "-0.0") else v

    def _touch(self, e):
        if self.cw <= 0 or not self.series:
            return
        x = max(0.0, min(self.cw, e.local_position.x))
        t0, t1 = self.span
        t = t0 + x / self.cw * (t1 - t0)
        parts = []
        for pts, colour, name in self.series:
            if pts:
                pt = min(pts, key=lambda p: abs(p[0] - t))
                parts.append((name + " " if name else "") + self.fmt(pt[1]))
        when = time.strftime("%a %H:%M", time.localtime(t))
        self.readout.value = f"{when} · " + ", ".join(parts)
        self.cursor_x = x
        self.draw()
        self.update()

    def _release(self, e):
        self.cursor_x = None
        self.readout.value = self._latest()
        self.draw()
        self.update()


class HistoryScreen:
    def __init__(self, app):
        self.app = app
        self.archive = history.Archive(_storage_dir() / "history.csv")
        self.minutes: list[dict] = []
        self.range = "day"
        self.status = muted("")
        self.picker = ft.SegmentedButton(
            selected=["day"], show_selected_icon=False, on_change=self._range_changed,
            segments=[ft.Segment(value=k, label=ft.Text(t)) for k, t, _ in RANGES])
        units = app.device.settings.get("weather", {}).get("units", "c")
        self.f = units == "f"
        deg = (lambda v: f"{v:.1f} °F") if self.f else (lambda v: f"{v:.1f} °C")
        self.temp = Chart("Temperature", deg)
        self.temp_key = ft.Row([self._key(BLUE, "room"), self._key(ORANGE, "outside")], spacing=14)
        self.hum = Chart("Humidity", lambda v: f"{v:.0f} %")
        self.pres = Chart("Air pressure", lambda v: f"{v:.0f} hPa", min_span=4)
        self.light = Chart("Light", lambda v: f"{v:.1f} lx" if v < 10 else f"{v:.0f} lx", ymap=history.light_y)
        self.bright = Chart("Display brightness", lambda v: f"{v:.1f} of 15" if v % 1 else f"{v:.0f} of 15")
        self.view = ft.View(
            route="/history",
            appbar=ft.AppBar(title=ft.Text("History"), actions=[
                ft.IconButton(ft.Icons.REFRESH, tooltip="Fetch again", on_click=lambda e: self.app.page.run_task(self.load))]),
            controls=[ft.Column([
                self.picker, self.status,
                ft.Column([self.temp, self.temp_key], spacing=2), self.hum, self.pres, self.light, self.bright,
                muted("Touch a chart to read it. The display keeps 30 days; the phone keeps every "
                      "day it has fetched, from the first time you opened this page.", 12),
                ft.Container(height=40),
            ], spacing=18, scroll=ft.ScrollMode.AUTO, expand=True)],
            padding=16)

    @staticmethod
    def _key(colour, text):
        return ft.Row([ft.Container(width=14, height=3, bgcolor=colour), muted(text, 12)], spacing=6)

    def refresh(self):
        """The app calls this when the display's state changes; the charts don't follow it."""

    def show(self):
        self.app.push(self.view, self)
        self.redraw()
        self.app.page.run_task(self.load)

    async def load(self):
        """Fetch the quarters the phone doesn't have yet, and the last day's minutes."""
        host = self.app.device.host
        self.status.value = "Fetching from the display…"
        self.status.update()
        try:
            quarters, minutes = await asyncio.gather(
                history.fetch(host, 15, self.archive.last), history.fetch(host, 1, int(time.time()) - 86400))
        except Exception:  # noqa: BLE001 — offline, or an older display
            self.status.value = "Couldn't fetch from the display; showing what the phone has kept."
            self.status.update()
            self.redraw()
            return
        new = self.archive.merge(quarters)
        if new:
            await asyncio.to_thread(self.archive.save)
        self.minutes = minutes
        self.status.value = ""
        self.status.visible = False
        self.redraw()

    def _range_changed(self, e):
        self.range = e.control.selected[0] if e.control.selected else "day"
        self.redraw()

    def redraw(self):
        now = time.time()
        span = dict((k, s) for k, _, s in RANGES)[self.range]
        if self.range == "day":
            rows = self.minutes or history.window(self.archive.rows, now - span, now)
            start = now - span
        else:
            start = now - span if span else (self.archive.rows[0]["t"] if self.archive.rows else now - 86400)
            rows = history.window(self.archive.rows, start, now)
        c2 = (lambda pts: [(t, v * 9 / 5 + 32) for t, v in pts]) if self.f else (lambda pts: pts)  # kept in °C
        self.temp.set([(c2(history.thin(rows, "temp_c")), BLUE, "room"),
                       (c2(history.thin(rows, "outdoor_c")), ORANGE, "out")], start, now)
        self.hum.set([(history.thin(rows, "humidity"), BLUE, "")], start, now)
        self.pres.set([(history.thin(rows, "pressure_hpa"), PURPLE, "")], start, now)
        self.light.set([(history.thin(rows, "lux"), GOLD, "")], start, now)
        self.bright.set([(history.thin(rows, "brightness"), GREEN, "")], start, now)
        try:
            self.view.update()
        except Exception:  # noqa: BLE001 — not on the page yet
            pass
