#!/usr/bin/env python3
"""
dm — talk to the Dot Matrix display from the command line (protocol v1).

    pip install websockets
    python tools/dm.py state
    python tools/dm.py mode clock
    python tools/dm.py playlist tools/examples/demo.json
    python tools/dm.py say "Hello world" --effect scroll_left
    python tools/dm.py preview '{"type":"animation","animation":"matrix_reveal","text":"Hi"}'
    python tools/dm.py settings '{"brightness":4,"clock":{"date_every":30}}'
    python tools/dm.py watch            # print every message from the device

Use --host to reach a device by IP, or set DM_HOST once per terminal
(default: dotmatrix.local).
"""
import argparse
import asyncio
import json
import os
import sys

try:
    import websockets
except ImportError:
    sys.exit("This tool needs the 'websockets' package:  pip install websockets")


async def run(host, commands, watch=False):
    """Send commands, print their replies, return when every command is answered."""
    url = f"ws://{host}/ws"
    try:
        ws = await asyncio.wait_for(websockets.connect(url, max_size=2**20), timeout=5)
    except Exception as ex:  # noqa: BLE001
        hint = ""
        if host.endswith(".local"):
            hint = "\nIf the name doesn't resolve, use the IP shown on the display: --host 192.168.x.x (or set DM_HOST)"
        sys.exit(f"Can't connect to {url}: {type(ex).__name__} {ex}{hint}")

    async with ws:
        pending = {}   # id -> command name, until acked
        wanted = set()  # events still to print: "state", "settings"
        for i, cmd in enumerate(commands, start=1):
            pending[i] = cmd["cmd"]
            if cmd["cmd"] == "get_state":
                wanted.add("state")
            if cmd["cmd"] == "get_settings":
                wanted.add("settings")
            await ws.send(json.dumps({"id": i, **cmd}))

        async for raw in ws:
            msg = json.loads(raw)
            evt = msg.get("evt")
            if watch:
                print(json.dumps(msg) if evt == "state" else json.dumps(msg, indent=2))
                continue
            if evt == "playlist" and msg.get("id") in pending:
                pending.pop(msg["id"])
                print(json.dumps({"name": msg["name"], "items": msg["items"]}, indent=2))
            elif evt == "ack" and msg.get("id") in pending:
                name = pending.pop(msg["id"])
                if not msg.get("ok"):
                    print(f"{name}: FAILED: {msg.get('error')}")
                    wanted.clear()
                elif name not in ("get_state", "get_settings"):
                    print(f"{name}: ok")
            elif evt in wanted and not pending:
                wanted.discard(evt)
                print(json.dumps(msg.get("settings", msg), indent=2))
            if not pending and not wanted:
                return


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--host", default=os.environ.get("DM_HOST", "dotmatrix.local"),
                   help="device name or IP (default: $DM_HOST or dotmatrix.local)")
    sub = p.add_subparsers(dest="action", required=True)
    sub.add_parser("state")
    sub.add_parser("watch")
    sub.add_parser("get-playlist")
    sub.add_parser("get-settings")
    sub.add_parser("reboot")
    sub.add_parser("preview-end")
    m = sub.add_parser("mode")
    m.add_argument("mode", choices=["text", "clock", "off"])
    pl = sub.add_parser("playlist", help="send a playlist JSON file {name, items}")
    pl.add_argument("file")
    s = sub.add_parser("say", help="play one text item as the whole playlist")
    s.add_argument("text")
    s.add_argument("--effect", default="scroll_left")
    pv = sub.add_parser("preview", help="show one item (JSON) until preview-end")
    pv.add_argument("item")
    st = sub.add_parser("settings", help="partial settings update (JSON)")
    st.add_argument("json")
    w = sub.add_parser("wifi", help="change Wi-Fi network (device reboots)")
    w.add_argument("ssid")
    w.add_argument("password")
    a = p.parse_args()

    if a.action == "state":
        cmds = [{"cmd": "get_state"}]
    elif a.action == "watch":
        asyncio.run(run(a.host, [], watch=True))
        return
    elif a.action == "get-playlist":
        cmds = [{"cmd": "get_playlist"}]
    elif a.action == "get-settings":
        cmds = [{"cmd": "get_settings"}]
    elif a.action == "reboot":
        cmds = [{"cmd": "reboot"}]
    elif a.action == "preview-end":
        cmds = [{"cmd": "preview_end"}]
    elif a.action == "mode":
        cmds = [{"cmd": "set_mode", "mode": a.mode}]
    elif a.action == "playlist":
        with open(a.file, encoding="utf-8") as f:
            data = json.load(f)
        cmds = [{"cmd": "set_playlist", "name": data.get("name", ""), "items": data["items"]},
                {"cmd": "set_mode", "mode": "text"}]
    elif a.action == "say":
        item = {"text": a.text, "effect_in": a.effect, "effect_out": a.effect, "pause": 1000}
        cmds = [{"cmd": "set_playlist", "name": "say", "items": [item]}, {"cmd": "set_mode", "mode": "text"}]
    elif a.action == "preview":
        cmds = [{"cmd": "preview", "item": json.loads(a.item)}]
    elif a.action == "settings":
        cmds = [{"cmd": "set_settings", "settings": json.loads(a.json)}]
    elif a.action == "wifi":
        cmds = [{"cmd": "set_wifi", "ssid": a.ssid, "password": a.password}]

    asyncio.run(run(a.host, cmds))


if __name__ == "__main__":
    main()
