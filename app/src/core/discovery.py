"""Find the display on the local network.

Order: the address that worked last time → dotmatrix.local (mDNS) → a scan of
the phone's /24 subnet for the device's /api/status page. The scan needs no
special Android permissions and takes about two seconds.
"""
import asyncio
import json
import socket

PORT = 80


def local_ip() -> str | None:
    """The phone's own Wi-Fi address (no packet is actually sent)."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("10.255.255.255", 1))
        return s.getsockname()[0]
    except OSError:
        return None
    finally:
        s.close()


async def probe(host: str, port: int = PORT, timeout: float = 0.6) -> dict | None:
    """GET /api/status; returns the device info if it's a Dot Matrix display."""
    try:
        reader, writer = await asyncio.wait_for(asyncio.open_connection(host, port), timeout)
    except (OSError, asyncio.TimeoutError):
        return None
    try:
        writer.write(f"GET /api/status HTTP/1.0\r\nHost: {host}\r\n\r\n".encode())
        await writer.drain()
        data = await asyncio.wait_for(reader.read(2048), timeout * 2)
        body = data.split(b"\r\n\r\n", 1)[-1]
        info = json.loads(body.decode("utf-8", "replace"))
        if isinstance(info, dict) and "fw" in info:
            return {**info, "host": host if port == PORT else f"{host}:{port}"}
    except (OSError, asyncio.TimeoutError, ValueError):
        return None
    finally:
        writer.close()
    return None


async def resolve(name: str, timeout: float = 2.5) -> str | None:
    loop = asyncio.get_running_loop()
    try:
        infos = await asyncio.wait_for(loop.getaddrinfo(name, PORT, family=socket.AF_INET), timeout)
        return infos[0][4][0] if infos else None
    except (OSError, asyncio.TimeoutError):
        return None


async def scan_subnet(progress=None) -> list[dict]:
    ip = local_ip()
    if not ip:
        return []
    prefix = ip.rsplit(".", 1)[0]
    sem = asyncio.Semaphore(48)
    found: list[dict] = []
    done = 0

    async def one(i):
        nonlocal done
        async with sem:
            info = await probe(f"{prefix}.{i}")
        done += 1
        if progress:
            progress(done / 254)
        if info:
            found.append(info)

    await asyncio.gather(*(one(i) for i in range(1, 255)))
    return sorted(found, key=lambda d: d["host"])


async def find(cached: str = "", name: str = "dotmatrix.local", progress=None) -> list[dict]:
    """Return every display found, best guess first."""
    if cached:
        info = await probe(cached.split(":")[0], int(cached.split(":")[1]) if ":" in cached else PORT)
        if info:
            return [info]
    ip = await resolve(name)
    if ip:
        info = await probe(ip)
        if info:
            return [info]
    return await scan_subnet(progress)
