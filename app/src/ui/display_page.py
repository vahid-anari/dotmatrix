"""Settings → Display: how the display itself is doing (Wi-Fi, chip temperature,
memory, storage), its Wi-Fi radio, its name, and restarting it."""
import flet as ft

from .home import signal_words, uptime_words
from .widgets import muted, section

TX_STEPS = (8.5, 11.0, 15.0, 19.5)  # dBm; the firmware takes any of its own steps


def kb(n: int) -> str:
    return f"{round(n / 1024)} KB"


def device_rows(d) -> list[tuple[str, str]]:
    """Label/value rows about the display, from its state."""
    st = d.state
    if not d.connected:
        return [("Address", d.host or "–")]
    rssi = st.get("rssi", 0)
    rows = [("Address", d.host),
            ("Wi-Fi signal", f"{signal_words(rssi)} ({rssi} dBm)".replace("-", "−") if rssi else "–"),
            ("Running for", uptime_words(st.get("uptime", 0))),
            ("Firmware", d.hello.get("fw", "–"))]
    chip = st.get("chip")
    if chip:  # firmware 0.9.0
        rows.append(("Chip temperature", f"{chip['c']:.0f} °C (since the start {chip['min']:.0f}–{chip['max']:.0f})"))
    if "free_heap" in st:
        heap = kb(st["free_heap"]) + " free"
        if "heap_size" in st:
            heap += f" of {kb(st['heap_size'])}"
        if "min_free_heap" in st:
            heap += f" (lowest {kb(st['min_free_heap'])})"
        rows.append(("Memory", heap))
    if st.get("fs_total"):
        rows.append(("Storage", f"{kb(st['fs_used'])} of {kb(st['fs_total'])} used"))
    return rows


def subtitle(d) -> str:
    if not d.connected:
        return "Not connected"
    st = d.state
    parts = [d.hello.get("name", "dotmatrix") + ".local"]
    if st.get("chip"):
        parts.append(f"chip {st['chip']['c']:.0f} °C")
    if "free_heap" in st:
        parts.append(f"{kb(st['free_heap'])} free")
    return " · ".join(parts)


class DisplayPage:
    def __init__(self, app, hostname_row: ft.Control, wifi_btn: ft.Control, reboot_btn: ft.Control):
        self.app = app
        self.facts = ft.Column(spacing=6)
        self.tx = ft.SegmentedButton(
            segments=[ft.Segment(value=f"{v:g}", label=ft.Text(f"{v:g}")) for v in TX_STEPS],
            selected=["8.5"], show_selected_icon=False,
            on_change=lambda e: self._radio(tx_power=float(next(iter(e.control.selected), "8.5"))))
        self.sleep = ft.Switch(label="Let the radio doze between the router's signals",
                               on_change=lambda e: self._radio(sleep=bool(e.control.value)))
        self.radio = section(
            "Wi-Fi radio",
            ft.Column([muted("Transmit power (dBm)", 14), ft.Row([self.tx], scroll=ft.ScrollMode.AUTO)], spacing=6),
            self.sleep,
            note="Stronger reaches further and warms the chip a little; some of these boards don't "
                 "connect at all when it's strong. Dozing keeps the chip much cooler; while it dozes "
                 "the display waits 20 s for the router before it counts the Wi-Fi as lost. If a change loses the Wi-Fi for a minute, the "
                 "display goes back to what worked and notes it under History → Events.")
        self.controls = [
            section("Now", self.facts,
                    note="The chip's temperature is the ESP32's own: well above the room, as its radio "
                         "is always on."),
            self.radio,
            section("Name and network", hostname_row, wifi_btn, reboot_btn),
        ]

    def refresh(self):
        d = self.app.device
        self.facts.controls = [
            ft.Row([muted(k, 14), ft.Text(v, size=14, text_align=ft.TextAlign.RIGHT, expand=True)],
                   alignment=ft.MainAxisAlignment.SPACE_BETWEEN, spacing=12)
            for k, v in device_rows(d)]
        r = d.settings.get("radio")
        self.radio.visible = r is not None  # firmware 0.9.0
        if r:
            tx = min(TX_STEPS, key=lambda v: abs(v - r.get("tx_power", 8.5)))
            self.tx.selected = [f"{tx:g}"]
            self.sleep.value = bool(r.get("sleep"))
        self.tx.disabled = self.sleep.disabled = not d.connected

    def _radio(self, **changes):
        self.app.run(self.app.device.update_settings, radio=changes)
