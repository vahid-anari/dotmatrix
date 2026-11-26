"""Settings → Brightness: how automatic brightness follows the light, and dimming
at night. (Home keeps the everyday part: Automatic on or off, and the level.)"""
import datetime as dt
import time

import flet as ft

from .home import lux_range_error, lux_text
from .widgets import Debouncer, LabeledSlider, muted, section


class BrightnessPage:
    def __init__(self, app):
        self.app = app
        self._touched = 0.0
        self._send_night = Debouncer(app.page, 0.3, self._night_brightness)

        # Automatic brightness (firmware 0.8, with a light sensor).
        self.auto = ft.Switch(label="Automatic, from the room's light", on_change=self._auto_switched)
        self.auto_dark = LabeledSlider("In the dark", 0, 0, 15, 1, lambda v: f"{int(v)} of 15",
                                       lambda v: self._auto(dark=int(v)), self._released)
        self.auto_bright = LabeledSlider("With the lights on", 2, 0, 15, 1, lambda v: f"{int(v)} of 15",
                                         lambda v: self._auto(bright=int(v)), self._released)
        # The light that counts as dark and as bright (firmware 0.8.6); between them a log scale.
        lux_field = lambda label: ft.TextField(
            label=label, suffix="lx", expand=True, keyboard_type=ft.KeyboardType.NUMBER,
            input_filter=ft.InputFilter(regex_string=r"^[0-9]*[.]?[0-9]*$", allow=True, replacement_string=""),
            on_submit=self._lux_entered, on_blur=self._lux_entered)
        self.lux_low = lux_field("Dark is below")
        self.lux_high = lux_field("Bright is above")
        self.lux_range = ft.Row([self.lux_low, self.lux_high], spacing=12)
        self.instant = ft.Switch(label="Follow the light instantly (for testing)",
                                 on_change=lambda e: self._auto(instant=bool(e.control.value)))
        self.auto_rows = ft.Column([self.auto_dark, self.auto_bright, self.lux_range, self.instant], spacing=12)
        self.auto_section = section(
            "Automatic brightness", self.auto, self.auto_rows,
            note="Every tenfold step of light between the two moves the level the same amount, "
                 "so dawn counts as much as switching on a lamp.")

        # Night (moved here from Clock in 0.9.0).
        self.night = ft.Switch(label="Dim at night", on_change=lambda e: self._set_night(enabled=e.control.value))
        self.from_btn = ft.OutlinedButton("23:00", icon=ft.Icons.BEDTIME, on_click=lambda e: self._pick("from"))
        self.to_btn = ft.OutlinedButton("07:00", icon=ft.Icons.WB_SUNNY, on_click=lambda e: self._pick("to"))
        self.night_b = LabeledSlider("Brightness at night", 1, 0, 15, 1,
                                     lambda v: f"{int(v)} of 15" + (" (dimmest)" if v == 0 else ""),
                                     lambda v: self._send_night(int(v)))
        self.night_rows = ft.Column([
            ft.Row([ft.Column([muted("From", 14), self.from_btn], spacing=4),
                    ft.Column([muted("Until", 14), self.to_btn], spacing=4)], spacing=24),
            self.night_b,
        ], spacing=14)

        self.controls = [
            self.auto_section,
            section("Night", self.night, self.night_rows,
                    note="Lowers the brightness during these hours, in every mode; "
                         "with automatic brightness too, as a ceiling."),
        ]

    @staticmethod
    def subtitle(d) -> str:
        ab = d.settings.get("auto_brightness") or {}
        n = d.settings.get("night") or {}
        parts = []
        if ab.get("enabled"):
            parts.append(f"Automatic · {lux_text(ab.get('lux_low', 0.1))}–{lux_text(ab.get('lux_high', 40))} lx"
                         if "lux_low" in ab else "Automatic")
        else:
            parts.append(f"Level {d.settings.get('brightness', '–')} of 15")
        if n.get("enabled"):
            parts.append(f"dim {n.get('from', '23:00')}–{n.get('to', '07:00')}")
        return " · ".join(parts)

    def refresh(self):
        d = self.app.device
        on = d.connected
        ab = d.settings.get("auto_brightness")
        auto_on = bool(ab and ab.get("enabled"))
        self.auto_section.visible = ab is not None
        self.auto_rows.visible = auto_on
        for c in (self.auto, self.auto_dark.slider, self.auto_bright.slider, self.lux_low, self.lux_high, self.instant,
                  self.night, self.from_btn, self.to_btn, self.night_b.slider):
            c.disabled = not on
        self.lux_range.visible = bool(ab) and "lux_low" in ab
        self.instant.visible = bool(ab) and "instant" in ab
        if time.monotonic() - self._touched < 2:
            return  # don't fight the user's finger
        if ab:
            self.auto.value = auto_on
            self.auto_dark.set(ab.get("dark", 0))
            self.auto_bright.set(ab.get("bright", 2))
            self.instant.value = bool(ab.get("instant"))
            if self.lux_range.visible:
                for field, key in ((self.lux_low, "lux_low"), (self.lux_high, "lux_high")):
                    if not field.error:  # keep what's being corrected
                        field.value = lux_text(ab[key])
        n = d.settings.get("night", {})
        self.night.value = n.get("enabled", False)
        self.from_btn.content = n.get("from", "23:00")
        self.to_btn.content = n.get("to", "07:00")
        self.night_b.set(n.get("brightness", 1))
        self.night_rows.visible = bool(self.night.value)

    # --------------------------------------------------------------- actions
    def _released(self, e):
        self._touched = time.monotonic()

    def _auto_switched(self, e):
        on = bool(e.control.value)
        self.auto_rows.visible = on
        self.auto_rows.update()
        self._auto(enabled=on)

    def _auto(self, **changes):
        self._touched = time.monotonic()
        self.app.device.send("set_settings", settings={"auto_brightness": changes})

    def _lux_entered(self, e):
        lo_err, hi_err = lux_range_error(self.lux_low.value or "", self.lux_high.value or "")
        self.lux_low.error, self.lux_high.error = lo_err, hi_err
        self.lux_range.update()
        if lo_err or hi_err:
            return
        ab = self.app.device.settings.get("auto_brightness", {})
        lo, hi = float(self.lux_low.value), float(self.lux_high.value)
        if (lo, hi) != (ab.get("lux_low"), ab.get("lux_high")):
            self._auto(lux_low=lo, lux_high=hi)

    def _set_night(self, **changes):
        self._touched = time.monotonic()
        if "enabled" in changes:
            self.night_rows.visible = changes["enabled"]
            self.night_rows.update()
        self.app.run(self.app.device.update_settings, night=changes)

    async def _night_brightness(self, v):
        self._touched = time.monotonic()
        await self.app.device.update_settings(night={"brightness": v})

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
