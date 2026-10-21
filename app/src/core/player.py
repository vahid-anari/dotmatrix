"""Plays an item over time, the way the display does, for the editor's preview.

`Player(item).frame(t_ms)` gives what the 64×8 display shows t ms into the
item (looping): (64 column bytes, brightness 0..1).

What is copied from the firmware, and how closely:
- our own effects (lasers), the overlays and the animations: the same code,
  ported line by line (random ones look alike, not identical);
- Parola's print, scroll, wipe, open/close, slice and sprite effects: the same
  movement, step for step;
- Parola's other effects (mesh, fade, dissolve, ...): close likenesses.
"""
import random

from . import sprites
from .preview import HEIGHT, WIDTH, layout

Frame = list[int]
FULL = 0xFF
FRAMES_CAP = 4000  # one effect never needs more frames than this


def _place(cols: list[int], x: int) -> Frame:
    f = [0] * WIDTH
    for i, c in enumerate(cols):
        if 0 <= x + i < WIDTH:
            f[x + i] = c
    return f


def _lit(f: Frame) -> int:
    return sum(bin(c).count("1") for c in f)


# ====================================================== Parola-like effects

def rest_x(name_in: str, cols: list[int], x0: int) -> int:
    """Where the text rests after coming in. Text wider than the display rests
    at the left edge, except after scrolling in from the right: Parola stops
    once the last column is in (same rule as TextMode.cpp)."""
    return WIDTH - len(cols) if len(cols) > WIDTH and name_in == "scroll_left" else x0


def _parola_in(name: str, cols: list[int], x0: int, rng: random.Random) -> list[Frame]:
    """Frames of an entry effect, ending with the text at rest."""
    w = len(cols)
    base = _place(cols, x0)
    if name in ("print", "no_effect"):
        return [base]
    if name == "scroll_left":  # enters from the right edge
        return [_place(cols, x) for x in range(WIDTH - 1, rest_x(name, cols, x0) - 1, -1)]
    if name == "scroll_right":  # enters from the left edge
        return [_place(cols, x) for x in range(-w + 1, x0 + 1)]
    if name == "scroll_up":
        return [[(c << r) & FULL for c in base] for r in range(7, -1, -1)]
    if name == "scroll_down":
        return [[c >> r for c in base] for r in range(7, -1, -1)]
    if name.startswith("scroll_") and "_" in name[7:]:  # diagonals, e.g. scroll_up_left
        up, left = "up" in name, "left" in name
        out = []
        for k in range(7, -1, -1):
            f = _place(cols, x0 + (k if left else -k))
            out.append([((c << k) if up else (c >> k)) & FULL for c in f])
        return out
    if name in ("wipe", "wipe_cursor"):
        out = []
        for k in range(w + 1):
            f = [c if x < x0 + k else 0 for x, c in enumerate(base)]
            if name == "wipe_cursor" and k < w and 0 <= x0 + k < WIDTH:
                f[x0 + k] = FULL
            out.append(f)
        return out
    if name.startswith(("opening", "closing")):
        mid, out = WIDTH // 2, []
        for k in range(mid + 1):
            if name.startswith("opening"):
                f = [c if mid - k <= x < mid + k else 0 for x, c in enumerate(base)]
                bars = (mid - k - 1, mid + k)
            else:
                f = [c if x < k or x >= WIDTH - k else 0 for x, c in enumerate(base)]
                bars = (k, WIDTH - 1 - k)
            if name.endswith("_cursor") and k < mid:
                for b in bars:
                    if 0 <= b < WIDTH:
                        f[b] = FULL
            out.append(f)
        return out
    if name == "slice":  # each column flies in from the right, left-most first
        out, f = [], [0] * WIDTH
        for x, c in enumerate(base):
            if not c:
                continue
            for p in range(WIDTH - 1, x - 1, -1):
                g = f[:]
                g[p] = c
                out.append(g)
            f[x] = c
        return out or [base]
    if name.startswith("sprite_"):
        return _sprite(name[7:], base, True)
    if name in ("grow_up", "grow_down"):
        out = []
        for k in range(1, 9):
            mask = (FULL << (8 - k)) & FULL if name == "grow_up" else FULL >> (8 - k)
            out.append([c & mask for c in base])
        return out
    if name == "mesh":  # odd columns from above, even ones from below
        return [[((c >> r) if x % 2 else (c << r)) & FULL for x, c in enumerate(base)] for r in range(7, -1, -1)]
    if name in ("dissolve", "random"):
        pixels = [(x, y) for x in range(WIDTH) for y in range(HEIGHT) if base[x] >> y & 1]
        rng.shuffle(pixels)
        out, f, n = [], [0] * WIDTH, max(1, len(pixels) // 16)
        for i, (x, y) in enumerate(pixels):
            f[x] |= 1 << y
            if i % n == n - 1:
                out.append(f[:])
        return out + [base]
    if name == "blinds":
        bars = [[FULL if x % 4 < k else 0 for x in range(WIDTH)] for k in range(1, 5)]
        shown = [[c if x % 4 >= k else FULL for x, c in enumerate(base)] for k in range(3, -1, -1)]
        return bars + shown
    if name.startswith("scan_horiz"):
        return [[c if x == k else 0 for x, c in enumerate(base)] for k in range(WIDTH)] + [base]
    if name.startswith("scan_vert"):
        return [[c & (1 << k) for c in base] for k in range(HEIGHT)] + [base]
    return [base]  # fade is done with brightness, see Player


def _parola_out(name: str, cols: list[int], x0: int, rng: random.Random) -> list[Frame]:
    """Frames of an exit effect, ending with an empty display."""
    w = len(cols)
    base = _place(cols, x0)
    blank = [0] * WIDTH
    if name == "print":
        return [blank]
    if name == "scroll_left":  # x0: where the text is now
        return [_place(cols, x) for x in range(x0 - 1, -w - 1, -1)]
    if name == "scroll_right":
        return [_place(cols, x) for x in range(x0 + 1, WIDTH + 1)]
    if name == "scroll_up":
        return [[c >> r for c in base] for r in range(1, 9)]
    if name == "scroll_down":
        return [[(c << r) & FULL for c in base] for r in range(1, 9)]
    if name.startswith("scroll_") and "_" in name[7:]:
        up, left = "up" in name, "left" in name
        out = []
        for k in range(1, 9):
            f = _place(cols, x0 + (-k if left else k))
            out.append([((c >> k) if up else (c << k)) & FULL for c in f])
        return out
    if name in ("wipe", "wipe_cursor"):
        out = []
        for k in range(w + 1):
            f = [0 if x < x0 + k else c for x, c in enumerate(base)]
            if name == "wipe_cursor" and k < w and 0 <= x0 + k < WIDTH:
                f[x0 + k] = FULL
            out.append(f)
        return out
    if name.startswith(("opening", "closing")):
        return list(reversed(_parola_in("closing" + name[7:] if name.startswith("opening") else
                                        "opening" + name[7:], cols, x0, rng)))[1:] + [blank]
    if name == "slice":  # each column flies off to the left, left-most first
        out, f = [], base[:]
        for x, c in enumerate(base):
            if not c:
                continue
            f[x] = 0
            for p in range(x, -1, -1):
                g = f[:]
                g[p] = c
                out.append(g)
        return out + [blank]
    if name.startswith("sprite_"):
        return _sprite(name[7:], base, False)
    if name in ("grow_up", "grow_down", "mesh", "dissolve", "random", "blinds") or name.startswith("scan_"):
        frames = _parola_in(name, cols, x0, rng)
        return list(reversed(frames))[1:] + [blank]
    return [blank]


def _sprite(name: str, base: Frame, entering: bool) -> list[Frame]:
    """Parola's sprite effect: the sprite runs across, the text appears
    behind it (in) or is eaten up by it (out)."""
    width, nframes, data = sprites.SPRITES.get(name, sprites.SPRITES["pacman"])
    out = []
    for step in range(WIDTH + width + 1):
        frame_no = step % nframes
        col = data[frame_no * width:(frame_no + 1) * width]
        if entering:  # moves left to right, the text is to its left
            head = step
            f = [c if x <= head - width else 0 for x, c in enumerate(base)]
            for i in range(width):
                if 0 <= head - i < WIDTH:
                    f[head - i] = col[i]
        else:  # moves right to left, front edge on the left, text left of it remains
            head = WIDTH - 1 - step
            f = [c if x < head else 0 for x, c in enumerate(base)]
            for i in range(width):
                if 0 <= head + i < WIDTH:
                    f[head + i] = col[i]
        out.append(f)
    return out


# ================================================== Lasers (TextFx.cpp)

WRITE_STEPS, CUT_STEPS = 64, 80
BEAM_X, BEAM_Y = 0, HEIGHT - 1


def _get(f: Frame, x: int, y: int) -> bool:
    return 0 <= x < WIDTH and 0 <= y < HEIGHT and bool(f[x] >> y & 1)


def _set(f: Frame, x: int, y: int, on: bool = True) -> None:
    if 0 <= x < WIDTH and 0 <= y < HEIGHT:
        if on:
            f[x] |= 1 << y
        else:
            f[x] &= ~(1 << y) & FULL


def _order_columns(text: Frame) -> list[tuple[int, int]]:
    return [(x, y) for x in range(WIDTH) for y in range(HEIGHT) if text[x] >> y & 1]


def _order_strokes(text: Frame) -> list[tuple[int, int]]:
    dirs = [(0, 1), (1, 1), (1, 0), (1, -1), (0, -1), (-1, -1), (-1, 0), (-1, 1)]
    seen, order = set(), []
    for sx in range(WIDTH):
        for sy in range(HEIGHT):
            if not _get(text, sx, sy) or (sx, sy) in seen:
                continue
            stack = [(sx, sy)]
            seen.add((sx, sy))
            order.append((sx, sy))
            while stack:
                x, y = stack[-1]
                for dx, dy in dirs:
                    n = (x + dx, y + dy)
                    if _get(text, *n) and n not in seen:
                        seen.add(n)
                        stack.append(n)
                        order.append(n)
                        break
                else:
                    stack.pop()
    return order


def _line(f: Frame, x0: int, y0: int, x1: int, y1: int) -> None:
    dx, sx = abs(x1 - x0), 1 if x0 < x1 else -1
    dy, sy = -abs(y1 - y0), 1 if y0 < y1 else -1
    err = dx + dy
    while True:
        _set(f, x0, y0)
        if x0 == x1 and y0 == y1:
            break
        e2 = 2 * err
        if e2 >= dy:
            err += dy
            x0 += sx
        if e2 <= dx:
            err += dx
            y0 += sy


def _laser(kind: str, text: Frame, entering: bool, rng: random.Random) -> list[Frame]:
    """Frames of a laser effect; the last frame is the text (in) or empty (out)."""
    out = []
    if kind == "laser_scan":
        for s in range(WIDTH + 2):
            bx = s - 1
            f = [c if (x < bx if entering else x > bx) else 0 for x, c in enumerate(text)]
            if 0 <= bx < WIDTH:
                f[bx] = FULL
            spark = bx - 1 if entering else bx + 1
            if 0 <= spark < WIDTH:
                for y in range(HEIGHT):
                    if rng.randrange(100) < 30:
                        _set(f, spark, y, not _get(f, spark, y))
            out.append(f)
    else:
        order = _order_columns(text) if kind == "laser_write" else _order_strokes(text)
        n = len(order)
        target = CUT_STEPS if kind == "laser_cut" else WRITE_STEPS
        per = -(-n // target) if n > target else 1
        for s in range(-(-n // per) if n else 0):
            done = min((s + 1) * per, n)
            if entering:
                f = [0] * WIDTH
                for x, y in order[:done]:
                    _set(f, x, y)
            else:
                f = text[:]
                for x, y in order[:done]:
                    _set(f, x, y, False)
            x, y = order[done - 1]
            if kind == "laser_write":
                _line(f, BEAM_X, BEAM_Y, x, y)
            else:
                _set(f, x, y)
                if rng.randrange(100) < 60:
                    _set(f, x + rng.randrange(-1, 2), y + rng.randrange(-1, 2))
            out.append(f)
    out.append(text[:] if entering else [0] * WIDTH)
    return out


# ================================================= Overlays (Overlay.cpp)

WAVE_HOP_MS, WAVE_REST_MS, PULSE_MS, BORDER_LEN = 110, 700, 1600, 6


def _letters(text: Frame) -> list[tuple[int, int]]:
    out, x = [], 0
    while x < WIDTH:
        if not text[x]:
            x += 1
            continue
        start = x
        while x < WIDTH and text[x]:
            x += 1
        out.append((start, x))
    return out


def _edge_point(p: int) -> tuple[int, int]:
    if p < WIDTH:
        return p, 0
    p -= WIDTH
    if p < HEIGHT - 1:
        return WIDTH - 1, p + 1
    p -= HEIGHT - 1
    if p < WIDTH - 1:
        return WIDTH - 2 - p, HEIGHT - 1
    p -= WIDTH - 1
    return 0, HEIGHT - 2 - p


def overlay_frame(kind: str, text: Frame, t: int, rng: random.Random) -> tuple[Frame, float]:
    f = text[:]
    level = 1.0
    if kind == "wave":
        letters = _letters(text)
        if letters:
            cycle = len(letters) * WAVE_HOP_MS + WAVE_REST_MS
            i = (t % cycle) // WAVE_HOP_MS
            if i < len(letters):
                for x in range(*letters[i]):
                    f[x] = (text[x] << 1) & FULL
    elif kind == "sparkle":
        for _ in range(5):
            _set(f, rng.randrange(WIDTH), rng.randrange(HEIGHT))
        if rng.randrange(100) < 25:
            x = rng.randrange(WIDTH)
            if f[x]:
                f[x] &= ~(1 << rng.randrange(HEIGHT)) & FULL
    elif kind == "pulse":
        p = t % PULSE_MS
        tri = p if p < PULSE_MS // 2 else PULSE_MS - p
        level = 1 - 0.75 * tri / (PULSE_MS / 2)
    elif kind == "border":
        perimeter = 2 * (WIDTH + HEIGHT) - 4
        head = (t // 15) % perimeter
        for i in range(BORDER_LEN):
            _set(f, *_edge_point((head - i) % perimeter))
    return f, level


# ============================================ Animations (animations/*.cpp)

class _Anim:
    frame_ms = 50

    def __init__(self, item: dict, rng: random.Random):
        self.item, self.rng = item, rng
        self.params = item.get("params") or {}

    def step(self, t: int) -> Frame:  # pragma: no cover - overridden
        return [0] * WIDTH


class _MatrixRain(_Anim):
    frame_ms = 45

    def __init__(self, item, rng, reveal: bool):
        super().__init__(item, rng)
        self.reveal = reveal
        self.density = min(self.params.get("density") or 18, 40)
        self.duration = item.get("duration", 10000)
        self.target = [0] * WIDTH
        if reveal:
            cols, x0 = layout(item.get("text", ""), item.get("align", "center"))
            self.target = _place(cols, x0)
        self.shown = [0] * WIDTH
        self.drops = [self._spawn(False) for _ in range(self.density)]
        for d in self.drops:
            d[1] = -rng.randrange(0, 16)

    def _spawn(self, prefer_hidden: bool) -> list[int]:
        x = self.rng.randrange(WIDTH)
        if prefer_hidden:
            for _ in range(8):
                c = self.rng.randrange(WIDTH)
                if self.target[c] & ~self.shown[c]:
                    x = c
                    break
        # x, y, len, period, tick
        return [x, -self.rng.randrange(0, 4), self.rng.randrange(2, 6), self.rng.randrange(1, 4), 0]

    def step(self, t):
        raining = not self.reveal or t < self.duration * 3 // 4
        eager = self.reveal and t > self.duration * 3 // 5
        f = self.shown[:]
        active = False
        for i, d in enumerate(self.drops):
            if d is None:
                if raining:
                    self.drops[i] = self._spawn(self.reveal)
                continue
            active = True
            d[4] += 1
            if d[4] >= d[3]:
                d[4] = 0
                d[1] += 1
            x, y, length = d[0], d[1], d[2]
            for k in range(length + 1):
                if 0 <= y - k < HEIGHT and (k == 0 or self.rng.randrange(100) < 85 - k * 15):
                    f[x] |= 1 << (y - k)
            if self.reveal and 0 <= y < HEIGHT and self.target[x] >> y & 1 and \
                    (eager or self.rng.randrange(100) < 35):
                self.shown[x] |= 1 << y
            if y - length >= HEIGHT:
                self.drops[i] = None
        if self.reveal and not raining and not active:
            self.shown = self.target[:]
            f = self.shown[:]
        return f


class _Starfield(_Anim):
    frame_ms = 40

    def __init__(self, item, rng):
        super().__init__(item, rng)
        self.stars = [self._spawn(True) for _ in range(min(self.params.get("density") or 24, 48))]

    def _spawn(self, anywhere):
        while True:
            dx, dy = self.rng.randrange(-160, 161), self.rng.randrange(-40, 41)
            if abs(dx) >= 24 or abs(dy) >= 12:
                break
        s = [WIDTH * 128, HEIGHT * 128, dx, dy]
        for _ in range(self.rng.randrange(0, 40) if anywhere else 0):
            s[0] += int(dx / 4)
            s[1] += int(dy / 4)
        return s

    def step(self, t):
        f = [0] * WIDTH
        for i, s in enumerate(self.stars):
            px, py = s[0] // 256, s[1] // 256
            dist = abs(px - WIDTH // 2) + 4 * abs(py - HEIGHT // 2)
            k = 4 + dist // 3
            s[0] += int(s[2] * k / 16)
            s[1] += int(s[3] * k / 16)
            nx, ny = s[0] // 256, s[1] // 256
            if s[0] < 0 or nx >= WIDTH or s[1] < 0 or ny >= HEIGHT:
                self.stars[i] = self._spawn(False)
                continue
            _set(f, nx, ny)
            if dist > 20:
                _set(f, px, py)
        return f


class _Life(_Anim):
    frame_ms = 140

    def __init__(self, item, rng):
        super().__init__(item, rng)
        self.density = max(5, min(self.params.get("density") or 35, 60))
        self._seed()

    def _seed(self):
        self.cells = [sum(1 << y for y in range(HEIGHT) if self.rng.randrange(100) < self.density)
                      for _ in range(WIDTH)]
        self.prev, self.prev2, self.gen, self.fade = [0] * WIDTH, [0] * WIDTH, 0, 0

    def step(self, t):
        if self.fade:
            self.fade -= 1
            if self.fade == 0:
                self._seed()
            return [0] * WIDTH if (self.fade // 2) % 2 else self.cells[:]
        nxt = [0] * WIDTH
        for x in range(WIDTH):
            for y in range(HEIGHT):
                n = sum(1 for dx in (-1, 0, 1) for dy in (-1, 0, 1) if (dx or dy) and
                        self.cells[(x + dx) % WIDTH] >> ((y + dy) % HEIGHT) & 1)
                alive = self.cells[x] >> y & 1
                if (alive and n in (2, 3)) or (not alive and n == 3):
                    nxt[x] |= 1 << y
        settled = not any(nxt) or nxt in (self.cells, self.prev, self.prev2)
        self.prev2, self.prev, self.cells = self.prev, self.cells, nxt
        self.gen += 1
        if settled or self.gen > 400:
            self.fade = 12
        return self.cells[:]


class _Fireworks(_Anim):
    frame_ms = 35

    def __init__(self, item, rng):
        super().__init__(item, rng)
        self.max_rockets = max(1, min(self.params.get("density") or 2, 4))
        self.p: list[dict] = []
        self.wait = 0

    def step(self, t):
        f = [0] * WIDTH
        rng = self.rng
        if self.wait:
            self.wait -= 1
        if not self.wait and sum(p["rocket"] for p in self.p) < self.max_rockets:
            self.p.append(dict(rocket=True, x=rng.randrange(6, WIDTH - 6) * 256, y=(HEIGHT - 1) * 256,
                               dx=rng.randrange(-20, 21), dy=-rng.randrange(150, 200), life=60))
            self.wait = rng.randrange(6, 28)
        born = []
        for p in self.p:
            p["x"] += p["dx"]
            p["y"] += p["dy"]
            x, y = p["x"] // 256, p["y"] // 256
            if p["rocket"]:
                p["dy"] += 6
                if p["dy"] > -30 or y <= 1:
                    p["life"] = 0
                    free = 64 - len(self.p) - len(born)  # the display has room for 64
                    born += [dict(rocket=False, x=p["x"], y=p["y"], dx=rng.randrange(-240, 241),
                                  dy=rng.randrange(-140, 81), life=rng.randrange(14, 28))
                             for _ in range(min(rng.randrange(10, 16), max(free, 0)))]
                    continue
                _set(f, x, y)
                if rng.randrange(100) < 70:
                    _set(f, x, y + 1)
            else:
                p["dy"] += 5
                p["dx"] -= int(p["dx"] / 12)
                p["life"] -= 1
                if p["x"] < 0 or x >= WIDTH or y >= HEIGHT:
                    p["life"] = 0
                    continue
                if p["life"] > 6 or rng.randrange(100) < 50:
                    _set(f, x, y)
            p["life"] -= 1
        self.p = [p for p in self.p if p["life"] > 0] + born
        return f


class _Equalizer(_Anim):
    frame_ms = 60
    BARS = WIDTH // 4

    def __init__(self, item, rng):
        super().__init__(item, rng)
        self.level, self.target = [0] * self.BARS, [0] * self.BARS
        self.peak, self.hold = [0] * self.BARS, [0] * self.BARS

    def step(self, t):
        f = [0] * WIDTH
        for b in range(self.BARS):
            if self.rng.randrange(100) < 30:
                top = HEIGHT * 16 - b * 2
                self.target[b] = self.rng.randrange(top // 5, top)
            if self.level[b] < self.target[b]:
                self.level[b] += (self.target[b] - self.level[b] + 1) // 2
            else:
                self.level[b] = max(0, self.level[b] - 10)
            if self.level[b] >= self.target[b]:
                self.target[b] = 0
            h = self.level[b] // 16
            if h > self.peak[b]:
                self.peak[b], self.hold[b] = h, 8
            elif self.hold[b]:
                self.hold[b] -= 1
            elif self.peak[b]:
                self.peak[b] -= 1
                self.hold[b] = 1
            bits = (FULL << (HEIGHT - h)) & FULL if h else 0
            if self.peak[b] > h:
                bits |= 1 << (HEIGHT - self.peak[b])
            for i in range(3):
                f[b * 4 + i] = bits
        return f


class _Snake(_Anim):
    frame_ms = 70
    MAX_LEN = 48
    DIRS = [(1, 0), (0, 1), (-1, 0), (0, -1)]

    def __init__(self, item, rng):
        super().__init__(item, rng)
        self.tick = 0
        self._reset()

    def _reset(self):
        self.body = [(20 - i, 3) for i in range(4)]
        self.dir, self.dead = 0, 0
        self._food()

    def _food(self):
        while True:
            self.food = (self.rng.randrange(WIDTH), self.rng.randrange(HEIGHT))
            if self.food not in self.body:
                return

    def _room(self, start):
        seen = set(self.body[:-1]) | {start}
        queue = [start]
        for x, y in queue:
            for dx, dy in self.DIRS:
                n = (x + dx, y + dy)
                if 0 <= n[0] < WIDTH and 0 <= n[1] < HEIGHT and n not in seen:
                    seen.add(n)
                    queue.append(n)
        return len(queue)

    def step(self, t):
        self.tick += 1
        if self.dead:
            self.dead -= 1
            if not self.dead:
                self._reset()
        else:
            (hx, hy), (fx, fy) = self.body[0], self.food
            best, best_score = None, 0
            for d, (dx, dy) in enumerate(self.DIRS):
                if d == (self.dir + 2) % 4:
                    continue
                n = (hx + dx, hy + dy)
                if not (0 <= n[0] < WIDTH and 0 <= n[1] < HEIGHT) or n in self.body[:-1]:
                    continue
                space = self._room(n)
                score = -(abs(n[0] - fx) + abs(n[1] - fy)) * 4
                if space < len(self.body) + 2:
                    score -= 1000 - space
                if d == self.dir:
                    score += 1
                if best is None or score > best_score:
                    best, best_score = d, score
            if best is None:
                self.dead = 14
            else:
                self.dir = best
                dx, dy = self.DIRS[best]
                n = (hx + dx, hy + dy)
                eats = n == self.food
                self.body.insert(0, n)
                if not eats or len(self.body) > self.MAX_LEN:
                    self.body.pop()
                if eats:
                    if len(self.body) >= self.MAX_LEN:
                        self.dead = 14
                    else:
                        self._food()
        f = [0] * WIDTH
        if not self.dead or (self.dead // 2) % 2:
            for x, y in self.body:
                _set(f, x, y)
        if not self.dead and self.tick % 4 < 3:
            _set(f, *self.food)
        return f


class _SpriteRun(_Anim):
    frame_ms = 50

    def __init__(self, item, rng):
        super().__init__(item, rng)
        self.width, self.frames, self.data = sprites.SPRITES.get(self.params.get("sprite", "pacman"),
                                                                 sprites.SPRITES["pacman"])
        self.x, self.frame_no = -1, 0

    def step(self, t):
        f = [0] * WIDTH
        for i in range(self.width):
            if 0 <= self.x - i < WIDTH:
                f[self.x - i] = self.data[self.frame_no * self.width + i]
        self.frame_no = (self.frame_no + 1) % self.frames
        self.x += 1
        if self.x - self.width >= WIDTH + 8:
            self.x = -1
        return f


ANIMATIONS = {
    "matrix_rain": lambda item, rng: _MatrixRain(item, rng, False),
    "matrix_reveal": lambda item, rng: _MatrixRain(item, rng, True),
    "starfield": _Starfield, "life": _Life, "fireworks": _Fireworks,
    "equalizer": _Equalizer, "snake": _Snake, "sprite_run": _SpriteRun,
}


# ================================================================= player

LASERS = ("laser_write", "laser_scan", "laser_cut")
# Parola effects whose look the preview copies step for step.
EXACT = {"no_effect", "print", "scroll_left", "scroll_right", "scroll_up", "scroll_down", "wipe",
         "wipe_cursor", "opening", "opening_cursor", "closing", "closing_cursor", "slice", *LASERS}


def is_exact(effect: str) -> bool:
    return effect in EXACT or effect.startswith("sprite_")


class Player:
    """Builds the item's timeline once; frame(t) is then cheap."""

    def __init__(self, item: dict, seed: int = 1):
        self.item = item
        self.rng = random.Random(seed)
        self.anim = None
        self.segments: list[tuple[int, object]] = []  # (duration ms, frames list | callable)
        if item.get("type") == "animation":
            self._build_animation()
        else:
            self._build_text()
        self.total = max(1, sum(d for d, _ in self.segments))

    # ---- building
    def _build_animation(self):
        it = self.item
        make = ANIMATIONS.get(it.get("animation", ""), ANIMATIONS["matrix_rain"])
        self._make = lambda: make(it, random.Random(7))
        self.anim, self._anim_t, self._anim_frame = self._make(), -1, [0] * WIDTH
        self.anim_ms = max(1, int((it.get("params") or {}).get("speed") or self.anim.frame_ms))
        self.segments = [(int(it.get("duration") or 10000), self._animation_at),
                         (int(it.get("gap") or 0), [[0] * WIDTH])]

    def _build_text(self):
        it = self.item
        cols, x0 = layout(it.get("text") or "", it.get("align") or "center")
        fits = len(cols) <= WIDTH
        fx_in = it.get("effect_in") or "scroll_left"
        fx_out = it.get("effect_out") or "scroll_left"
        sp_in, sp_out = max(1, int(it.get("speed_in") or 40)), max(1, int(it.get("speed_out") or 40))
        pause, gap = int(it.get("pause") or 0), int(it.get("gap") or 0)
        rng = self.rng
        x_rest = rest_x(fx_in, cols, x0)
        text = _place(cols, x_rest)  # the text at rest, as far as it's on the display

        def timed(frames, speed):
            return (len(frames) * speed, frames[:FRAMES_CAP])

        # In
        if fx_in in LASERS:
            self.segments.append(timed(_laser(fx_in, text, True, rng), sp_in))
        elif fx_in == "fade":
            self.segments.append((16 * sp_in, lambda t, s=sp_in: (text, min(1.0, (t // s + 1) / 16))))
        else:
            self.segments.append(timed(_parola_in(fx_in, cols, x0, rng), sp_in))
        # Pause, with the overlay (only on a text that fits, like the display)
        overlay = it.get("overlay") or "none"
        if overlay != "none" and fits and pause:
            self.segments.append((pause, lambda t: overlay_frame(overlay, text, t, rng)))
        else:
            self.segments.append((pause, [text]))
        # Out
        if fx_out in LASERS:
            self.segments.append(timed(_laser(fx_out, text, False, rng), sp_out))
        elif fx_out == "fade":
            self.segments.append((16 * sp_out, lambda t, s=sp_out: (text, max(0.0, 1 - (t // s + 1) / 16))))
        elif fx_out != "no_effect":  # with no exit effect the text stays up through the gap
            self.segments.append(timed(_parola_out(fx_out, cols, x_rest, rng), sp_out))
        self.segments.append((gap, [text if fx_out == "no_effect" else [0] * WIDTH]))

    def _animation_at(self, t: int):
        if t < self._anim_t:  # looped around: start again
            self.anim, self._anim_t, self._anim_frame = self._make(), -1, [0] * WIDTH
        # Step at 0, anim_ms, 2·anim_ms, ... up to t, like the display's frame timer.
        while (self._anim_t + self.anim_ms if self._anim_t >= 0 else 0) <= t:
            self._anim_t = self._anim_t + self.anim_ms if self._anim_t >= 0 else 0
            self._anim_frame = self.anim.step(self._anim_t)
        return self._anim_frame

    # ---- playing
    def frame(self, t: int) -> tuple[Frame, float]:
        t %= self.total
        last = len(self.segments) - 1
        for i, (dur, content) in enumerate(self.segments):
            if t >= dur and i < last:
                t -= dur
                continue
            if callable(content):
                r = content(t)
            else:
                r = content[min(len(content) - 1, t * len(content) // max(dur, 1))]
            f, level = r if isinstance(r, tuple) else (r, 1.0)
            if self.item.get("invert"):
                f = [~c & FULL for c in f]
            return f, level
        return [0] * WIDTH, 1.0
