"""Tests for the app's core logic (no UI, no device needed).

    cd app && python -m pytest
"""
import asyncio
import json

import pytest

from core import discovery, preview, updates
from core.device import Device, DeviceError
from core.items import DEMO_NAME, demo_items, nice_name, normalized, summary
from core.library import Library


# ------------------------------------------------------------------ items

def test_nice_names():
    assert nice_name("scroll_up_left") == "Scroll up left"
    assert nice_name("sprite_pacman") == "Pacman"
    assert nice_name("no_effect") == "None"


def test_demo_has_one_item_per_effect():
    items = demo_items()
    texts = [i for i in items if i["type"] == "text"]
    assert len(texts) == 45  # 46 effects minus "no_effect"
    assert items[0]["animation"] == "matrix_reveal"


def test_summary_and_normalize():
    it = normalized({"type": "text", "text": "Hi", "effect_in": "slice", "effect_out": "fade", "pause": 1500})
    assert it["speed_in"] == 40 and it["align"] == "center"
    assert summary(it) == "Slice in, fade out, stays 1.5 s"


# ---------------------------------------------------------------- preview

def test_text_width_matches_firmware_rules():
    # 5-column glyphs + 1 column spacing; narrow custom 1 and 7 like Display.cpp
    assert preview.text_width("A") == 5
    assert preview.text_width("AB") == 11
    assert preview.glyph("1") == [0x00, 0x04, 0x02, 0x7F, 0x00]


def test_render_is_png_and_cached():
    png = preview.render_text("Hello")
    assert png.startswith(b"\x89PNG")
    assert preview.render_text("Hello") is png  # lru_cache


def test_invert_and_animation_frames_are_stable():
    inv = preview.frame_for({"text": "", "invert": True})
    assert all(c == 0xFF for c in inv)
    a = preview.frame_for({"type": "animation", "animation": "matrix_rain"})
    b = preview.frame_for({"type": "animation", "animation": "matrix_rain"})
    assert a == b and any(a)


# ---------------------------------------------------------------- library

def test_library_round_trip(tmp_path):
    lib = Library(tmp_path / "lib.json")
    assert lib.find(DEMO_NAME)
    g = lib.add_group("Kitchen")
    g["items"].append({"type": "text", "text": "Dinner!"})
    lib.save()
    again = Library(tmp_path / "lib.json")
    assert again.find("Kitchen")["items"][0]["text"] == "Dinner!"


def test_library_names_rename_import(tmp_path):
    lib = Library(tmp_path / "lib.json")
    a = lib.add_group("A")
    assert lib.add_group("A")["name"] == "A 2"
    assert lib.rename_group(a, "A 2") == "A group with this name already exists."
    assert lib.rename_group(a, "  ") == "The name can't be empty."
    data = lib.export_bytes()
    other = Library(tmp_path / "other.json")
    assert other.import_bytes(data) == len(lib.groups)
    with pytest.raises(ValueError):
        other.import_bytes(json.dumps({"groups": []}).encode())


# -------------------------------------------------- device, against a fake

@pytest.fixture
def fake_server():
    """A tiny protocol-v1 server on a free port."""
    import websockets

    async def handler(ws):
        await ws.send(json.dumps({"evt": "hello", "proto": 1, "fw": "test", "effects": ["print"],
                                  "animations": ["matrix_rain"]}))
        async for raw in ws:
            m = json.loads(raw)
            ok = m["cmd"] != "set_mode" or m.get("mode") in ("text", "clock", "off")
            await ws.send(json.dumps({"evt": "ack", "id": m["id"], "ok": ok,
                                      **({} if ok else {"error": "unknown mode"})}))

    return handler


def test_device_request_and_errors(fake_server):
    import websockets

    async def run():
        async with websockets.serve(fake_server, "127.0.0.1", 0) as server:
            port = server.sockets[0].getsockname()[1]
            d = Device()
            d.start(f"127.0.0.1:{port}")
            for _ in range(50):
                if d.connected and d.hello:
                    break
                await asyncio.sleep(0.05)
            assert d.connected and d.effects == ["print"]
            assert (await d.request("set_mode", mode="clock"))["ok"]
            with pytest.raises(DeviceError, match="unknown mode"):
                await d.request("set_mode", mode="nope")
            await d.stop()

    asyncio.run(run())


def test_device_not_connected():
    async def run():
        with pytest.raises(DeviceError):
            await Device().request("get_state")

    asyncio.run(run())


def test_probe_rejects_non_display():
    async def run():
        assert await discovery.probe("127.0.0.1", 9, timeout=0.2) is None

    asyncio.run(run())


# ---------------------------------------------------------------- updates

def test_versions():
    assert updates.is_newer("0.2.0", "0.1.9")
    assert updates.is_newer("0.10.0", "0.9.0")
    assert updates.is_newer("0.2.0", "0.2.0-dev")  # a release beats its dev build
    assert not updates.is_newer("0.2.0", "0.2.0")
    assert updates.is_newer("0.2.0", "dev-1a2b3c4")  # CI builds from main
    assert updates.parse_version("v1.2.3") == (1, 2, 3, 1)


def _image(chip=5, desc=True, size=100_000):
    b = bytearray(size)
    b[0] = 0xE9
    b[12:14] = chip.to_bytes(2, "little")
    if desc:
        b[0x20:0x24] = bytes.fromhex("3254cdab")
    return bytes(b)


def test_firmware_image_check():
    assert updates.check_firmware_image(_image()) is None
    assert "different ESP32" in updates.check_firmware_image(_image(chip=0))
    assert "full flash image" in updates.check_firmware_image(_image(desc=False))
    assert updates.check_firmware_image(b"PK" + b"\0" * 100_000)  # a zip, not firmware
    assert updates.check_firmware_image(b"\xe9")  # too small


def test_time_formats_match_firmware():
    from ui.tools import fmt_stopwatch, fmt_timer  # same cases as firmware/test_host
    assert fmt_stopwatch(83123) == "01:23.12"
    assert fmt_stopwatch(3723000) == "1:02:03"
    assert fmt_timer(1) == "00:01" and fmt_timer(0) == "00:00"
    assert fmt_timer(3600000) == "1:00:00"


def test_upload_to_fake_device(tmp_path):
    """The real upload code against an HTTP server that checks the multipart body."""
    import http.server
    import threading

    got = {}

    class H(http.server.BaseHTTPRequestHandler):
        def do_POST(self):
            n = int(self.headers["Content-Length"])
            body = self.rfile.read(n)
            got["ctype"] = self.headers["Content-Type"]
            got["body"] = body
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b'{"ok":true}')

        def log_message(self, *a):
            pass

    srv = http.server.HTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    data = b"\xe9" + bytes(range(256)) * 400
    steps = []

    async def run():
        await updates.upload_firmware(f"127.0.0.1:{srv.server_port}", data, steps.append)

    asyncio.run(run())
    srv.shutdown()
    assert got["ctype"].startswith("multipart/form-data; boundary=")
    assert data in got["body"] and b'name="firmware"' in got["body"]
    assert steps and steps[-1] == 1.0
