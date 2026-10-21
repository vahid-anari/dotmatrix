"""Settings: finding the display, its name and time zone, Wi-Fi, backup."""
import time

import flet as ft

from core.device import PROTO_VERSION

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

        self.file_picker = ft.FilePicker()

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
