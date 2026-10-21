"""WebSocket client for the display (protocol v1, docs/DESIGN.md §6).

- Keeps one connection open and reconnects on its own.
- `request()` sends a command and waits for its ack; `send()` doesn't wait.
- Listeners are called on every change (status, hello, state, settings).
"""
import asyncio
import json
import logging
from typing import Callable

import websockets

from .items import DEFAULT_ANIMATIONS, DEFAULT_EFFECTS

PROTO_VERSION = 1
log = logging.getLogger("device")


class DeviceError(Exception):
    pass


class Device:
    DISCONNECTED, CONNECTING, CONNECTED = "disconnected", "connecting", "connected"

    def __init__(self):
        self.host = ""
        self.status = self.DISCONNECTED
        self.error = ""
        self.hello: dict = {}
        self.state: dict = {}
        self.settings: dict = {}
        self._ws = None
        self._next_id = 1
        self._pending: dict[int, asyncio.Future] = {}
        self._listeners: list[Callable[[str], None]] = []
        self._task: asyncio.Task | None = None
        self._wake = asyncio.Event()

    # ------------------------------------------------------------- properties
    @property
    def connected(self) -> bool:
        return self.status == self.CONNECTED

    @property
    def effects(self) -> list[str]:
        return self.hello.get("effects") or DEFAULT_EFFECTS

    @property
    def animations(self) -> list[str]:
        return self.hello.get("animations") or DEFAULT_ANIMATIONS

    @property
    def max_items(self) -> int:
        return self.hello.get("max_items", 100)

    @property
    def max_text(self) -> int:
        return self.hello.get("max_text", 128)

    @property
    def proto_mismatch(self) -> bool:
        return bool(self.hello) and self.hello.get("proto") != PROTO_VERSION

    # -------------------------------------------------------------- listeners
    def listen(self, fn: Callable[[str], None]):
        self._listeners.append(fn)

    def _emit(self, what: str):
        for fn in list(self._listeners):
            try:
                fn(what)
            except Exception:  # noqa: BLE001 — a UI error must not kill the link
                log.exception("listener failed")

    def _set_status(self, status: str, error: str = ""):
        self.status, self.error = status, error
        self._emit("status")

    # ------------------------------------------------------------- connection
    def start(self, host: str):
        """Connect to host (name or IP, optional :port) and keep reconnecting."""
        self.host = host.strip()
        if self._task is None or self._task.done():
            self._task = asyncio.create_task(self._run())
        else:
            self._wake.set()  # drop the current link and use the new host
            if self._ws:
                asyncio.create_task(self._ws.close())

    async def stop(self):
        if self._task:
            self._task.cancel()
            self._task = None
        if self._ws:
            await self._ws.close()
        self._set_status(self.DISCONNECTED)

    async def _run(self):
        delay = 1
        while True:
            if not self.host:
                self._set_status(self.DISCONNECTED, "No device address yet")
                await self._wait(3600)
                continue
            self._set_status(self.CONNECTING)
            url = f"ws://{self.host}/ws"
            try:
                async with asyncio.timeout(6):
                    ws = await websockets.connect(url, max_size=2**20, ping_interval=10, ping_timeout=10,
                                                  open_timeout=5)
            except (OSError, asyncio.TimeoutError, websockets.WebSocketException) as ex:
                self._set_status(self.DISCONNECTED, _describe(ex))
                await self._wait(delay)
                delay = min(delay * 2, 10)
                continue

            delay = 1
            self._ws = ws
            self._set_status(self.CONNECTED)
            try:
                async for raw in ws:
                    self._dispatch(raw)
            except websockets.WebSocketException:
                pass
            finally:
                self._ws = None
                for fut in self._pending.values():
                    if not fut.done():
                        fut.set_exception(DeviceError("Connection lost"))
                self._pending.clear()
            self._set_status(self.DISCONNECTED, "Connection lost")
            await self._wait(1)

    async def _wait(self, seconds: float):
        self._wake.clear()
        try:
            await asyncio.wait_for(self._wake.wait(), seconds)
        except asyncio.TimeoutError:
            pass

    def retry_now(self):
        self._wake.set()

    # --------------------------------------------------------------- messages
    def _dispatch(self, raw):
        try:
            msg = json.loads(raw)
        except ValueError:
            return
        evt = msg.get("evt")
        if evt in ("ack", "playlist"):
            fut = self._pending.pop(msg.get("id"), None)
            if fut and not fut.done():
                fut.set_result(msg)
            return
        if evt == "hello":
            self.hello = msg
        elif evt == "state":
            self.state = msg
        elif evt == "settings":
            self.settings = msg.get("settings", {})
        else:
            return
        self._emit(evt)

    async def request(self, cmd: str, timeout: float = 5, **fields) -> dict:
        """Send a command and wait for the reply; raises DeviceError on failure."""
        if not self._ws:
            raise DeviceError("Not connected to the display")
        mid = self._next_id
        self._next_id += 1
        fut = asyncio.get_running_loop().create_future()
        self._pending[mid] = fut
        try:
            await self._ws.send(json.dumps({"id": mid, "cmd": cmd, **fields}))
            reply = await asyncio.wait_for(fut, timeout)
        except asyncio.TimeoutError:
            raise DeviceError("The display didn't answer") from None
        except websockets.WebSocketException:
            raise DeviceError("Connection lost") from None
        finally:
            self._pending.pop(mid, None)
        if reply.get("evt") == "ack" and not reply.get("ok"):
            raise DeviceError(reply.get("error") or "Command failed")
        return reply

    def send(self, cmd: str, **fields):
        """Fire and forget (live preview, sliders). Errors are ignored."""
        if self._ws:
            asyncio.create_task(self._quiet(cmd, fields))

    async def _quiet(self, cmd, fields):
        try:
            await self.request(cmd, **fields)
        except DeviceError:
            pass

    # ------------------------------------------------------------ convenience
    async def play_group(self, name: str, items: list[dict]):
        await self.request("set_playlist", name=name, items=items)
        if self.state.get("mode") != "text":
            await self.request("set_mode", mode="text")

    async def update_settings(self, **settings):
        await self.request("set_settings", settings=settings)


def _describe(ex: Exception) -> str:
    if isinstance(ex, asyncio.TimeoutError):
        return "No answer from the display"
    if isinstance(ex, OSError):
        if "Name or service not known" in str(ex) or "nodename nor servname" in str(ex) \
                or getattr(ex, "errno", None) in (-2, -3, 8):
            return "Name not found on this network"
        return "Can't reach the display"
    return "Connection failed"
