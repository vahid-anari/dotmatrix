#!/usr/bin/env python3
"""
fake_device — a stand-in for the ESP32 that speaks protocol v1 (docs/DESIGN.md §6).

Lets the app be developed and tested without hardware:

    pip install aiohttp
    python tools/fake_device.py            # ws://127.0.0.1:8080/ws
    python tools/fake_device.py --port 8081 --host 0.0.0.0

Serves the same endpoints as the device on one port: /ws, /api/status and
POST /update (firmware upload; the file is checked and discarded). The effect
and animation lists are read from the firmware source, so they always match
what the real device supports. Every command is printed as it arrives.
"""
import argparse
import asyncio
import json
import re
import time
from pathlib import Path

from aiohttp import WSMsgType, web

ROOT = Path(__file__).resolve().parent.parent
FW = ROOT / "firmware" / "src"


def read_ids(path, pattern):
    try:
        return re.findall(pattern, path.read_text())
    except OSError:
        return []


EFFECTS = read_ids(FW / "display" / "Effects.cpp", r'\{"([a-z0-9_]+)", PA_')
ANIMATIONS = read_ids(FW / "animations" / "Registry.cpp", r'\{"([a-z0-9_]+)", &')
OVERLAYS = read_ids(FW / "display" / "Overlay.cpp", r'"([a-z]+)"(?=[,}])')
SPRITES = read_ids(FW / "display" / "Sprites.cpp", r'\{"([a-z0-9_]+)", \w+, \w+_w')
MAX_ITEMS, MAX_TEXT = 100, 128
fw_version = "0.2.0-fake"

START = time.monotonic()
clients: set[web.WebSocketResponse] = set()
state = {
    "mode": "text",
    "playlist": {"name": "", "items": []},
    "index": -1,
    "preview": None,
    "preview_client": None,
}
settings = {
    "brightness": 6,
    "mode": "text",
    "hostname": "dotmatrix",
    "timezone": "EST5EDT,M3.2.0,M11.1.0",
    "clock": {"format_24h": True, "seconds": True, "date_every": 0, "date_format": "%a %b %d",
              "weather_every": 0},
    "weather": {"place": "", "lat": 0, "lon": 0, "units": "c"},
    "night": {"enabled": False, "from": "23:00", "to": "07:00", "brightness": 1},
}


def now_ms() -> int:
    return int(time.monotonic() * 1000)


class RunClock:
    """Same bookkeeping as firmware/src/modes/TimeFormat.h."""

    def __init__(self):
        self.running, self.since, self.banked = False, 0, 0

    def elapsed(self):
        return self.banked + (now_ms() - self.since if self.running else 0)

    def start(self):
        if not self.running:
            self.since, self.running = now_ms(), True

    def pause(self):
        if self.running:
            self.banked += now_ms() - self.since
            self.running = False

    def reset(self):
        self.running, self.banked = False, 0


stopwatch = RunClock()
timer = {"clock": RunClock(), "total": 5 * 60 * 1000, "done": False}


def timer_remaining():
    return max(0, timer["total"] - timer["clock"].elapsed())


def log(*a):
    print(time.strftime("%H:%M:%S"), *a, flush=True)


def night_active():
    n = settings["night"]
    if not n["enabled"]:
        return False
    t = time.localtime()
    m = t.tm_hour * 60 + t.tm_min
    f = int(n["from"][:2]) * 60 + int(n["from"][3:])
    to = int(n["to"][:2]) * 60 + int(n["to"][3:])
    return (f <= m < to) if f <= to else (m >= f or m < to)


def state_msg():
    b = settings["brightness"]
    if night_active():
        b = min(b, settings["night"]["brightness"])
    return {
        "evt": "state",
        "mode": state["mode"],
        "playlist": state["playlist"]["name"],
        "items": len(state["playlist"]["items"]),
        "index": state["index"],
        "previewing": state["preview"] is not None,
        "time": time.strftime("%Y-%m-%d %H:%M:%S"),
        "brightness": b,
        "night": night_active(),
        "wifi": "online",
        "ip": "127.0.0.1",
        "rssi": -52,
        "uptime": int(time.monotonic() - START),
        "free_heap": 154000,
        "min_free_heap": 148000,
        "last_reset": "power_on",
        "stopwatch": {"ms": stopwatch.elapsed(), "running": stopwatch.running},
        "timer": {"remaining_ms": timer_remaining(), "total_ms": timer["total"],
                  "running": timer["clock"].running, "done": timer["done"]},
        **fake_weather(),
    }


def fake_weather():
    """A made-up reading once a place is set (the real display asks Open-Meteo)."""
    w = settings["weather"]
    if not w.get("place"):
        return {}
    temp = 8.4 if w.get("units") != "f" else 47.1
    return {"weather": {"temp": temp, "units": w.get("units", "c"), "code": 61, "text": "Rain", "age": 42}}


def hello_msg():
    return {"evt": "hello", "proto": 1, "fw": fw_version, "name": settings["hostname"],
            "max_items": MAX_ITEMS, "max_text": MAX_TEXT, "effects": EFFECTS,
            "animations": ANIMATIONS, "overlays": OVERLAYS, "sprites": SPRITES, "modes": ["text", "clock", "off", "stopwatch", "timer"]}


def check_item(it):
    if not isinstance(it, dict):
        return "item must be an object"
    t = it.get("type", "text")
    if t not in ("text", "animation"):
        return "unknown item type"
    if t == "animation" and it.get("animation") not in ANIMATIONS:
        return "unknown animation"
    if len(it.get("text", "")) > MAX_TEXT:
        return "text too long"
    return None


async def send(ws, msg):
    try:
        await ws.send_str(json.dumps(msg))
    except Exception:  # noqa: BLE001
        pass


async def broadcast(msg):
    for ws in list(clients):
        await send(ws, msg)


def describe(it):
    if it.get("type") == "animation":
        return f"[{it.get('animation')}] {it.get('text', '')!r} {it.get('duration', 10000)} ms"
    return f"{it.get('text', '')!r} {it.get('effect_in', 'scroll_left')} → {it.get('effect_out', 'scroll_left')}"


async def handle(ws, raw):
    try:
        msg = json.loads(raw)
    except ValueError:
        return await send(ws, {"evt": "ack", "id": -1, "ok": False, "error": "invalid JSON"})
    mid, cmd = msg.get("id", -1), msg.get("cmd", "")

    def ack(ok=True, error=None):
        m = {"evt": "ack", "id": mid, "ok": ok}
        if error:
            m["error"] = error
        return send(ws, m)

    if cmd == "get_state":
        await ack()
        await send(ws, state_msg())
    elif cmd == "set_mode":
        if msg.get("mode") not in ("text", "clock", "off", "stopwatch", "timer"):
            return await ack(False, "unknown mode")
        state["mode"] = msg["mode"]
        if msg["mode"] in ("text", "clock", "off"):
            settings["mode"] = msg["mode"]
        state["preview"] = None
        log("mode:", msg["mode"])
        await ack()
        await broadcast(state_msg())
    elif cmd == "set_playlist":
        items = msg.get("items")
        if not isinstance(items, list):
            return await ack(False, "missing items")
        if len(items) > MAX_ITEMS:
            return await ack(False, "too many items")
        for i, it in enumerate(items):
            err = check_item(it)
            if err:
                return await ack(False, f"item {i}: {err}")
        state["playlist"] = {"name": msg.get("name", ""), "items": items}
        state["index"] = 0 if items else -1
        log(f"playlist '{msg.get('name', '')}': {len(items)} items")
        for i, it in enumerate(items):
            log(f"   {i:2d}. {describe(it)}")
        await ack()
        await broadcast(state_msg())
    elif cmd == "get_playlist":
        await send(ws, {"evt": "playlist", "id": mid, **state["playlist"]})
    elif cmd == "preview":
        err = check_item(msg.get("item"))
        if err:
            return await ack(False, err)
        state["preview"], state["preview_client"] = msg["item"], ws
        log("preview:", describe(msg["item"]))
        await ack()
    elif cmd == "preview_end":
        state["preview"] = None
        log("preview end")
        await ack()
    elif cmd == "get_settings":
        await ack()
        await send(ws, {"evt": "settings", "settings": settings})
    elif cmd == "set_settings":
        s = msg.get("settings")
        if not isinstance(s, dict):
            return await ack(False, "missing settings")
        b = s.get("brightness")
        if b is not None and not (0 <= b <= 15):
            return await ack(False, "brightness must be 0-15")
        for k, v in s.items():
            if k == "mode":
                continue
            if isinstance(v, dict) and isinstance(settings.get(k), dict):
                settings[k].update(v)
            else:
                settings[k] = v
        log("settings:", json.dumps(s))
        await ack()
        await broadcast({"evt": "settings", "settings": settings})
        await broadcast(state_msg())
    elif cmd == "stopwatch":
        action = msg.get("action")
        if action not in ("start", "pause", "reset", "show"):
            return await ack(False, "action must be start, pause, reset or show")
        if action != "show":
            getattr(stopwatch, action)()
        state["mode"], state["preview"] = "stopwatch", None
        log("stopwatch:", action, stopwatch.elapsed(), "ms")
        await ack()
        await broadcast(state_msg())
    elif cmd == "timer":
        action, secs = msg.get("action"), msg.get("seconds")
        c = timer["clock"]
        if action in ("start", "set") and secs is not None:
            if not isinstance(secs, (int, float)) or not 0 < secs <= 86400:
                return await ack(False, "seconds must be 1-86400")
            timer["total"], timer["done"] = int(secs * 1000), False
            c.reset()
        elif action == "set":
            return await ack(False, "seconds must be 1-86400")
        if action == "start":
            if timer["done"]:
                c.reset()
                timer["done"] = False
            c.start()
        elif action == "pause":
            c.pause()
        elif action == "reset":
            c.reset()
            timer["done"] = False
        elif action not in ("set", "show"):
            return await ack(False, "action must be start, set, pause, reset or show")
        state["mode"], state["preview"] = "timer", None
        log("timer:", action, timer_remaining(), "ms left")
        await ack()
        await broadcast(state_msg())
    elif cmd == "set_wifi":
        log("set_wifi:", msg.get("ssid"))
        await ack()
    elif cmd == "reboot":
        log("reboot requested (ignored)")
        await ack()
    else:
        await ack(False, "unknown command")


async def ws_handler(request):
    ws = web.WebSocketResponse(heartbeat=10, max_msg_size=2**20)
    await ws.prepare(request)
    clients.add(ws)
    log(f"client connected ({len(clients)})")
    await send(ws, hello_msg())
    await send(ws, {"evt": "settings", "settings": settings})
    await send(ws, state_msg())
    try:
        async for m in ws:
            if m.type == WSMsgType.TEXT:
                await handle(ws, m.data)
    finally:
        clients.discard(ws)
        if state["preview_client"] is ws and state["preview"] is not None:
            state["preview"] = None
            log("preview end (client left)")
        log(f"client disconnected ({len(clients)})")
    return ws


async def status_handler(request):
    return web.json_response({"name": settings["hostname"], "fw": fw_version, "wifi": "online",
                              "ip": "127.0.0.1"})


async def update_handler(request):
    """Like the device: accept a multipart firmware upload, then 'reboot'."""
    reader = await request.multipart()
    size, head = 0, b""
    async for part in reader:
        while chunk := await part.read_chunk(64 * 1024):
            if not head:
                head = chunk[:1]
            size += len(chunk)
    # ESP32 app images start with the magic byte 0xE9.
    if size == 0 or head != b"\xe9":
        log(f"update rejected ({size} bytes, not an ESP32 image)")
        return web.json_response({"ok": False}, status=500)
    log(f"update received: {size} bytes; restarting")
    asyncio.get_running_loop().call_later(0.5, lambda: asyncio.ensure_future(fake_reboot()))
    return web.json_response({"ok": True})


async def fake_reboot():
    global fw_version
    for ws in list(clients):
        await ws.close()
    fw_version = request_version_after_update
    log(f"rebooted, now running {fw_version}")


request_version_after_update = "0.2.0"


async def ticker():
    """Advance the playlist index, finish the timer, broadcast state."""
    last = 0.0
    while True:
        await asyncio.sleep(0.25)
        if timer["clock"].running and timer_remaining() == 0:
            timer["clock"].pause()
            timer["clock"].banked = timer["total"]
            timer["done"] = True
            state["mode"], state["preview"] = "timer", None
            log("timer: done")
            await broadcast(state_msg())
        if time.monotonic() - last >= 5:
            last = time.monotonic()
            items = state["playlist"]["items"]
            if state["mode"] == "text" and items and state["preview"] is None:
                state["index"] = (state["index"] + 1) % len(items)
            await broadcast(state_msg())


async def main():
    global request_version_after_update
    p = argparse.ArgumentParser(description="Fake Dot Matrix device")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8080)
    p.add_argument("--fw", default=fw_version, help="firmware version to report")
    p.add_argument("--fw-after-update", default="0.2.0", help="version reported after an upload")
    a = p.parse_args()
    globals()["fw_version"] = a.fw
    request_version_after_update = a.fw_after_update

    app = web.Application(client_max_size=4 * 2**20)
    app.add_routes([web.get("/ws", ws_handler), web.get("/api/status", status_handler),
                    web.post("/update", update_handler)])
    runner = web.AppRunner(app)
    await runner.setup()
    await web.TCPSite(runner, a.host, a.port).start()
    log(f"fake device {fw_version} on ws://{a.host}:{a.port}/ws  ({len(EFFECTS)} effects, "
        f"{len(ANIMATIONS)} animations, {len(OVERLAYS)} overlays)")
    await ticker()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
