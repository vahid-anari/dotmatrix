"""Clock: how the time looks, and the date, the weather and the room that pass by
now and then. (Dimming at night moved to Settings → Brightness in 0.9.0.)"""
import time

import flet as ft

from core import preview, weather

from .widgets import LabeledSlider, bottom_room, led, muted, section

EVERY = [(0, "Never"), (10, "Every 10 seconds"), (20, "Every 20 seconds"), (30, "Every 30 seconds"),
         (60, "Every minute"), (300, "Every 5 minutes")]
DATE_FORMATS = ["%a %b %d", "%a %d %b", "%d/%m/%Y", "%m/%d/%Y", "%Y-%m-%d", "%A", "%B %d"]


class ClockTab:
    def __init__(self, app, open_settings=None):
        self.app = app
        self.open_settings = open_settings
        self._touched = 0.0

        self.led = led(preview.render_text(""), radius=12)
        self.show_btn = ft.FilledButton("Show the clock now", icon=ft.Icons.SCHEDULE, on_click=self._show_clock)
        self.h24 = ft.Switch(label="24-hour time", on_change=lambda e: self._clock(format_24h=e.control.value))
        self.secs = ft.Switch(label="Show seconds", on_change=lambda e: self._clock(seconds=e.control.value))
        # Date and weather: shown one after the other, every so often.
        self.show_date = ft.Checkbox(label="The date", on_change=lambda e: self._extras(show_date=e.control.value))
        self.show_weather = ft.Checkbox(label="The weather outside",
                                        on_change=lambda e: self._extras(show_weather=e.control.value))
        self.show_indoor = ft.Checkbox(label="The temperature and humidity in the room",
                                       on_change=lambda e: self._clock(show_indoor=e.control.value))
        self.every = ft.Dropdown(label="How often", expand=True,
                                 options=[ft.DropdownOption(key=str(k), text=t) for k, t in EVERY],
                                 on_select=lambda e: self._extras(every=int(e.control.value)))
        self.style = ft.SegmentedButton(
            segments=[ft.Segment(value="drop", label="Drop in from the top", icon=ft.Icons.SOUTH),
                      ft.Segment(value="scroll", label="Scroll across", icon=ft.Icons.WEST)],
            selected=["drop"], show_selected_icon=False, on_change=self._style_changed)
        self.pause = LabeledSlider("Each stays for", 3, 1, 10, 0.5, lambda v: f"{v:g} s",
                                   lambda v: None, on_release=self._pause_released)
        self.style_old = muted("Dropping in from the top needs newer firmware on the display "
                               "(Settings → Updates).", 14)
        today = time.localtime()
        self.fmt = ft.Dropdown(label="Date style", expand=True,
                               options=[ft.DropdownOption(key=f, text=time.strftime(f, today)) for f in DATE_FORMATS],
                               on_select=lambda e: self._clock(date_format=e.control.value))
        self.w_place = ft.Text("", size=15)
        self.w_now = muted("", 14)
        self.w_choose = ft.TextButton("Change the location", icon=ft.Icons.PLACE,
                                      on_click=lambda e: self.open_settings and self.open_settings())
        self.w_units = ft.SegmentedButton(
            segments=[ft.Segment(value="c", label="°C"), ft.Segment(value="f", label="°F")],
            selected=["c"], show_selected_icon=False,
            on_change=lambda e: self._weather(units=next(iter(e.control.selected), "c")))
        self.w_old = muted("Update the display's firmware (Settings → Updates) to show the weather.", 14)
        self.w_rows = ft.Column([self.w_place, self.w_now, ft.Row([self.w_units]), self.w_choose],
                                spacing=10)
        self.view = ft.Column([
            self.led,
            self.show_btn,
            section("Time", self.h24, self.secs),
            section("Date and weather", self.show_date, self.show_weather, self.show_indoor, ft.Row([self.every]),
                    ft.Row([self.style], scroll=ft.ScrollMode.AUTO), self.style_old, self.pause,
                    ft.Row([self.fmt]), self.w_old, self.w_rows,
                    note="Now and then the time makes way for them, one after the other: first the "
                         "date, then the weather, then the room. The weather comes from Open-Meteo "
                         "every 15 minutes."),
            bottom_room(),
        ], spacing=18, scroll=ft.ScrollMode.AUTO, expand=True)
        self.refresh()

    def refresh(self):
        d = self.app.device
        on = d.connected
        for c in (self.show_btn, self.h24, self.secs, self.every, self.fmt, self.show_date,
                  self.show_weather, self.show_indoor, self.style, self.pause.slider, self.w_choose, self.w_units):
            c.disabled = not on
        # Firmware from before 0.4 has no weather (its settings don't mention it).
        has_weather = not d.settings or "weather" in d.settings
        self.w_old.visible, self.w_rows.visible = not has_weather, has_weather
        w = d.settings.get("weather", {})
        self.w_place.value = f"For {w['place']}" if w.get("place") else "Choose the display's location first."
        now = weather.describe(d.state.get("weather"))
        self.w_now.value = f"Now: {now}" if now else ("Waiting for the first reading…" if w.get("place") else "")
        self.w_now.visible = bool(self.w_now.value)
        # Firmware from before 0.5 has two separate intervals and only scrolls across.
        new_fw = not d.settings or "extras_every" in d.settings.get("clock", {})
        self.style.visible = new_fw
        self.style_old.visible = not new_fw
        self.show_weather.visible = has_weather
        # The room's temperature needs firmware 0.6 and a temperature sensor fitted.
        self.show_indoor.visible = "show_indoor" in d.settings.get("clock", {}) and \
            "temp" in d.state.get("sensors", {})
        if time.monotonic() - self._touched < 2:
            return  # don't fight the user's finger
        c = d.settings.get("clock", {})
        self.h24.value = c.get("format_24h", True)
        self.secs.value = c.get("seconds", True)
        x = extras_from(c)
        self.show_date.value, self.show_weather.value = x["show_date"], x["show_weather"]
        self.show_indoor.value = c.get("show_indoor", True)
        self.every.value = str(x["every"])
        if self.every.value not in {str(k) for k, _ in EVERY}:
            self.every.options.append(ft.DropdownOption(key=self.every.value,
                                                        text=f"Every {self.every.value} seconds"))
        self.style.selected = [c.get("extras_style", "drop")]
        self.pause.set(c.get("extras_pause", 3000) / 1000)
        self.pause.visible = new_fw and c.get("extras_style", "drop") == "drop"
        self.fmt.value = c.get("date_format", DATE_FORMATS[0])
        self.w_units.selected = [w.get("units", "c")]
        self.tick()

    def tick(self):
        c = self.app.device.settings.get("clock", {})
        t = self.app.device.local_time()
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

    def _extras(self, **changes):
        """Send which extras to show and how often, in both forms: the 0.5 keys,
        and the two intervals older firmware reads."""
        x = {**extras_from(self.app.device.settings.get("clock", {})), **changes}
        self._clock(**extras_settings(x))

    def _style_changed(self, e):
        style = next(iter(e.control.selected), "drop")
        self.pause.visible = style == "drop"
        self.pause.update()
        self._clock(extras_style=style)

    def _pause_released(self, e):
        self._clock(extras_pause=int(round(self.pause.slider.value * 1000)))

    def _weather(self, **changes):
        self._touched = time.monotonic()
        self.app.run(self.app.device.update_settings, weather=changes)

    def _show_clock(self, e):
        self.app.run(self.app.device.request, "set_mode", mode="clock", ok="Showing the clock")


def extras_from(clock: dict) -> dict:
    """Which extras the display shows and how often, from its clock settings.
    Firmware from before 0.5 has two intervals instead: either one non-zero
    counts as shown, and the shared interval is the non-zero one."""
    if "extras_every" in clock:
        return {"every": clock["extras_every"], "show_date": clock.get("show_date", True),
                "show_weather": clock.get("show_weather", True)}
    d, w = clock.get("date_every", 0), clock.get("weather_every", 0)
    return {"every": d or w, "show_date": bool(d) or not w, "show_weather": bool(w) or not d}


def extras_settings(x: dict) -> dict:
    """The clock settings to send for these extras (both forms, see extras_from)."""
    every = x["every"]
    return {"extras_every": every, "show_date": x["show_date"], "show_weather": x["show_weather"],
            "date_every": every if x["show_date"] else 0, "weather_every": every if x["show_weather"] else 0}
