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
