"""Home: what the display shows now, its mode and brightness, a quick message."""
import time

import flet as ft

from core import preview
from core.items import new_text_item

from .widgets import LabeledSlider, heading, muted, section, status_dot

MODE_LABELS = {"text": "Texts", "clock": "Clock", "off": "Off"}


def signal_words(rssi: int) -> str:
    if rssi == 0:
        return "–"
    if rssi > -55:
        return "Strong"
    if rssi > -70:
        return "Good"
    return "Weak"


def uptime_words(seconds: int) -> str:
    d, rest = divmod(int(seconds), 86400)
    h, rest = divmod(rest, 3600)
    m = rest // 60
    if d:
        return f"{d} d {h} h"
    if h:
        return f"{h} h {m} min"
    return f"{m} min"


class ConnectionLine(ft.Row):
    """Dot + one line of connection status. Tapping it opens Settings."""

    def __init__(self, app, on_tap):
        self.app = app
        self.dot = status_dot("#9AA5AE")
        self.label = ft.Text(size=13, color=ft.Colors.ON_SURFACE_VARIANT)
        super().__init__([ft.Container(ft.Row([self.dot, self.label], spacing=8), on_click=on_tap,
                                       padding=ft.Padding.symmetric(vertical=4))], spacing=0)
        self.refresh()

    def refresh(self):
        d, p = self.app.device, self.app.palette()
        if d.connected:
            self.dot.bgcolor = p["primary"]
            self.label.value = f"Connected to {d.hello.get('name', 'display')}"
        elif self.app.scanning:
            self.dot.bgcolor = p["gold"]
            self.label.value = "Looking for the display on this Wi-Fi…"
        elif d.status == "connecting":
            self.dot.bgcolor = p["gold"]
            self.label.value = f"Connecting to {d.host}…"
        else:
            self.dot.bgcolor = "#9AA5AE"
            self.label.value = f"{d.error or 'Not connected'}. Tap to set up." if d.host else \
                "No display yet. Tap to set up."


class HomeTab:
    def __init__(self, app, open_settings):
        self.app = app
        self._brightness_touched = 0.0
        self._showing_message = False

        self.conn = ConnectionLine(app, lambda e: open_settings())
        self.now_image = ft.Image(src=preview.render_text(""), fit=ft.BoxFit.CONTAIN, gapless_playback=True)
        self.now_caption = muted("")
        self.modes = ft.SegmentedButton(
            segments=[ft.Segment(value=k, label=v, icon=ft.Icon(i)) for (k, v), i in
                      zip(MODE_LABELS.items(), (ft.Icons.TEXT_FIELDS, ft.Icons.SCHEDULE, ft.Icons.POWER_SETTINGS_NEW))],
            selected=["text"], on_change=self._mode_changed, show_selected_icon=False,
        )
        self.brightness = LabeledSlider("Level", 6, 0, 15, 1, lambda v: f"{int(v)} of 15",
                                        self._brightness_changed, self._brightness_released)
        self.night_note = muted("")
        self.message = ft.TextField(hint_text="Type a message", expand=True, dense=True,
                                    max_length=128, counter="", on_submit=self._show_message)
        self.message_btn = ft.FilledButton("Show", icon=ft.Icons.PLAY_ARROW, on_click=self._show_message)
        self.facts = ft.Column(spacing=6)

        self.view = ft.Column([
            ft.Column([heading("Dot Matrix"), self.conn], spacing=2),
            ft.Container(self.now_image, bgcolor="#120A09", padding=10, border_radius=12),
            self.now_caption,
            ft.Container(height=4),
            section("Show", self.modes),
            section("Brightness", self.brightness, self.night_note),
            section("Quick message", ft.Row([self.message, self.message_btn],
                                            vertical_alignment=ft.CrossAxisAlignment.START),
                    note="Scrolls across the display until you stop it."),
            section("This display", self.facts),
        ], spacing=18, scroll=ft.ScrollMode.AUTO, expand=True)
        self.refresh()

    # --------------------------------------------------------------- refresh
    def refresh(self):
        app, d = self.app, self.app.device
        st = d.state
        self.conn.refresh()
        on = d.connected
        for c in (self.modes, self.brightness.slider, self.message, self.message_btn):
            c.disabled = not on

        mode = st.get("mode", "text")
        self.modes.selected = [mode]
        self.now_image.src, self.now_caption.value = self._now(mode, st)

        if time.monotonic() - self._brightness_touched > 2:
            self.brightness.set(d.settings.get("brightness", st.get("brightness", 6)))
        night = on and bool(st.get("night"))
        self.night_note.value = "Dimmed for the night right now." if night else ""
        self.night_note.visible = night

        self.message_btn.content = "Stop" if self._showing_message and st.get("previewing") else "Show"
        self.message_btn.icon = ft.Icons.STOP if self.message_btn.content == "Stop" else ft.Icons.PLAY_ARROW
        if not st.get("previewing"):
            self._showing_message = False

        rows = []
        if on:
            rows = [("Address", d.host), ("Wi-Fi signal", signal_words(st.get("rssi", 0))),
                    ("Running for", uptime_words(st.get("uptime", 0))),
                    ("Firmware", d.hello.get("fw", "–"))]
        else:
            rows = [("Address", d.host or "–")]
        self.facts.controls = [
            ft.Row([muted(k, 14), ft.Text(v, size=14)], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)
            for k, v in rows]

    def _now(self, mode: str, st: dict):
        d = self.app.device
        if not d.connected:
            return preview.render_text(""), "The display isn't connected."
        if st.get("previewing"):
            return preview.render_text(self.message.value or "…"), "Showing a preview."
        if mode == "off":
            return preview.render_text(""), "The display is switched off."
        if mode == "clock":
            return preview.render_text(self.clock_text()), "Showing the clock."
        group = self.app.active_group()
        name = st.get("playlist") or ""
        idx, n = st.get("index", -1), st.get("items", 0)
        if group and 0 <= idx < len(group["items"]):
            return preview.render_item(group["items"][idx]), f"Playing “{name}”, item {idx + 1} of {n}."
        if n:
            return preview.render_text(name[:10]), f"Playing “{name}”, item {idx + 1} of {n}."
        return preview.render_text("Hello!"), "Nothing to play yet. Pick a group under Texts."

    def clock_text(self) -> str:
        c = self.app.device.settings.get("clock", {})
        t = time.localtime()
        h = t.tm_hour if c.get("format_24h", True) else (t.tm_hour % 12 or 12)
        hh = f"{h:02d}" if c.get("format_24h", True) else str(h)
        return f"{hh}:{t.tm_min:02d}:{t.tm_sec:02d}" if c.get("seconds", True) else f"{hh}:{t.tm_min:02d}"

    def tick(self):
        """Called every second so the clock preview runs like the real one."""
        if self.app.device.state.get("mode") == "clock" and self.app.device.connected \
                and not self.app.device.state.get("previewing"):
            self.now_image.src = preview.render_text(self.clock_text())
            return True
        return False

    # --------------------------------------------------------------- actions
    def _mode_changed(self, e):
        mode = next(iter(e.control.selected), "text")
        d = self.app.device
        if mode == "text" and not d.state.get("items"):
            group = self.app.library.groups[0] if self.app.library.groups else None
            if group:
                self.app.run(d.play_group, group["name"], group["items"], ok=f"Playing “{group['name']}”")
                return
        self.app.run(d.request, "set_mode", mode=mode)

    def _brightness_changed(self, v):
        self._brightness_touched = time.monotonic()
        self.app.device.send("set_settings", settings={"brightness": int(v)})

    def _brightness_released(self, e):
        self._brightness_touched = time.monotonic()

    def _show_message(self, e):
        d = self.app.device
        if self._showing_message:
            self._showing_message = False
            self.app.run(d.request, "preview_end")
            return
        text = (self.message.value or "").strip()
        if not text:
            return
        item = {**new_text_item(text), "pause": 0, "speed_in": 35, "speed_out": 35}
        self._showing_message = True
        self.app.run(d.request, "preview", item=item)
