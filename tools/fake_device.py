#!/usr/bin/env python3
"""
fake_device — a stand-in for the ESP32 that speaks protocol v1 (docs/DESIGN.md §6).

Lets the app be developed and tested without hardware:

    pip install websockets
    python tools/fake_device.py            # ws://127.0.0.1:8080/ws
    python tools/fake_device.py --port 8081 --host 0.0.0.0

The effect and animation lists are read from the firmware source, so they always
match what the real device supports. Every command is printed as it arrives.
"""
import argparse
import asyncio
import json
import re
import time
from http import HTTPStatus
from pathlib import Path

from websockets.asyncio.server import serve
from websockets.http11 import Response
from websockets.datastructures import Headers
from websockets.exceptions import ConnectionClosed

ROOT = Path(__file__).resolve().parent.parent
FW = ROOT / "firmware" / "src"


def read_ids(path, pattern):
    try:
        return re.findall(pattern, path.read_text())
    except OSError:
        return []


EFFECTS = read_ids(FW / "display" / "Effects.cpp", r'\{"([a-z0-9_]+)", PA_')
ANIMATIONS = read_ids(FW / "animations" / "Registry.cpp", r'\{"([a-z0-9_]+)", &')
MAX_ITEMS, MAX_TEXT = 100, 128
FW_VERSION = "0.9.0-fake"

START = time.monotonic()
clients = set()
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
    "clock": {"format_24h": True, "seconds": True, "date_every": 0, "date_format": "%a %b %d"},
    "night": {"enabled": False, "from": "23:00", "to": "07:00", "brightness": 1},
}


def log(*a):
    print(time.strftime("%H:%M:%S"), *a, flush=True)


def night_active():
    n = settings["night"]
    if not n["enabled"]:
        return False
    m = time.localtime().tm_hour * 60 + time.localtime().tm_min
    f = int(n["from"][:2]) * 60 + int(n["from"][3:])
    t = int(n["to"][:2]) * 60 + int(n["to"][3:])
    return (f <= m < t) if f <= t else (m >= f or m < t)


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
    }


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
        await ws.send(json.dumps(msg))
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
        if msg.get("mode") not in ("text", "clock", "off"):
            return await ack(False, "unknown mode")
        state["mode"] = settings["mode"] = msg["mode"]
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
    elif cmd == "set_wifi":
        log("set_wifi:", msg.get("ssid"))
        await ack()
    elif cmd == "reboot":
        log("reboot requested (ignored)")
        await ack()
    elif cmd in ("stopwatch", "timer"):
        await ack(False, "not available in this firmware yet")
    else:
        await ack(False, "unknown command")


async def connection(ws):
    clients.add(ws)
    log(f"client connected ({len(clients)})")
    await send(ws, {"evt": "hello", "proto": 1, "fw": FW_VERSION, "name": settings["hostname"],
                    "max_items": MAX_ITEMS, "max_text": MAX_TEXT, "effects": EFFECTS,
                    "animations": ANIMATIONS, "modes": ["text", "clock", "off"]})
    await send(ws, {"evt": "settings", "settings": settings})
    await send(ws, state_msg())
    try:
        async for raw in ws:
            await handle(ws, raw)
    except ConnectionClosed:
        pass  # client went away without a close frame (app killed, Wi-Fi lost)
    finally:
        clients.discard(ws)
        if state["preview_client"] is ws and state["preview"] is not None:
            state["preview"] = None
            log("preview end (client left)")
        log(f"client disconnected ({len(clients)})")


def http(conn, request):
    """Serve /api/status like the device; let /ws through to the WebSocket."""
    if request.path == "/ws":
        return None
    if request.path == "/api/status":
        body = json.dumps({"name": settings["hostname"], "fw": FW_VERSION, "wifi": "online", "ip": "127.0.0.1"})
        return Response(HTTPStatus.OK, "OK", Headers({"Content-Type": "application/json"}), body.encode())
    return Response(HTTPStatus.NOT_FOUND, "Not Found", Headers(), b"not found")


async def ticker():
    """Advance the playlist index and broadcast state, like the device."""
    while True:
        await asyncio.sleep(5)
        items = state["playlist"]["items"]
        if state["mode"] == "text" and items and state["preview"] is None:
            state["index"] = (state["index"] + 1) % len(items)
        await broadcast(state_msg())


async def main():
    p = argparse.ArgumentParser(description="Fake Dot Matrix device")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8080)
    a = p.parse_args()
    log(f"fake device on ws://{a.host}:{a.port}/ws  ({len(EFFECTS)} effects, {len(ANIMATIONS)} animations)")
    async with serve(connection, a.host, a.port, process_request=http, max_size=2**20):
        await ticker()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
