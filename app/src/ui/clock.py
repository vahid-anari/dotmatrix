"""Clock: how the time looks, the date and the weather that pass by now and then,
and dimming at night."""
import datetime as dt
import time

import flet as ft

from core import preview, weather

from .widgets import Debouncer, LabeledSlider, bottom_room, led, muted, section

EVERY = [(0, "Never"), (10, "Every 10 seconds"), (20, "Every 20 seconds"), (30, "Every 30 seconds"),
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
        # Date and weather: shown one after the other, every so often.
        self.show_date = ft.Checkbox(label="The date", on_change=lambda e: self._extras(show_date=e.control.value))
        self.show_weather = ft.Checkbox(label="The weather outside",
                                        on_change=lambda e: self._extras(show_weather=e.control.value))
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
        self.w_choose = ft.OutlinedButton("Choose the place", icon=ft.Icons.PLACE, on_click=self._choose_place)
        self.w_units = ft.SegmentedButton(
            segments=[ft.Segment(value="c", label="°C"), ft.Segment(value="f", label="°F")],
            selected=["c"], show_selected_icon=False,
            on_change=lambda e: self._weather(units=next(iter(e.control.selected), "c")))
        self.w_old = muted("Update the display's firmware (Settings → Updates) to show the weather.", 14)
        self.w_rows = ft.Column([self.w_place, self.w_now, ft.Row([self.w_choose, self.w_units], wrap=True)],
                                spacing=10)
        self.night = ft.Switch(label="Dim at night", on_change=lambda e: self._set_night(enabled=e.control.value))
        self.from_btn = ft.OutlinedButton("23:00", icon=ft.Icons.BEDTIME, on_click=lambda e: self._pick("from"))
        self.to_btn = ft.OutlinedButton("07:00", icon=ft.Icons.WB_SUNNY, on_click=lambda e: self._pick("to"))
        self.night_b = LabeledSlider("Brightness at night", 1, 0, 15, 1,
                                     lambda v: f"{int(v)} of 15" + (" (dimmest)" if v == 0 else ""),
                                     lambda v: self._send_brightness(int(v)))
        self.night_rows = ft.Column([
            ft.Row([ft.Column([muted("From", 14), self.from_btn], spacing=4),
                    ft.Column([muted("Until", 14), self.to_btn], spacing=4)], spacing=24),
            self.night_b,
        ], spacing=14)

        self.view = ft.Column([
            self.led,
            self.show_btn,
            section("Time", self.h24, self.secs),
            section("Date and weather", self.show_date, self.show_weather, ft.Row([self.every]),
                    ft.Row([self.style], scroll=ft.ScrollMode.AUTO), self.style_old, self.pause,
                    note="Now and then the time makes way for them, one after the other: "
                         "first the date, then the weather."),
            section("Date", ft.Row([self.fmt])),
            section("Weather", self.w_old, self.w_rows,
                    note="The display fetches it from Open-Meteo every 15 minutes."),
            section("Night", self.night, self.night_rows,
                    note="Lowers the brightness during these hours, in every mode."),
            bottom_room(),
        ], spacing=18, scroll=ft.ScrollMode.AUTO, expand=True)
        self.refresh()

    def refresh(self):
        d = self.app.device
        on = d.connected
        for c in (self.show_btn, self.h24, self.secs, self.every, self.fmt, self.night, self.show_date,
                  self.show_weather, self.style, self.pause.slider,
                  self.from_btn, self.to_btn, self.night_b.slider, self.w_choose, self.w_units):
            c.disabled = not on
        # Firmware from before 0.4 has no weather (its settings don't mention it).
        has_weather = not d.settings or "weather" in d.settings
        self.w_old.visible, self.w_rows.visible = not has_weather, has_weather
        w = d.settings.get("weather", {})
        self.w_place.value = w.get("place") or "No place chosen yet."
        now = weather.describe(d.state.get("weather"))
        self.w_now.value = f"Now: {now}" if now else ("Waiting for the first reading…" if w.get("place") else "")
        self.w_now.visible = bool(self.w_now.value)
        # Firmware from before 0.5 has two separate intervals and only scrolls across.
        new_fw = not d.settings or "extras_every" in d.settings.get("clock", {})
        self.style.visible = new_fw
        self.style_old.visible = not new_fw
        self.show_weather.visible = has_weather
        if time.monotonic() - self._touched < 2:
            return  # don't fight the user's finger
        c = d.settings.get("clock", {})
        n = d.settings.get("night", {})
        self.h24.value = c.get("format_24h", True)
        self.secs.value = c.get("seconds", True)
        x = extras_from(c)
        self.show_date.value, self.show_weather.value = x["show_date"], x["show_weather"]
        self.every.value = str(x["every"])
        if self.every.value not in {str(k) for k, _ in EVERY}:
            self.every.options.append(ft.DropdownOption(key=self.every.value,
                                                        text=f"Every {self.every.value} seconds"))
        self.style.selected = [c.get("extras_style", "drop")]
        self.pause.set(c.get("extras_pause", 3000) / 1000)
        self.pause.visible = new_fw and c.get("extras_style", "drop") == "drop"
        self.fmt.value = c.get("date_format", DATE_FORMATS[0])
        self.w_units.selected = [w.get("units", "c")]
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

    def _choose_place(self, e):
        """Search by name; tapping a result sends it to the display."""
        query = ft.TextField(label="Town or city", autofocus=True, expand=True,
                             value=(self.app.device.settings.get("weather", {}).get("place") or "").split(",")[0])
        results = ft.Column(spacing=0, scroll=ft.ScrollMode.AUTO, height=300)
        note = muted("")

        def pick(place):
            self.app.page.pop_dialog()
            self.w_place.value = place.label
            self.w_place.update()
            self._weather(place=place.label, lat=place.lat, lon=place.lon)
            # A new place counts as wanting to see it: switch it on if it was off.
            x = extras_from(self.app.device.settings.get("clock", {}))
            if not (x["show_weather"] and x["every"]):
                self._extras(show_weather=True, every=x["every"] or 30)

        async def find(ev=None):
            name = (query.value or "").strip()
            if len(name) < 2:
                return
            note.value = "Searching…"
            results.controls = []
            note.update()
            results.update()
            try:
                places = await weather.search(name)
            except Exception:  # noqa: BLE001 — offline
                note.value = "Couldn't search. Check the phone's internet connection."
                note.update()
                return
            note.value = "" if places else "Nothing found. Try another spelling."
            results.controls = [ft.ListTile(title=ft.Text(p.name), subtitle=ft.Text(p.full),
                                            on_click=lambda ev, p=p: pick(p)) for p in places]
            note.update()
            results.update()

        query.on_submit = find
        self.app.page.show_dialog(ft.AlertDialog(
            title=ft.Text("Weather for"),
            content=ft.Column([ft.Row([query, ft.IconButton(ft.Icons.SEARCH, on_click=find)]), note, results],
                              tight=True, width=360),
            actions=[ft.TextButton("Cancel", on_click=lambda ev: self.app.page.pop_dialog())]))

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
