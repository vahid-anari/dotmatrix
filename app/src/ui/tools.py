"""Tools: a stopwatch and a countdown timer that run on the display itself,
so they keep going when the phone is put away."""
import time

import flet as ft

from core import preview

from .widgets import heading, led, muted, section

PRESETS = [1, 3, 5, 10, 15, 30, 60]  # minutes


def fmt_stopwatch(ms: int) -> str:
    """Same as formatStopwatch() in firmware/src/modes/TimeFormat.h."""
    s = ms // 1000
    if s < 3600:
        return f"{s // 60:02d}:{s % 60:02d}.{ms % 1000 // 10:02d}"
    return f"{s // 3600}:{s // 60 % 60:02d}:{s % 60:02d}"


def fmt_timer(ms: int) -> str:
    """Same as formatTimer(): whole seconds rounded up."""
    s = (ms + 999) // 1000
    if s < 3600:
        return f"{s // 60:02d}:{s % 60:02d}"
    return f"{s // 3600}:{s // 60 % 60:02d}:{s % 60:02d}"


class ToolsTab:
    def __init__(self, app):
        self.app = app
        self._done_since: float | None = None

        # Stopwatch
        self.sw_led = led(preview.render_text("00:00.00"), radius=12)
        self.sw_start = ft.FilledButton("Start", icon=ft.Icons.PLAY_ARROW, on_click=self._sw_toggle)
        self.sw_reset = ft.OutlinedButton("Reset", icon=ft.Icons.RESTART_ALT,
                                          on_click=lambda e: self._sw("reset"))
        self.sw_show = ft.TextButton("Show on the display", on_click=lambda e: self._sw("show"))

        # Timer
        self.t_led = led(preview.render_text("05:00"), radius=12)
        self.t_note = muted("")
        self.t_start = ft.FilledButton("Start", icon=ft.Icons.PLAY_ARROW, on_click=self._t_toggle)
        self.t_reset = ft.OutlinedButton("Reset", icon=ft.Icons.RESTART_ALT,
                                         on_click=lambda e: self._t("reset"))
        self.t_show = ft.TextButton("Show on the display", on_click=lambda e: self._t("show"))
        self.presets = ft.Row(wrap=True, spacing=8, run_spacing=8, controls=[
            ft.Chip(label=ft.Text(f"{m} min" if m < 60 else "1 hour"), on_click=lambda e, m=m: self._t_set(m * 60))
            for m in PRESETS] + [ft.Chip(label=ft.Text("Other…"), leading=ft.Icon(ft.Icons.EDIT, size=16),
                                         on_click=self._t_custom)])

        self.old_fw = muted("This display's firmware has no stopwatch or timer yet. "
                            "Update it under Settings.", 14)
        self.view = ft.Column([
            heading("Tools"),
            muted("Both run on the display, so they keep going when your phone is away."),
            self.old_fw,
            # "Show on the display" sits on its own line, so the buttons never move
            # when Start turns into Pause.
            section("Stopwatch", self.sw_led, ft.Row([self.sw_start, self.sw_reset]), self.sw_show),
            section("Timer", self.t_led, self.t_note, self.presets,
                    ft.Row([self.t_start, self.t_reset]), self.t_show,
                    note="When it reaches zero, the display switches to it and blinks."),
        ], spacing=20, scroll=ft.ScrollMode.AUTO, expand=True)
        self.refresh()

    # ------------------------------------------------------------- refresh
    def refresh(self):
        d = self.app.device
        on = d.connected and d.has_tools
        self.old_fw.visible = d.connected and not d.has_tools
        for c in (self.sw_start, self.sw_reset, self.sw_show, self.t_start, self.t_reset, self.t_show,
                  self.presets):
            c.disabled = not on
        mode = d.state.get("mode")
        sw = d.state.get("stopwatch", {})
        t = d.state.get("timer", {})

        running = sw.get("running", False)
        self.sw_start.content, self.sw_start.icon = ("Pause", ft.Icons.PAUSE) if running else \
            ("Start" if not sw.get("ms") else "Resume", ft.Icons.PLAY_ARROW)
        self.sw_show.opacity = 1 if on and mode != "stopwatch" else 0
        self.sw_show.disabled = not on or mode == "stopwatch"

        t_running = t.get("running", False)
        done = t.get("done", False)
        self.t_start.content, self.t_start.icon = ("Pause", ft.Icons.PAUSE) if t_running else \
            ("Start again" if done else ("Resume" if 0 < t.get("remaining_ms", 0) < t.get("total_ms", 0)
                                         else "Start"), ft.Icons.PLAY_ARROW)
        self.t_show.opacity = 1 if on and mode != "timer" else 0
        self.t_show.disabled = not on or mode == "timer"
        total = t.get("total_ms", 0)
        self.t_note.value = "Time's up." if done else (f"Set to {fmt_timer(total)}" if total else "")
        self.tick()

    def tick(self) -> bool:
        d = self.app.device
        self.sw_led.content.src = preview.render_text(fmt_stopwatch(d.stopwatch_ms()))
        t = d.state.get("timer", {})
        text = fmt_timer(d.timer_remaining_ms())
        if t.get("done"):
            if self._done_since is None:
                self._done_since = time.monotonic()
            # Blink along with the display, which blinks for one minute.
            if time.monotonic() - self._done_since < 60 and int(time.monotonic() * 2) % 2:
                text = ""
        else:
            self._done_since = None
        self.t_led.content.src = preview.render_text(text)
        return True

    # ------------------------------------------------------------- actions
    def _sw(self, action):
        self.app.run(self.app.device.request, "stopwatch", action=action)

    def _sw_toggle(self, e):
        self._sw("pause" if self.app.device.state.get("stopwatch", {}).get("running") else "start")

    def _t(self, action, **kw):
        self.app.run(self.app.device.request, "timer", action=action, **kw)

    def _t_toggle(self, e):
        self._t("pause" if self.app.device.state.get("timer", {}).get("running") else "start")

    def _t_set(self, seconds: int):
        self._t("set", seconds=seconds)

    def _t_custom(self, e):
        mins = ft.TextField(label="Minutes", value="0", keyboard_type=ft.KeyboardType.NUMBER, width=110,
                            autofocus=True)
        secs = ft.TextField(label="Seconds", value="0", keyboard_type=ft.KeyboardType.NUMBER, width=110)

        def ok(ev):
            try:
                total = int(mins.value or 0) * 60 + int(secs.value or 0)
            except ValueError:
                total = 0
            if not 0 < total <= 86400:
                secs.error = "1 second to 24 hours"
                secs.update()
                return
            self.app.page.pop_dialog()
            self._t_set(total)

        self.app.page.show_dialog(ft.AlertDialog(
            title=ft.Text("Timer length"), content=ft.Row([mins, secs], tight=True),
            actions=[ft.TextButton("Cancel", on_click=lambda ev: self.app.page.pop_dialog()),
                     ft.FilledButton("Set", on_click=ok)]))
