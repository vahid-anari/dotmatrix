"""Settings: finding the display, its name and time zone, Wi-Fi, backup."""
import time

import flet as ft

from core import updates
from core.device import PROTO_VERSION

from . import theme
from .app import APP_VERSION
from .widgets import heading, muted, section

# POSIX TZ strings: the ESP32 has no time zone database, so it needs these.
TIMEZONES = [
    ("EST5EDT,M3.2.0,M11.1.0", "Toronto, New York (Eastern)"),
    ("CST6CDT,M3.2.0,M11.1.0", "Chicago, Winnipeg (Central)"),
    ("MST7MDT,M3.2.0,M11.1.0", "Denver, Edmonton (Mountain)"),
    ("PST8PDT,M3.2.0,M11.1.0", "Vancouver, Los Angeles (Pacific)"),
    ("GMT0BST,M3.5.0/1,M10.5.0", "London"),
    ("CET-1CEST,M3.5.0,M10.5.0/3", "Paris, Berlin, Rome, Warsaw"),
    ("EET-2EEST,M3.5.0/3,M10.5.0/4", "Athens, Helsinki"),
    ("<+0330>-3:30", "Tehran"),
    ("<+03>-3", "Istanbul"),
    ("GST-4", "Dubai"),
    ("JST-9", "Tokyo"),
    ("UTC0", "UTC"),
]


class SettingsTab:
    def __init__(self, app):
        self.app = app
        self._found: list[dict] = []

        self.status = muted("", 14)
        self.address = ft.TextField(label="Display address", hint_text="e.g. 192.168.1.50", expand=True,
                                    dense=True, on_submit=self._connect)
        self.connect_btn = ft.OutlinedButton("Connect", on_click=self._connect)
        self.find_btn = ft.FilledButton("Find the display", icon=ft.Icons.WIFI_FIND, on_click=self._find)
        self.progress = ft.ProgressBar(value=0, visible=False)
        self.found_list = ft.Column(spacing=6)

        self.hostname = ft.TextField(label="Name on the network", expand=True, dense=True, suffix=".local")
        self.host_btn = ft.OutlinedButton("Save", on_click=self._save_hostname)
        self.tz = ft.Dropdown(label="Time zone", expand=True,
                              options=[ft.DropdownOption(key=k, text=t) for k, t in TIMEZONES],
                              on_select=self._tz_changed)
        self.wifi_btn = ft.OutlinedButton("Move to another Wi-Fi network", icon=ft.Icons.WIFI, on_click=self._wifi)
        self.reboot_btn = ft.OutlinedButton("Restart the display", icon=ft.Icons.RESTART_ALT, on_click=self._reboot)
        self.about = ft.Column(spacing=6)

        self.upd_status = muted("", 14)
        self.upd_check = ft.OutlinedButton("Check for updates", icon=ft.Icons.SYNC, on_click=self._check)
        self.app_upd = ft.FilledButton(icon=ft.Icons.DOWNLOAD, on_click=self._get_app, visible=False)
        self.fw_upd = ft.FilledButton(icon=ft.Icons.SYSTEM_UPDATE_ALT, on_click=self._install_fw, visible=False)
        self.fw_progress = ft.ProgressBar(value=0, visible=False)
        self.fw_step = muted("", 14)
        self._installing = False
        self.launcher = ft.UrlLauncher()

        self.file_picker = ft.FilePicker()

        self.theme = ft.SegmentedButton(
            segments=[ft.Segment(value="system", label="Phone", icon=ft.Icons.SMARTPHONE),
                      ft.Segment(value="light", label="Light", icon=ft.Icons.LIGHT_MODE),
                      ft.Segment(value="dark", label="Dark", icon=ft.Icons.DARK_MODE)],
            selected=[app.library.prefs.get("theme", "system")], show_selected_icon=False,
            on_change=self._theme_changed)

        self.view = ft.Column([
            heading("Settings"),
            section("Connection", self.status, ft.Row([self.address, self.connect_btn]),
                    self.find_btn, self.progress, self.found_list,
                    note="The phone and the display must be on the same Wi-Fi."),
            section("Display", ft.Row([self.hostname, self.host_btn]), ft.Row([self.tz]),
                    self.wifi_btn, self.reboot_btn),
            section("Your texts",
                    ft.Row([ft.OutlinedButton("Export", icon=ft.Icons.UPLOAD_FILE, on_click=self._export),
                            ft.OutlinedButton("Import", icon=ft.Icons.FILE_OPEN, on_click=self._import)], wrap=True),
                    note="Save all groups to a file, or add groups from one."),
            section("Appearance", self.theme, note="Phone: light or dark, as the phone is set."),
            section("Updates", self.upd_status, self.app_upd, self.fw_upd, self.fw_progress, self.fw_step,
                    self.upd_check,
                    note="New versions come from this project's releases on GitHub."),
            section("About", self.about),
        ], spacing=22, scroll=ft.ScrollMode.AUTO, expand=True)
        self.refresh()

    def refresh(self):
        d = self.app.device
        on = d.connected
        if d.connected:
            self.status.value = f"Connected to {d.hello.get('name', 'the display')} at {d.host}."
        elif self.app.scanning:
            self.status.value = "Looking for the display on this Wi-Fi…"
        elif d.host:
            self.status.value = f"Can't reach {d.host}. {d.error}".strip()
        else:
            self.status.value = "No display set up yet. Tap Find the display."
        if not self.address.value and d.host:
            self.address.value = d.host
        self.find_btn.disabled = self.app.scanning
        for c in (self.hostname, self.host_btn, self.tz, self.wifi_btn, self.reboot_btn):
            c.disabled = not on
        s = d.settings
        if on and not self.hostname.value:
            self.hostname.value = s.get("hostname", "dotmatrix")
        tz = s.get("timezone")
        if tz and tz not in {k for k, _ in TIMEZONES} and not any(o.key == tz for o in self.tz.options):
            self.tz.options.append(ft.DropdownOption(key=tz, text=tz))
        self.tz.value = tz
        rows = [("App", APP_VERSION), ("Firmware", d.hello.get("fw", "–")),
                ("Protocol", f"{PROTO_VERSION}" + (" (display differs)" if d.proto_mismatch else ""))]
        self.about.controls = [ft.Row([muted(k, 14), ft.Text(v, size=14)],
                                      alignment=ft.MainAxisAlignment.SPACE_BETWEEN) for k, v in rows]
        self._refresh_updates()

    def _refresh_updates(self):
        app, latest = self.app, self.app.latest
        if self._installing:
            return
        if app.update_error:
            self.upd_status.value = app.update_error
        elif latest is None:
            self.upd_status.value = "Checking…"
        elif app.app_update or app.firmware_update:
            self.upd_status.value = f"Version {latest.version} is available."
        else:
            self.upd_status.value = f"Up to date (latest release is {latest.version})." if latest.version \
                else "No releases yet."
        d = app.device
        if self.fw_step.value.startswith("Installed") and d.connected and latest \
                and d.hello.get("fw") == latest.version:
            self.fw_step.value = ""  # the display is back, running the new version
        self.app_upd.visible = app.app_update
        self.app_upd.content = f"Download app {latest.version}" if latest else ""
        self.fw_upd.visible = app.firmware_update
        self.fw_upd.content = f"Install firmware {latest.version} on the display" if latest else ""

    def _theme_changed(self, e):
        key = next(iter(e.control.selected), "system")
        self.app.library.prefs["theme"] = key
        self.app.library.save()
        theme.set_mode(self.app.page, key)
        self.app.refresh()  # colours worked out in code (borders, the playing group)

    # --------------------------------------------------------------- connect
    def _connect(self, e):
        host = (self.address.value or "").strip()
        if host:
            self.app.use_host(host)
            self.app.refresh()

    async def _find(self, e):
        self.progress.visible, self.progress.value = True, 0
        self.found_list.controls = []
        self.app.refresh()

        def progress(frac):
            self.progress.value = frac

        found = await self.app.find_device(progress=progress)
        self.progress.visible = False
        if not found:
            self.found_list.controls = [muted("No display found. Check that it shows the clock or a text, "
                                              "and that the phone is on the same Wi-Fi. You can also type "
                                              "the address it shows after connecting.", 14)]
        elif len(found) > 1:
            self.found_list.controls = [
                ft.ListTile(title=ft.Text(f["name"]), subtitle=ft.Text(f["host"]), leading=ft.Icon(ft.Icons.GRID_ON),
                            on_click=lambda ev, h=f["host"]: self.app.use_host(h)) for f in found]
        else:
            self.address.value = found[0]["host"]
        self.app.refresh()

    # --------------------------------------------------------------- display
    def _save_hostname(self, e):
        name = (self.hostname.value or "").strip().lower()
        self.app.run(self.app.device.update_settings, hostname=name, ok=f"Now reachable as {name}.local")

    def _tz_changed(self, e):
        self.app.run(self.app.device.update_settings, timezone=e.control.value, ok="Time zone changed")

    def _wifi(self, e):
        ssid = ft.TextField(label="Network name", autofocus=True)
        pw = ft.TextField(label="Password", password=True, can_reveal_password=True)

        def go(ev):
            if not ssid.value:
                ssid.error = "Enter the network name"
                ssid.update()
                return
            self.app.page.pop_dialog()
            self.app.run(self.app.device.request, "set_wifi", ssid=ssid.value, password=pw.value or "",
                         ok="The display restarts and joins the new network.")

        self.app.page.show_dialog(ft.AlertDialog(
            title=ft.Text("Move to another Wi-Fi"),
            content=ft.Column([muted("The display restarts and joins this network. If it can't, it opens its "
                                     "setup network again (DotMatrix-…).", 14), ssid, pw], tight=True, spacing=12),
            actions=[ft.TextButton("Cancel", on_click=lambda ev: self.app.page.pop_dialog()),
                     ft.FilledButton("Move", on_click=go)]))

    def _reboot(self, e):
        self.app.run(self.app.device.request, "reboot", ok="Restarting the display…")

    # --------------------------------------------------------------- library
    async def _export(self, e):
        data = self.app.library.export_bytes()
        name = f"dotmatrix-texts-{time.strftime('%Y-%m-%d')}.json"
        try:
            path = await self.file_picker.save_file(dialog_title="Export texts", file_name=name,
                                                    allowed_extensions=["json"], src_bytes=data)
        except Exception as ex:  # noqa: BLE001 — platform without a save dialog
            self.app.toast(f"Couldn't export: {ex}")
            return
        if path:
            # Desktop returns a path without writing; mobile writes src_bytes itself.
            try:
                with open(path, "wb") as f:
                    f.write(data)
            except OSError:
                pass
            self.app.toast("Texts exported")

    async def _import(self, e):
        files = await self.file_picker.pick_files(dialog_title="Import texts", allowed_extensions=["json"],
                                                  with_data=True)
        if not files:
            return
        f = files[0]
        data = f.bytes
        if data is None and f.path:
            with open(f.path, "rb") as fh:
                data = fh.read()
        try:
            n = self.app.library.import_bytes(data or b"")
        except (ValueError, UnicodeDecodeError) as ex:
            self.app.toast(str(ex) if isinstance(ex, ValueError) and str(ex) else "That file couldn't be read.")
            return
        self.app.toast(f"Added {n} group{'s' if n != 1 else ''}")
        self.app.refresh()

    # --------------------------------------------------------------- updates
    async def _check(self, e):
        self.upd_status.value = "Checking…"
        self.upd_status.update()
        await self.app.check_updates()

    async def _get_app(self, e):
        latest = self.app.latest
        if latest and latest.apk_url:
            # The phone's browser downloads it; open the file to install over this version.
            await self.launcher.launch_url(latest.apk_url)
            self.app.toast("Downloading. Open the file when it's done to install the update.")

    def _install_fw(self, e):
        latest, d = self.app.latest, self.app.device
        if not latest:
            return

        def yes(ev):
            self.app.page.pop_dialog()
            self.app.page.run_task(self._do_install)

        self.app.page.show_dialog(ft.AlertDialog(
            title=ft.Text(f"Install firmware {latest.version}?"),
            content=ft.Text(f"The display runs {d.hello.get('fw', '?')}. Your phone downloads the update "
                            "from GitHub and sends it to the display over Wi-Fi. This takes about a minute, "
                            "then the display restarts. Your texts and settings stay."),
            actions=[ft.TextButton("Cancel", on_click=lambda ev: self.app.page.pop_dialog()),
                     ft.FilledButton("Install", on_click=yes)]))

    async def _do_install(self):
        latest, d = self.app.latest, self.app.device
        self._installing = True
        self.fw_upd.disabled = self.upd_check.disabled = True
        self.fw_progress.visible, self.fw_progress.value = True, 0

        def step(text, frac=None):
            self.fw_step.value = text
            if frac is not None:
                self.fw_progress.value = frac
            self.app.page.update()

        try:
            step("Downloading from GitHub…")
            data = await updates.download(latest.firmware_url, lambda f: step("Downloading from GitHub…", f * 0.3))
            err = updates.check_firmware_image(data)
            if err:
                raise RuntimeError(err)
            step("Sending to the display…", 0.3)
            await updates.upload_firmware(d.host, data, lambda f: step("Sending to the display…", 0.3 + f * 0.7))
            step("Installed. The display is restarting…", 1.0)
            self.app.toast(f"Firmware {latest.version} installed. The display reconnects in a few seconds.")
        except Exception as ex:  # noqa: BLE001 — show any failure to the user
            step(f"The update didn't finish: {ex} The display keeps its current firmware.")
        finally:
            self._installing = False
            self.fw_upd.disabled = self.upd_check.disabled = False
            self.fw_progress.visible = False
            self.app.refresh()
