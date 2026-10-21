"""Clock: how the time looks, the date, and dimming at night."""
import datetime as dt
import time

import flet as ft

from core import preview

from .widgets import Debouncer, LabeledSlider, heading, led, muted, section

DATE_EVERY = [(0, "Never"), (10, "Every 10 seconds"), (20, "Every 20 seconds"), (30, "Every 30 seconds"),
              (60, "Every minute"), (300, "Every 5 minutes")]
DATE_FORMATS = ["%a %b %d", "%a %d %b", "%d/%m/%Y", "%m/%d/%Y", "%Y-%m-%d", "%A", "%B %d"]


class ClockTab:
    def __init__(self, app):
        self.app = app
        self._touched = 0.0
        self._send_brightness = Debouncer(app.page, 0.3, self._night_brightness)

        self.led = led(preview.render_text(""), radius=12)
        self.show_btn = ft.FilledButton("Show the clock now", icon=ft.Icons.SCHEDULE, on_click=self._show_clock)
        self.h24 = ft.Switch(label="24-hour time", on_change=lambda e: self._clock(format_24h=e.control.value))
        self.secs = ft.Switch(label="Show seconds", on_change=lambda e: self._clock(seconds=e.control.value))
        self.every = ft.Dropdown(label="Show the date", expand=True,
                                 options=[ft.DropdownOption(key=str(k), text=t) for k, t in DATE_EVERY],
                                 on_select=lambda e: self._clock(date_every=int(e.control.value)))
        today = time.localtime()
        self.fmt = ft.Dropdown(label="Date style", expand=True,
                               options=[ft.DropdownOption(key=f, text=time.strftime(f, today)) for f in DATE_FORMATS],
                               on_select=lambda e: self._clock(date_format=e.control.value))
        self.night = ft.Switch(label="Dim at night", on_change=lambda e: self._set_night(enabled=e.control.value))
        self.from_btn = ft.OutlinedButton("23:00", icon=ft.Icons.BEDTIME, on_click=lambda e: self._pick("from"))
        self.to_btn = ft.OutlinedButton("07:00", icon=ft.Icons.WB_SUNNY, on_click=lambda e: self._pick("to"))
        self.night_b = LabeledSlider("Brightness at night", 1, 0, 15, 1,
                                     lambda v: "Off" if v == 0 else f"{int(v)} of 15",
                                     lambda v: self._send_brightness(int(v)))
        self.night_rows = ft.Column([
            ft.Row([ft.Column([muted("From", 14), self.from_btn], spacing=4),
                    ft.Column([muted("Until", 14), self.to_btn], spacing=4)], spacing=24),
            self.night_b,
        ], spacing=14)

        self.view = ft.Column([
            heading("Clock"),
            self.led,
            self.show_btn,
            section("Time", self.h24, self.secs),
            section("Date", ft.Row([self.every]), ft.Row([self.fmt]),
                    note="The date scrolls past once, then the time comes back."),
            section("Night", self.night, self.night_rows,
                    note="Lowers the brightness during these hours, in every mode."),
        ], spacing=18, scroll=ft.ScrollMode.AUTO, expand=True)
        self.refresh()

    def refresh(self):
        d = self.app.device
        on = d.connected
        for c in (self.show_btn, self.h24, self.secs, self.every, self.fmt, self.night,
                  self.from_btn, self.to_btn, self.night_b.slider):
            c.disabled = not on
        if time.monotonic() - self._touched < 2:
            return  # don't fight the user's finger
        c = d.settings.get("clock", {})
        n = d.settings.get("night", {})
        self.h24.value = c.get("format_24h", True)
        self.secs.value = c.get("seconds", True)
        self.every.value = str(c.get("date_every", 0))
        if self.every.value not in {str(k) for k, _ in DATE_EVERY}:
            self.every.options.append(ft.DropdownOption(key=self.every.value,
                                                        text=f"Every {self.every.value} seconds"))
        self.fmt.value = c.get("date_format", DATE_FORMATS[0])
        self.night.value = n.get("enabled", False)
        self.from_btn.content = n.get("from", "23:00")
        self.to_btn.content = n.get("to", "07:00")
        self.night_b.set(n.get("brightness", 1))
        self.night_rows.visible = bool(self.night.value)
        self.tick()

    def tick(self):
        c = self.app.device.settings.get("clock", {})
        t = time.localtime()
        h24 = c.get("format_24h", True)
        h = t.tm_hour if h24 else (t.tm_hour % 12 or 12)
        hh = f"{h:02d}" if h24 else str(h)
        text = f"{hh}:{t.tm_min:02d}:{t.tm_sec:02d}" if c.get("seconds", True) else \
            f"{hh}{':' if t.tm_sec % 2 == 0 else ' '}{t.tm_min:02d}"
        self.led.content.src = preview.render_text(text)
        return True

    # --------------------------------------------------------------- actions
    def _clock(self, **changes):
        self._touched = time.monotonic()
        self.app.run(self.app.device.update_settings, clock=changes)

    def _set_night(self, **changes):
        self._touched = time.monotonic()
        if "enabled" in changes:
            self.night_rows.visible = changes["enabled"]
            self.night_rows.update()
        self.app.run(self.app.device.update_settings, night=changes)

    async def _night_brightness(self, v):
        self._touched = time.monotonic()
        await self.app.device.update_settings(night={"brightness": v})

    def _show_clock(self, e):
        self.app.run(self.app.device.request, "set_mode", mode="clock", ok="Showing the clock")

    def _pick(self, which: str):
        btn = self.from_btn if which == "from" else self.to_btn
        h, m = (int(x) for x in str(btn.content).split(":"))

        def chosen(e):
            v = e.control.value
            if v:
                text = f"{v.hour:02d}:{v.minute:02d}"
                btn.content = text
                btn.update()
                self._set_night(**{which: text})

        self.app.page.show_dialog(ft.TimePicker(value=dt.time(h, m), on_change=chosen,
                                                help_text="Dim from" if which == "from" else "Dim until"))
