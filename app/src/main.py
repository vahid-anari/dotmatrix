"""Dot Matrix — Android app for the ESP32-C3 LED display.

Run on a computer:   flet run src/main.py          (or --web)
Build for Android:   flet build apk                (from the app/ folder)
Test without hardware: python ../tools/fake_device.py, then set the address
to 127.0.0.1:8080 in Settings.
"""
import asyncio
import logging
import os

import flet as ft

from ui import theme
from ui.app import App
from ui.clock import ClockTab
from ui.home import HomeTab
from ui.settings import SettingsTab
from ui.texts import TextsTab
from ui.tools import ToolsTab

logging.basicConfig(level=os.getenv("DM_LOG", "WARNING"))


async def main(page: ft.Page):
    page.title = "Dot Matrix"
    theme.apply(page)

    app = App(page)
    # For development: DM_HOST=127.0.0.1:8080 flet run src/main.py
    if os.getenv("DM_HOST"):
        app.library.prefs["host"] = os.getenv("DM_HOST")

    tabs: list = []
    body = ft.Container(expand=True, padding=ft.Padding.only(left=16, right=16, top=8))

    def select(i: int):
        for t in tabs:
            app.unregister(t)
        tab = tabs[i]
        app.register(tab)
        body.content = tab.view
        nav.selected_index = i
        tab.refresh()
        page.update()

    tabs.extend([HomeTab(app, open_settings=lambda: select(4)), TextsTab(app), ClockTab(app), ToolsTab(app),
                 SettingsTab(app)])

    nav = ft.NavigationBar(
        selected_index=0,
        destinations=[
            ft.NavigationBarDestination(icon=ft.Icons.GRID_VIEW_OUTLINED, selected_icon=ft.Icons.GRID_VIEW_ROUNDED,
                                        label="Home"),
            ft.NavigationBarDestination(icon=ft.Icons.TEXT_SNIPPET_OUTLINED, selected_icon=ft.Icons.TEXT_SNIPPET,
                                        label="Texts"),
            ft.NavigationBarDestination(icon=ft.Icons.SCHEDULE_OUTLINED, selected_icon=ft.Icons.SCHEDULE,
                                        label="Clock"),
            ft.NavigationBarDestination(icon=ft.Icons.TIMER_OUTLINED, selected_icon=ft.Icons.TIMER,
                                        label="Tools"),
            ft.NavigationBarDestination(icon=ft.Icons.SETTINGS_OUTLINED, selected_icon=ft.Icons.SETTINGS,
                                        label="Settings"),
        ],
        on_change=lambda e: select(e.control.selected_index),
    )

    root = ft.View(route="/", controls=[ft.SafeArea(body, expand=True)], navigation_bar=nav, padding=0)
    app.root = root
    page.views.clear()
    page.views.append(root)

    async def view_pop(e):
        app.pop()

    page.on_view_pop = view_pop
    select(0)
    app.start()

    async def ticker():
        """Four times a second, so clock and stopwatch previews run like the display."""
        while True:
            await asyncio.sleep(0.25)
            current = tabs[nav.selected_index] if len(page.views) == 1 else None
            if current is not None and hasattr(current, "tick") and current.tick():
                try:
                    current.view.update()
                except Exception:  # noqa: BLE001 — page closing
                    return

    page.run_task(ticker)


if __name__ == "__main__":
    ft.run(main, assets_dir="assets")
