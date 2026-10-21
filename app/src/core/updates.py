"""Updates from GitHub Releases: check, download, and install firmware over Wi-Fi.

Each release (tag vX.Y.Z) carries the APK and the firmware, built by CI with
that same version, so one "latest release" answers both "is there a newer app?"
and "is there newer firmware?".
"""
import asyncio
import http.client
import json
import os
import re
import ssl
import urllib.error
import urllib.request
import uuid
from dataclasses import dataclass, field

def _ssl_context() -> ssl.SSLContext:
    # SSL_CERT_FILE wins when set (corporate proxies, tests). Otherwise certifi,
    # because Python on Android often has no CA store of its own.
    if os.getenv("SSL_CERT_FILE"):
        return ssl.create_default_context(cafile=os.environ["SSL_CERT_FILE"])
    try:
        import certifi

        return ssl.create_default_context(cafile=certifi.where())
    except ImportError:  # pragma: no cover
        return ssl.create_default_context()


_SSL = _ssl_context()

REPO = "vahid-anari/dotmatrix"
API = f"https://api.github.com/repos/{REPO}/releases/latest"
FIRMWARE_ASSET = "dotmatrix-firmware.bin"


@dataclass
class Release:
    version: str
    page: str
    apk_url: str | None = None
    firmware_url: str | None = None
    firmware_size: int = 0
    notes: str = ""
    assets: dict = field(default_factory=dict)


def parse_version(v: str) -> tuple:
    """'0.2.0' → (0, 2, 0, 1); '0.2.0-dev' → (0, 2, 0, 0), so a dev build sorts
    just below its release. Anything unparsable sorts lowest."""
    m = re.match(r"v?(\d+)\.(\d+)\.(\d+)(.*)", v or "")
    if not m:
        return (-1,)
    return (int(m[1]), int(m[2]), int(m[3]), 0 if m[4] else 1)


def is_newer(candidate: str, current: str) -> bool:
    return parse_version(candidate) > parse_version(current)


def _get(url: str, timeout: float = 15) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "dotmatrix-app",
                                               "Accept": "application/vnd.github+json"})
    with urllib.request.urlopen(req, timeout=timeout, context=_SSL) as r:
        return r.read()


class NoReleases(Exception):
    pass


async def latest_release() -> Release:
    try:
        data = json.loads(await asyncio.to_thread(_get, API))
    except urllib.error.HTTPError as ex:
        if ex.code == 404:  # the repository has no releases yet
            raise NoReleases() from None
        raise
    assets = {a["name"]: a for a in data.get("assets", [])}
    apk = next((a for n, a in assets.items() if n.endswith(".apk")), None)
    fw = assets.get(FIRMWARE_ASSET)
    return Release(
        version=data.get("tag_name", "").lstrip("v"),
        page=data.get("html_url", f"https://github.com/{REPO}/releases"),
        apk_url=apk["browser_download_url"] if apk else None,
        firmware_url=fw["browser_download_url"] if fw else None,
        firmware_size=fw.get("size", 0) if fw else 0,
        notes=data.get("body", ""),
        assets={n: a["browser_download_url"] for n, a in assets.items()},
    )


async def download(url: str, progress=None) -> bytes:
    """Download with progress(fraction) callbacks on the event loop."""
    loop = asyncio.get_running_loop()

    def work():
        req = urllib.request.Request(url, headers={"User-Agent": "dotmatrix-app"})
        with urllib.request.urlopen(req, timeout=30, context=_SSL) as r:
            total = int(r.headers.get("Content-Length") or 0)
            chunks, got = [], 0
            while chunk := r.read(32 * 1024):
                chunks.append(chunk)
                got += len(chunk)
                if progress and total:
                    loop.call_soon_threadsafe(progress, got / total)
            return b"".join(chunks)

    return await asyncio.to_thread(work)


ESP32C3_CHIP_ID = 5
APP_DESC_MAGIC = bytes.fromhex("3254cdab")  # esp_app_desc_t, right after the first segment header


def check_firmware_image(data: bytes) -> str | None:
    """Make sure this is an app image for the ESP32-C3 before sending it.

    A merged "full" image (bootloader + partitions + app) also starts with 0xE9,
    but has no app description at 0x20, so it's rejected here."""
    if len(data) < 64 * 1024:
        return "The firmware file is too small."
    if data[0] != 0xE9:
        return "That isn't an ESP32 firmware file."
    if int.from_bytes(data[12:14], "little") != ESP32C3_CHIP_ID:
        return "That firmware is for a different ESP32 chip."
    if data[0x20:0x24] != APP_DESC_MAGIC:
        return "That's a full flash image, not an app update."
    return None


async def upload_firmware(host: str, data: bytes, progress=None) -> None:
    """POST the image to the display's /update, as multipart like a browser."""
    loop = asyncio.get_running_loop()
    hostname, _, port = host.partition(":")
    boundary = uuid.uuid4().hex
    head = (f"--{boundary}\r\nContent-Disposition: form-data; name=\"firmware\"; "
            f"filename=\"firmware.bin\"\r\nContent-Type: application/octet-stream\r\n\r\n").encode()
    tail = f"\r\n--{boundary}--\r\n".encode()

    def work():
        conn = http.client.HTTPConnection(hostname, int(port or 80), timeout=60)
        try:
            conn.putrequest("POST", "/update")
            conn.putheader("Content-Type", f"multipart/form-data; boundary={boundary}")
            conn.putheader("Content-Length", str(len(head) + len(data) + len(tail)))
            conn.endheaders()
            conn.send(head)
            step = 8 * 1024
            for i in range(0, len(data), step):
                conn.send(data[i:i + step])
                if progress:
                    loop.call_soon_threadsafe(progress, min(1.0, (i + step) / len(data)))
            conn.send(tail)
            resp = conn.getresponse()
            body = resp.read()
            if resp.status != 200 or b'"ok":true' not in body.replace(b" ", b""):
                raise RuntimeError("The display rejected the firmware.")
        finally:
            conn.close()

    await asyncio.to_thread(work)
