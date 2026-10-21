"""Colours and type.

Circuit-board green (solder mask) for controls and aluminium greys for surfaces.
Red is reserved for the LED previews, so red always means "this is what the
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


def apply(page: ft.Page):
    page.fonts = {FONT: "IBMPlexSans.ttf"}
    page.theme = ft.Theme(font_family=FONT, color_scheme=_scheme(LIGHT, GREEN, GOLD, False),
                          scaffold_bgcolor=LIGHT["bg"])
    page.dark_theme = ft.Theme(font_family=FONT, color_scheme=_scheme(DARK, GREEN_DARK, GOLD_DARK, True),
                               scaffold_bgcolor=DARK["bg"])
    page.theme_mode = ft.ThemeMode.SYSTEM


def palette(page: ft.Page) -> dict:
    dark = page.theme_mode == ft.ThemeMode.DARK or (
        page.theme_mode == ft.ThemeMode.SYSTEM and page.platform_brightness == ft.Brightness.DARK)
    p = DARK if dark else LIGHT
    return {**p, "primary": GREEN_DARK if dark else GREEN, "gold": GOLD_DARK if dark else GOLD}
