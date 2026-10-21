"""The app controller: owns the device link, the library, and navigation.

Screens get this object, call its helpers, and implement `refresh()`, which is
called whenever the device reports something new.
"""
import logging

import flet as ft

from core import discovery, updates
from core.device import Device, DeviceError
from core.library import Library

from . import theme

APP_VERSION = "0.3.1"  # must match app/pyproject.toml and the release tag (CI checks)
log = logging.getLogger("app")


class App:
    def __init__(self, page: ft.Page):
        self.page = page
        self.device = Device()
        self.library = Library()
        self.scanning = False
        self._failures = 0
        self._refreshables: list = []  # screens currently on screen
        self.root = None  # set by main
        self.latest: updates.Release | None = None  # newest GitHub release, once checked
        self.update_error = ""

        self.device.listen(self._on_device)

    # ------------------------------------------------------------ connection
    def start(self):
        host = self.library.prefs.get("host", "")
        if host:
            self.device.start(host)
        else:
            self.page.run_task(self.find_device)
        self.page.run_task(self.check_updates)

    # --------------------------------------------------------------- updates
    async def check_updates(self) -> bool:
        """Look up the newest release on GitHub. Returns True on success."""
        try:
            self.latest = await updates.latest_release()
            self.update_error = ""
        except updates.NoReleases:
            self.latest = updates.Release(version="", page="")
            self.update_error = ""
        except Exception as ex:  # noqa: BLE001 — offline, rate-limited
            log.info("update check failed: %s", ex)
            self.update_error = "Couldn't reach GitHub. Check the phone's internet connection."
            return False
        finally:
            self.refresh()
        return True

    @property
    def app_update(self) -> bool:
        return bool(self.latest and self.latest.apk_url and updates.is_newer(self.latest.version, APP_VERSION))

    @property
    def firmware_update(self) -> bool:
        fw = self.device.hello.get("fw", "")
        if not (self.device.connected and self.latest and self.latest.firmware_url):
            return False
        # Firmware from before M3 has no stopwatch/timer and reported "0.9.0",
        # which looks newer than the first releases: offer it the update anyway.
        return updates.is_newer(self.latest.version, fw) or not self.device.has_tools

    async def find_device(self, progress=None) -> list[dict]:
        """Look for displays; connects to the first one found. Returns all found."""
        if self.scanning:
            return []
        self.scanning = True
        self.refresh()
        try:
            found = await discovery.find(self.library.prefs.get("host", ""), progress=progress)
        finally:
            self.scanning = False
        if found:
            self.use_host(found[0]["host"])
        self.refresh()
        return found

    def use_host(self, host: str):
        host = host.strip()
        if not host:
            return
        self.library.prefs["host"] = host
        self.library.save()
        self._failures = 0
        self.device.start(host)

    def _on_device(self, what: str):
        if what == "status":
            if self.device.connected:
                self._failures = 0
            elif self.device.status == Device.DISCONNECTED and self.device.host:
                self._failures += 1
                # The address may have changed (new IP from the router): look again.
                if self._failures == 3 and not self.scanning:
                    self.page.run_task(self.find_device)
        if what == "hello" and self.device.proto_mismatch:
            self.toast("This display runs a different firmware version. Some features may not work.")
        self.refresh()

    # ------------------------------------------------------------ navigation
    def register(self, screen):
        if screen not in self._refreshables:
            self._refreshables.append(screen)

    def unregister(self, screen):
        if screen in self._refreshables:
            self._refreshables.remove(screen)

    def refresh(self):
        for s in list(self._refreshables):
            try:
                s.refresh()
            except Exception:  # noqa: BLE001
                log.exception("refresh failed")
        try:
            self.page.update()
        except Exception:  # noqa: BLE001 — page closing
            pass

    def push(self, view: ft.View, screen=None):
        if screen:
            view.data = screen
            self.register(screen)
        self.page.views.append(view)
        self.page.update()

    def pop(self):
        if len(self.page.views) <= 1:
            return
        view = self.page.views.pop()
        screen = view.data
        if screen is not None:
            if hasattr(screen, "on_close"):
                screen.on_close()
            self.unregister(screen)
        self.refresh()

    # -------------------------------------------------------------- messages
    def toast(self, text: str):
        self.page.show_dialog(ft.SnackBar(ft.Text(text), behavior=ft.SnackBarBehavior.FLOATING,
                                          duration=3500))

    def run(self, coro_fn, *args, ok: str | None = None, **kwargs):
        """Run a device action in the background; report errors as a toast."""

        async def wrapper():
            try:
                await coro_fn(*args, **kwargs)
                if ok:
                    self.toast(ok)
            except DeviceError as ex:
                self.toast(str(ex))

        self.page.run_task(wrapper)

    def need_device(self) -> bool:
        if self.device.connected:
            return True
        self.toast("Not connected to the display")
        return False

    def palette(self) -> dict:
        return theme.palette(self.page)

    # ------------------------------------------------------------- playlist
    def active_group(self) -> dict | None:
        """The library group the display is playing, if it came from this phone."""
        name = self.device.state.get("playlist")
        group = self.library.find(name) if name else None
        # Same name but different content (edited on another phone): don't guess.
        if group and len(group["items"]) != self.device.state.get("items"):
            return None
        return group

    def sync_if_active(self, group: dict):
        """Keep the display in step when the group it plays is edited."""
        if self.device.connected and self.device.state.get("playlist") == group["name"] \
                and self.device.state.get("mode") == "text":
            self.run(self.device.send_playlist, group["name"], group["items"])


    def sync_renamed(self, old_name: str, group: dict):
        """If the display plays the renamed group, give it the new name too."""
        if self.device.connected and self.device.state.get("playlist") == old_name:
            self.run(self.device.send_playlist, group["name"], group["items"])
