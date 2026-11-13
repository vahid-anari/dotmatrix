"""The sensors' history. The display keeps two days of readings a minute and 30
days of quarter-hour averages (/api/log); the app keeps every quarter hour it has
ever fetched in its own file, so the history on the phone has no end."""
import asyncio
import csv
import io
import math
import time
import urllib.request
from pathlib import Path

COLUMNS = ("lux", "temp_c", "humidity", "pressure_hpa", "outdoor_c", "brightness")


def parse(text: str) -> list[dict]:
    """Rows of the display's machine CSV (`t` in Unix time); empty cells become None."""
    rows = []
    for r in csv.DictReader(io.StringIO(text)):
        try:
            row = {"t": int(r["t"]), "mode": r.get("mode", "")}
        except (KeyError, TypeError, ValueError):
            continue
        for k in COLUMNS:
            v = r.get(k)
            try:
                row[k] = float(v) if v not in (None, "") else None
            except ValueError:
                row[k] = None
        rows.append(row)
    return rows


def to_csv(rows: list[dict]) -> str:
    out = io.StringIO()
    w = csv.writer(out, lineterminator="\n")
    w.writerow(("t",) + COLUMNS + ("mode",))
    for r in rows:
        w.writerow([r["t"]] + ["" if r.get(k) is None else f"{r[k]:g}" for k in COLUMNS] + [r.get("mode", "")])
    return out.getvalue()


class Archive:
    """The quarter hours kept on the phone, oldest first, one per time."""

    def __init__(self, path: Path):
        self.path = path
        self.rows: list[dict] = []
        try:
            self.rows = parse(path.read_text())
        except OSError:
            pass

    @property
    def last(self) -> int:
        return self.rows[-1]["t"] if self.rows else 0

    def merge(self, rows: list[dict]) -> int:
        """Add rows, newer ones winning over older copies; returns how many are new."""
        by_t = {r["t"]: r for r in self.rows}
        new = sum(1 for r in rows if r["t"] not in by_t)
        by_t.update({r["t"]: r for r in rows})
        self.rows = [by_t[t] for t in sorted(by_t)]
        return new

    def save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(to_csv(self.rows))
        tmp.replace(self.path)


async def fetch(host: str, res: int, since: int = 0, timeout: float = 60) -> list[dict]:
    """The display's rows after `since`: res 1 = minutes (two days), 15 = quarters (30 days)."""
    url = f"http://{host}/api/log?res={res}&since={since}"

    def get():
        with urllib.request.urlopen(url, timeout=timeout) as r:
            return r.read().decode("utf-8", "replace")
    return parse(await asyncio.to_thread(get))


def window(rows: list[dict], start: float, end: float) -> list[dict]:
    return [r for r in rows if start <= r["t"] <= end]


def thin(rows: list[dict], key: str, n: int = 300) -> list[tuple[float, float]]:
    """(time, value) points for one column, averaged into at most n buckets so a
    month draws as fast as a day; missing values are left out."""
    pts = [(r["t"], r[key]) for r in rows if r.get(key) is not None]
    if len(pts) <= n:
        return pts
    t0, t1 = pts[0][0], pts[-1][0]
    size = (t1 - t0) / n or 1
    out, bucket, edge = [], [], t0 + size
    for t, v in pts:
        while t > edge and bucket:
            out.append((sum(b[0] for b in bucket) / len(bucket), sum(b[1] for b in bucket) / len(bucket)))
            bucket = []
            edge += size
        while t > edge:
            edge += size
        bucket.append((t, v))
    if bucket:
        out.append((sum(b[0] for b in bucket) / len(bucket), sum(b[1] for b in bucket) / len(bucket)))
    return out


def nice_range(values: list[float], pad: float = 0.08, min_span: float = 1.0) -> tuple[float, float]:
    """A y range around the values, at least min_span wide."""
    if not values:
        return 0.0, 1.0
    lo, hi = min(values), max(values)
    if hi - lo < min_span:
        mid = (hi + lo) / 2
        lo, hi = mid - min_span / 2, mid + min_span / 2
    p = (hi - lo) * pad
    return lo - p, hi + p


def light_y(lux: float) -> float:
    """Light is drawn on a log scale: 0, 1, 10, 100 lx equally apart."""
    return math.log10(1 + max(0.0, lux))


def ticks(start: float, end: float) -> list[tuple[float, str]]:
    """Time labels for the axis: hours for a day, days for longer."""
    span = end - start
    lt = time.localtime(start)
    if span <= 2 * 86400:
        step_h = 6
        first = time.mktime((lt.tm_year, lt.tm_mon, lt.tm_mday, (lt.tm_hour // step_h + 1) * step_h, 0, 0, 0, 0, -1))
        return [(t, time.strftime("%H:%M", time.localtime(t))) for t in _steps(first, end, step_h * 3600)]
    step_d = 1 if span <= 8 * 86400 else 7 if span <= 40 * 86400 else 30
    first = time.mktime((lt.tm_year, lt.tm_mon, lt.tm_mday + 1, 0, 0, 0, 0, 0, -1))
    fmt = "%a" if step_d == 1 else "%b %d"
    return [(t, time.strftime(fmt, time.localtime(t))) for t in _steps(first, end, step_d * 86400)]


def _steps(t: float, end: float, step: float):
    while t <= end:
        yield t
        if step < 86400:
            t += step
        else:  # through mktime, so days stay at midnight across daylight saving
            lt = time.localtime(t + step + 3600)
            t = time.mktime((lt.tm_year, lt.tm_mon, lt.tm_mday, 0, 0, 0, 0, 0, -1))


# ------------------------------------------------------------------- events
# What happened to the display (firmware 0.8.2): Wi-Fi lost and back, restarts.

RESTARTS = {1: "power on", 2: "firmware update", 3: "restarted from the app", 4: "new Wi-Fi network",
            5: "restarted by its software", 6: "stuck; restarted by the watchdog", 7: "crashed",
            8: "the power dipped", 9: "unknown reason"}
UNUSUAL_RESTARTS = {6, 7, 8}
# The Wi-Fi's own disconnect reasons (ESP-IDF wifi_err_reason_t), in plain words.
WIFI_REASONS = {2: "the router dropped it", 3: "the router dropped it", 4: "no traffic for too long",
                8: "the display disconnected itself", 15: "couldn't sign in", 200: "signal lost", 201: "network not found",
                202: "wrong password", 203: "couldn't join", 204: "couldn't sign in"}


def parse_events(text: str) -> list[dict]:
    out = []
    for r in csv.DictReader(io.StringIO(text)):
        try:
            out.append({"t": int(r["t"]), "kind": r["kind"], "reason": int(r["reason"] or 0),
                        "seconds": int(r["seconds"] or 0), "rssi": int(r.get("rssi") or 0)})
        except (KeyError, TypeError, ValueError):
            continue
    return out


def events_csv(events: list[dict]) -> str:
    return "t,kind,reason,seconds,rssi\n" + "".join(
        f"{e['t']},{e['kind']},{e['reason']},{e['seconds']},{e.get('rssi', 0)}\n" for e in events)


class EventArchive:
    """Every event the phone has fetched, oldest first, one per (time, kind)."""

    def __init__(self, path: Path):
        self.path = path
        try:
            self.events = parse_events(path.read_text())
        except OSError:
            self.events = []

    @property
    def last(self) -> int:
        return self.events[-1]["t"] if self.events else 0

    def merge(self, events: list[dict]) -> int:
        by = {(e["t"], e["kind"]): e for e in self.events}
        new = sum(1 for e in events if (e["t"], e["kind"]) not in by)
        by.update({(e["t"], e["kind"]): e for e in events})
        self.events = [by[k] for k in sorted(by)]
        return new

    def save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(events_csv(self.events))
        tmp.replace(self.path)


async def fetch_events(host: str, since: int = 0, timeout: float = 20) -> list[dict]:
    url = f"http://{host}/api/events?since={since}"

    def get():
        with urllib.request.urlopen(url, timeout=timeout) as r:
            return r.read().decode("utf-8", "replace")
    return parse_events(await asyncio.to_thread(get))


def duration(seconds: int) -> str:
    if seconds < 60:
        return f"{seconds} s"
    if seconds < 3600:
        return f"{seconds // 60} min" + (f" {seconds % 60} s" if seconds % 60 and seconds < 600 else "")
    return f"{seconds // 3600} h {seconds % 3600 // 60} min"


def describe(e: dict) -> tuple[str, bool]:
    """A line for an event (without its time), and whether it's out of the ordinary."""
    if e["kind"] == "wifi":
        why = WIFI_REASONS.get(e["reason"], f"reason {e['reason']}")
        if e.get("rssi", 0) < 0:  # firmware 0.8.3: the signal just before
            why += f" (signal was {e['rssi']} dBm)".replace("-", "−")
        return f"Wi-Fi lost for {duration(e['seconds'])} · {why}", False
    return f"Restarted · {RESTARTS.get(e['reason'], 'unknown reason')}", e["reason"] in UNUSUAL_RESTARTS


def summary(events: list[dict]) -> str:
    drops = [e for e in events if e["kind"] == "wifi"]
    restarts = [e for e in events if e["kind"] == "restart"]
    if not drops and not restarts:
        return "Nothing happened: the Wi-Fi stayed on, and the display didn't restart."
    parts = []
    if drops:
        n = len(drops)
        parts.append(f"the Wi-Fi dropped {n} time{'s' if n > 1 else ''} "
                     f"({duration(sum(e['seconds'] for e in drops))} in all)")
    else:
        parts.append("the Wi-Fi stayed on")
    n = len(restarts)
    parts.append(f"the display restarted {'once' if n == 1 else f'{n} times'}" if n else "no restarts")
    s = ", ".join(parts)
    return s[0].upper() + s[1:] + "."
