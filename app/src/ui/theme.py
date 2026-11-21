"""Colours and type.

Circuit-board green (solder mask) for controls and aluminium greys for surfaces.
The LED colour (red unless chosen otherwise) is kept for the previews, so it always means "this is what the
display shows".
"""
import flet as ft

FONT = "Plex"

GREEN = "#1E6E50"        # solder mask
GREEN_DARK = "#52BE8C"
GOLD = "#B0892A"         # pad gold: marks the group that's playing
GOLD_DARK = "#D9B455"
DANGER = "#B3261E"

LIGHT = dict(bg="#E8EBEE", surface="#F7F8F9", raised="#FFFFFF", line="#CBD2D9",
             ink="#1D2733", muted="#5A6876")
DARK = dict(bg="#121719", surface="#1A2124", raised="#212A2E", line="#33404A",
            ink="#E4E9EC", muted="#97A6B0")


def _scheme(p: dict, primary: str, gold: str, dark: bool) -> ft.ColorScheme:
    return ft.ColorScheme(
        primary=primary, on_primary="#0D1F17" if dark else "#FFFFFF",
        secondary=gold, on_secondary="#1D1600",
        # surface = the aluminium page; cards sit on it in the raised colour
        surface=p["bg"], on_surface=p["ink"], on_surface_variant=p["muted"],
        surface_container_lowest=p["raised"], surface_container_low=p["surface"],
        surface_container=p["surface"], surface_container_high=p["surface"],
        surface_container_highest=p["line"],
        outline=p["line"], outline_variant=p["line"], error=DANGER,
    )


def _switch(p: dict, on_thumb: str) -> ft.SwitchTheme:
    # Material's switch draws the "off" thumb and track border in the outline colour,
    # which here is the same as the track, so an off switch was a blank grey pill.
    # Draw them in the muted ink instead (0.8.8); "on" keeps the defaults.
    off = p["muted"]
    return ft.SwitchTheme(
        thumb_color={ft.ControlState.SELECTED: on_thumb, ft.ControlState.DISABLED: ft.Colors.with_opacity(0.38, off),
                     ft.ControlState.DEFAULT: off},
        track_outline_color={ft.ControlState.SELECTED: ft.Colors.TRANSPARENT,
                             ft.ControlState.DISABLED: ft.Colors.with_opacity(0.38, off),
                             ft.ControlState.DEFAULT: off})


def apply(page: ft.Page):
    page.fonts = {FONT: "IBMPlexSans.ttf"}
    page.theme = ft.Theme(font_family=FONT, color_scheme=_scheme(LIGHT, GREEN, GOLD, False),
                          scaffold_bgcolor=LIGHT["bg"], switch_theme=_switch(LIGHT, "#FFFFFF"))
    page.dark_theme = ft.Theme(font_family=FONT, color_scheme=_scheme(DARK, GREEN_DARK, GOLD_DARK, True),
                               scaffold_bgcolor=DARK["bg"], switch_theme=_switch(DARK, "#0D1F17"))
    page.theme_mode = ft.ThemeMode.SYSTEM


# The choices in Settings → Appearance; "system" follows the phone.
MODES = {"system": ft.ThemeMode.SYSTEM, "light": ft.ThemeMode.LIGHT, "dark": ft.ThemeMode.DARK}


def set_mode(page: ft.Page, key: str):
    page.theme_mode = MODES.get(key, ft.ThemeMode.SYSTEM)


def palette(page: ft.Page) -> dict:
    dark = page.theme_mode == ft.ThemeMode.DARK or (
        page.theme_mode == ft.ThemeMode.SYSTEM and page.platform_brightness == ft.Brightness.DARK)
    p = DARK if dark else LIGHT
    return {**p, "primary": GREEN_DARK if dark else GREEN, "gold": GOLD_DARK if dark else GOLD}
