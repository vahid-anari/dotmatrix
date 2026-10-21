#pragma once
#include "Animation.h"

// Falling "code" columns, as in The Matrix.
// matrix_rain:   rain only.
// matrix_reveal: the item's text appears out of the rain, letter pixel by pixel,
//                and stays once the rain has passed.
class MatrixRain : public Animation {
 public:
  explicit MatrixRain(bool reveal) : _reveal(reveal) {}
  void begin(const Item& item, const Display& display) override;
  bool step(Frame& f, uint32_t now) override;
  uint16_t defaultFrameMs() const override { return 45; }

 private:
  struct Drop {
    int8_t x = -1;      // column, -1 = inactive
    int8_t y = 0;       // head row (can be above the top)
    uint8_t len = 3;    // tail length
    uint8_t period = 1; // frames per step (1 = fastest)
    uint8_t tick = 0;
  };
  static constexpr uint8_t MAX_DROPS = 40;

  bool _reveal;
  Drop _drops[MAX_DROPS];
  uint8_t _density = 18;  // active drops
  Frame _target;          // text to reveal
  Frame _shown;           // pixels already revealed
  uint32_t _start = 0;
  uint32_t _duration = 10000;

  void spawn(Drop& d, bool preferHidden);
  bool fullyRevealed() const;
};
