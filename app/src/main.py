"""Dot Matrix — Android app for the ESP32-C3 LED display.

Run on a computer:   flet run src/main.py          (or --web)
Build for Android:   flet build apk                (from the app/ folder)
Test without hardware: python ../tools/fake_device.py, then set the address
to 127.0.0.1:8080 in Settings.
"""
import asyncio
import logging
import os
import time

import flet as ft

from core import preview
from ui import theme
from ui.app import App
from ui.clock import ClockTab
from ui.home import ConnectionLine, HomeTab
from ui.settings import SettingsTab
from ui.texts import TextsTab
from ui.tools import ToolsTab

logging.basicConfig(level=os.getenv("DM_LOG", "WARNING"))

SETTINGS = 4      # Settings is always the last tab
EXIT_WINDOW = 2.0  # seconds for the second Back that leaves the app


async def main(page: ft.Page):
    page.title = "Dot Matrix"
    theme.apply(page)

    app = App(page)
    theme.set_mode(page, app.library.prefs.get("theme", "system"))
    preview.set_color(app.library.prefs.get("led_color", "red"))
    # For development: DM_HOST=127.0.0.1:8080 flet run src/main.py
    if os.getenv("DM_HOST"):
        app.library.prefs["host"] = os.getenv("DM_HOST")

    tabs: list = [HomeTab(app, open_settings=lambda: select(SETTINGS)), TextsTab(app), ClockTab(app),
                  ToolsTab(app), SettingsTab(app)]
    current = {"tab": 0, "asked_exit": None}  # the tab showing; when Back last said "again to exit"

    # The app's name stays at the top on every tab, with the connection as one dim line under it.
    conn = ConnectionLine(app, lambda e: select(SETTINGS), compact=True)
    app.register(conn)
    appbar = ft.AppBar(
        title=ft.Column([ft.Text("Dot Matrix", size=20, weight=ft.FontWeight.BOLD), conn],
                        spacing=0, tight=True),
        toolbar_height=64,
    )

    def select(i: int):
        """Show tab i, whether it was tapped in the bar, swiped to, or chosen in code."""
        for t in tabs:
            app.unregister(t)
        tab = tabs[i]
        app.register(tab)
        current["tab"] = i
        nav.selected_index = i
        if pager.selected_index != i:
            pager.selected_index = i
        tab.refresh()
        page.update()

    def swiped(e):
        i = int(e.data) if getattr(e, "data", None) not in (None, "") else e.control.selected_index
        if i != current["tab"]:
            select(i)

    # The tabs side by side: a swipe slides to the next one, and the bar follows.
    pager = ft.PageView(
        [ft.Container(t.view, padding=ft.Padding.only(left=16, right=16, top=8), expand=True) for t in tabs],
        selected_index=0, on_change=swiped, expand=True)

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

    async def back(e):
        """Android's Back on the tabs: from another tab to Home; on Home, a second Back
        within EXIT_WINDOW seconds leaves the app (the first only says so). Pages opened
        on top (a group, the editor) and dialogs close first, before this is asked."""
        now = time.monotonic()
        if current["tab"] != 0:
            current["asked_exit"] = None
            await e.control.confirm_pop(False)
            select(0)
        elif current["asked_exit"] is not None and now - current["asked_exit"] <= EXIT_WINDOW:
            await e.control.confirm_pop(True)
        else:
            current["asked_exit"] = now
            await e.control.confirm_pop(False)
            app.toast("Press Back again to exit")

    root = ft.View(route="/", appbar=appbar, controls=[ft.SafeArea(pager, expand=True)], navigation_bar=nav,
                   padding=0, can_pop=False, on_confirm_pop=back)
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
            showing = tabs[current["tab"]] if len(page.views) == 1 else None
            if showing is not None and hasattr(showing, "tick") and showing.tick():
                try:
                    showing.view.update()
                except Exception:  # noqa: BLE001 — page closing
                    return

    page.run_task(ticker)


if __name__ == "__main__":
    ft.run(main, assets_dir="assets")
