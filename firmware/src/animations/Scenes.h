#pragma once
#include "Animation.h"

// The smaller animations, one class each. Matrix rain has its own file.

// Stars fly out from the middle, faster as they get closer to the edge.
class Starfield : public Animation {
 public:
  void begin(const Item& item, const Display& display) override;
  bool step(Frame& f, uint32_t now) override;
  uint16_t defaultFrameMs() const override { return 40; }

 private:
  struct Star {
    int16_t x, y;    // position, 1/256 pixel
    int16_t dx, dy;  // direction, 1/256 pixel per frame at the centre
  };
  static constexpr uint8_t MAX_STARS = 48;
  Star _stars[MAX_STARS];
  uint8_t _count = 24;
  void spawn(Star& s, bool anywhere);
};

// Conway's Game of Life on the 64×8 display (edges wrap). Starts again from a
// new random pattern when it dies out, settles, or has run for a while.
class Life : public Animation {
 public:
  void begin(const Item& item, const Display& display) override;
  bool step(Frame& f, uint32_t now) override;
  uint16_t defaultFrameMs() const override { return 140; }

 private:
  Frame _cells, _prev, _prev2;
  uint16_t _generation = 0;
  uint8_t _density = 35;  // % of cells alive in a new pattern
  uint8_t _fade = 0;      // frames left of the "starting again" wipe
  void seed();
};

// Rockets rise and burst into sparks that fall back down.
class Fireworks : public Animation {
 public:
  void begin(const Item& item, const Display& display) override;
  bool step(Frame& f, uint32_t now) override;
  uint16_t defaultFrameMs() const override { return 35; }

 private:
  struct Particle {
    int16_t x, y, dx, dy;  // 1/256 pixel
    uint8_t life;          // frames left; 0 = free
    bool rocket;
  };
  static constexpr uint8_t MAX_PARTICLES = 64;
  Particle _p[MAX_PARTICLES];
  uint8_t _rockets = 2;  // at most this many rockets in the air
  uint8_t _wait = 0;     // frames until the next launch
  void launch();
  void burst(const Particle& rocket);
};

// Bars bounce like a music equalizer, with peak dots that drop slowly.
class Equalizer : public Animation {
 public:
  void begin(const Item& item, const Display& display) override;
  bool step(Frame& f, uint32_t now) override;
  uint16_t defaultFrameMs() const override { return 60; }

 private:
  static constexpr uint8_t BARS = DISPLAY_WIDTH / 4;  // 3 columns + a gap each
  uint8_t _level[BARS] = {0};   // height, 1/16 row
  uint8_t _target[BARS] = {0};
  uint8_t _peak[BARS] = {0};    // rows
  uint8_t _peakHold[BARS] = {0};
};

// A snake that plays by itself: it heads for the food and avoids running into
// itself, and starts over when it gets stuck or grows long.
class Snake : public Animation {
 public:
  void begin(const Item& item, const Display& display) override;
  bool step(Frame& f, uint32_t now) override;
  uint16_t defaultFrameMs() const override { return 70; }

 private:
  static constexpr uint16_t MAX_LEN = 48;
  uint16_t _body[MAX_LEN];  // x * 8 + y, head first
  uint16_t _len = 0;
  uint16_t _food = 0;
  uint8_t _dir = 0;   // 0 right, 1 down, 2 left, 3 up
  uint8_t _dead = 0;  // frames left of the game-over blink
  uint8_t _tick = 0;
  void reset();
  void placeFood();
  bool occupied(int x, int y, bool ignoreTail) const;
  uint16_t room(int x, int y) const;  // free cells reachable from (x, y)
};

// A sprite (Pacman, a rocket, ...) runs across the display again and again.
class SpriteRun : public Animation {
 public:
  void begin(const Item& item, const Display& display) override;
  bool step(Frame& f, uint32_t now) override;
  uint16_t defaultFrameMs() const override { return 50; }

 private:
  const struct Sprite* _sprite = nullptr;
  int16_t _x = 0;  // leading column
  uint8_t _frame = 0;
};
