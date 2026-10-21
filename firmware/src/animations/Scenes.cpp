#include "Scenes.h"

#include "../display/Sprites.h"

// Positions and speeds below are in 1/256 pixel, so everything stays integer
// (the ESP32-C3 has no floating-point unit).
static constexpr int16_t PX = 256;
static constexpr int16_t W = DISPLAY_WIDTH, H = DISPLAY_HEIGHT;

// ================================================================ Starfield

void Starfield::begin(const Item& item, const Display&) {
  _count = item.density ? min<uint8_t>(item.density, MAX_STARS) : 24;
  for (uint8_t i = 0; i < _count; i++) spawn(_stars[i], true);
}

void Starfield::spawn(Star& s, bool anywhere) {
  // The display is wide and short, so stars mostly travel sideways.
  do {
    s.dx = random(-160, 161);
    s.dy = random(-40, 41);
  } while (abs(s.dx) < 24 && abs(s.dy) < 12);
  s.x = (W * PX) / 2;
  s.y = (H * PX) / 2;
  // At the start, spread them along their paths so the sky isn't empty.
  for (int k = anywhere ? random(0, 40) : 0; k > 0; k--) {
    s.x += s.dx / 4;
    s.y += s.dy / 4;
  }
}

bool Starfield::step(Frame& f, uint32_t) {
  f.clear();
  for (uint8_t i = 0; i < _count; i++) {
    Star& s = _stars[i];
    int px = s.x / PX, py = s.y / PX;
    // Speed grows with the distance from the middle: they "come closer".
    int dist = abs(px - W / 2) + 4 * abs(py - H / 2);
    int k = 4 + dist / 3;
    s.x += s.dx * k / 16;
    s.y += s.dy * k / 16;
    int nx = s.x / PX, ny = s.y / PX;
    if (s.x < 0 || nx >= W || s.y < 0 || ny >= H) {
      spawn(s, false);
      continue;
    }
    f.set(nx, ny);
    if (dist > 20) f.set(px, py);  // fast stars leave a short streak
  }
  return true;
}

// ===================================================================== Life

void Life::begin(const Item& item, const Display&) {
  _density = item.density ? constrain(item.density, 5, 60) : 35;
  seed();
}

void Life::seed() {
  _cells.clear();
  for (int x = 0; x < W; x++)
    for (int y = 0; y < H; y++)
      if ((uint8_t)random(100) < _density) _cells.set(x, y);
  _prev.clear();
  _prev2.clear();
  _generation = 0;
  _fade = 0;
}

bool Life::step(Frame& f, uint32_t) {
  if (_fade) {
    // The last pattern blinks a few times, then a new one starts.
    if (--_fade == 0) seed();
    f = (_fade / 2) % 2 ? Frame() : _cells;
    return true;
  }

  Frame next;
  uint16_t alive = 0;
  for (int x = 0; x < W; x++) {
    for (int y = 0; y < H; y++) {
      uint8_t n = 0;
      for (int dx = -1; dx <= 1; dx++)
        for (int dy = -1; dy <= 1; dy++)
          if ((dx || dy) && _cells.get((x + dx + W) % W, (y + dy + H) % H)) n++;
      bool on = _cells.get(x, y) ? (n == 2 || n == 3) : n == 3;
      if (on) next.set(x, y), alive++;
    }
  }

  auto same = [](const Frame& a, const Frame& b) { return memcmp(a.col, b.col, sizeof(a.col)) == 0; };
  // Dead, still, blinking back and forth (period 2 or 3), or just old: start again.
  bool settled = alive == 0 || same(next, _cells) || same(next, _prev) || same(next, _prev2);
  _prev2 = _prev;
  _prev = _cells;
  _cells = next;
  if (settled || ++_generation > 400) _fade = 12;
  f = _cells;
  return true;
}

// ================================================================ Fireworks

void Fireworks::begin(const Item& item, const Display&) {
  _rockets = item.density ? constrain(item.density, 1, 4) : 2;
  for (auto& p : _p) p.life = 0;
  _wait = 0;
}

void Fireworks::launch() {
  for (auto& p : _p) {
    if (p.life) continue;
    p.rocket = true;
    p.x = random(6, W - 6) * PX;
    p.y = (H - 1) * PX;
    p.dx = random(-20, 21);
    p.dy = -random(150, 200);
    p.life = 60;
    return;
  }
}

void Fireworks::burst(const Particle& r) {
  uint8_t sparks = random(10, 16);
  for (auto& p : _p) {
    if (!sparks) break;
    if (p.life) continue;
    p.rocket = false;
    p.x = r.x;
    p.y = r.y;
    p.dx = random(-240, 241);
    p.dy = random(-140, 81);
    p.life = random(14, 28);
    sparks--;
  }
}

bool Fireworks::step(Frame& f, uint32_t) {
  f.clear();
  uint8_t inAir = 0;
  for (auto& p : _p)
    if (p.life && p.rocket) inAir++;
  if (_wait) _wait--;
  if (!_wait && inAir < _rockets) {
    launch();
    _wait = random(6, 28);
  }

  for (auto& p : _p) {
    if (!p.life) continue;
    p.x += p.dx;
    p.y += p.dy;
    int x = p.x / PX, y = p.y / PX;
    if (p.rocket) {
      p.dy += 6;  // gravity slows it down
      if (p.dy > -30 || y <= 1) {
        p.life = 0;
        burst(p);
        continue;
      }
      f.set(x, y);
      if (random(100) < 70) f.set(x, y + 1);  // flickering exhaust
    } else {
      p.dy += 5;
      p.dx -= p.dx / 12;  // air drag
      p.life--;
      if (p.x < 0 || x >= W || y >= H) {
        p.life = 0;
        continue;
      }
      // Sparks flicker as they die out (no per-pixel dimming on a MAX7219).
      if (p.life > 6 || random(100) < 50) f.set(x, y);
    }
    if (p.life) p.life--;
  }
  return true;
}

// ================================================================ Equalizer

void Equalizer::begin(const Item&, const Display&) {
  for (uint8_t b = 0; b < BARS; b++) _level[b] = _target[b] = _peak[b] = _peakHold[b] = 0;
}

bool Equalizer::step(Frame& f, uint32_t) {
  f.clear();
  for (uint8_t b = 0; b < BARS; b++) {
    if (random(100) < 30) {
      // Low bars (left) are usually busier, like bass on a real one.
      uint8_t top = H * 16 - (b * 2);
      _target[b] = random(top / 5, top);
    }
    if (_level[b] < _target[b])
      _level[b] += (_target[b] - _level[b] + 1) / 2;  // up fast
    else
      _level[b] = _level[b] > 10 ? _level[b] - 10 : 0;  // down slowly
    if (_level[b] >= _target[b]) _target[b] = 0;

    uint8_t h = _level[b] / 16;
    if (h > _peak[b]) {
      _peak[b] = h;
      _peakHold[b] = 8;
    } else if (_peakHold[b]) {
      _peakHold[b]--;
    } else if (_peak[b]) {
      _peak[b]--;
      _peakHold[b] = 1;
    }

    uint8_t bits = h ? (uint8_t)(0xFF << (H - h)) : 0;
    if (_peak[b] > h) bits |= 1 << (H - _peak[b]);
    for (uint8_t i = 0; i < 3; i++) f.col[b * 4 + i] = bits;
  }
  return true;
}

// ==================================================================== Snake

static const int8_t SNAKE_DX[] = {1, 0, -1, 0};
static const int8_t SNAKE_DY[] = {0, 1, 0, -1};

void Snake::begin(const Item&, const Display&) { reset(); }

void Snake::reset() {
  _len = 4;
  for (uint16_t i = 0; i < _len; i++) _body[i] = (20 - i) * 8 + 3;
  _dir = 0;
  _dead = 0;
  placeFood();
}

bool Snake::occupied(int x, int y, bool ignoreTail) const {
  uint16_t n = ignoreTail ? _len - 1 : _len;
  for (uint16_t i = 0; i < n; i++)
    if (_body[i] == x * 8 + y) return true;
  return false;
}

void Snake::placeFood() {
  do {
    _food = random(W) * 8 + random(H);
  } while (occupied(_food / 8, _food % 8, false));
}

uint16_t Snake::room(int sx, int sy) const {
  Frame seen;
  for (uint16_t i = 0; i + 1 < _len; i++) seen.set(_body[i] / 8, _body[i] % 8);
  static uint16_t queue[DISPLAY_WIDTH * DISPLAY_HEIGHT];
  uint16_t head = 0, tail = 0;
  queue[tail++] = sx * 8 + sy;
  seen.set(sx, sy);
  while (head < tail) {
    int x = queue[head] / 8, y = queue[head] % 8;
    head++;
    for (uint8_t d = 0; d < 4; d++) {
      int nx = x + SNAKE_DX[d], ny = y + SNAKE_DY[d];
      if (nx < 0 || nx >= W || ny < 0 || ny >= H || seen.get(nx, ny)) continue;
      seen.set(nx, ny);
      queue[tail++] = nx * 8 + ny;
    }
  }
  return tail;
}

bool Snake::step(Frame& f, uint32_t) {
  _tick++;
  if (_dead) {
    // Game over: the snake blinks, then a new game starts.
    if (--_dead == 0) reset();
  } else {
    int hx = _body[0] / 8, hy = _body[0] % 8;
    int fx = _food / 8, fy = _food % 8;
    int best = -1;
    long bestScore = 0;
    for (uint8_t d = 0; d < 4; d++) {
      if (d == (_dir + 2) % 4) continue;  // no turning back
      int nx = hx + SNAKE_DX[d], ny = hy + SNAKE_DY[d];
      if (nx < 0 || nx >= W || ny < 0 || ny >= H || occupied(nx, ny, true)) continue;
      // Closer to the food is better, but never into a pocket too small to fit.
      uint16_t space = room(nx, ny);
      long score = -(long)(abs(nx - fx) + abs(ny - fy)) * 4;
      if (space < _len + 2) score -= 1000 - space;
      if (d == _dir) score += 1;  // prefer going straight on a tie
      if (best < 0 || score > bestScore) best = d, bestScore = score;
    }
    if (best < 0) {
      _dead = 14;
    } else {
      _dir = best;
      int nx = hx + SNAKE_DX[_dir], ny = hy + SNAKE_DY[_dir];
      bool eats = nx * 8 + ny == _food;
      if (eats && _len < MAX_LEN) _len++;
      for (uint16_t i = _len - 1; i > 0; i--) _body[i] = _body[i - 1];
      _body[0] = nx * 8 + ny;
      if (eats) {
        if (_len >= MAX_LEN)
          _dead = 14;  // it's won: start again
        else
          placeFood();
      }
    }
  }

  f.clear();
  if (!_dead || (_dead / 2) % 2)
    for (uint16_t i = 0; i < _len; i++) f.set(_body[i] / 8, _body[i] % 8);
  if (!_dead && _tick % 4 < 3) f.set(_food / 8, _food % 8);  // the food blinks
  return true;
}

// ================================================================ SpriteRun

void SpriteRun::begin(const Item& item, const Display&) {
  _sprite = item.sprite < spriteCount() ? &spriteAt(item.sprite) : &spriteAt(0);
  _x = -1;
  _frame = 0;
}

bool SpriteRun::step(Frame& f, uint32_t) {
  f.clear();
  // Column 0 of the sprite data is its front edge (as Parola draws them).
  for (uint8_t i = 0; i < _sprite->width; i++) {
    int x = _x - i;
    if (x >= 0 && x < W) f.col[x] = _sprite->data[_frame * _sprite->width + i];
  }
  if (++_frame >= _sprite->frames) _frame = 0;
  if (++_x - _sprite->width >= W + 8) _x = -1;  // a short gap, then again
  return true;
}
