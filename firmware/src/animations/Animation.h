#pragma once
#include "../display/Display.h"
#include "../display/Frame.h"
#include "../model/Item.h"

// A standalone scene drawn frame by frame.
// To add one: subclass this, then register it in Registry.cpp.
class Animation {
 public:
  virtual ~Animation() = default;
  // Called once when the item starts. `display` is for text rendering only.
  virtual void begin(const Item& item, const Display& display) = 0;
  // Draw the next frame into f. Return false to finish early.
  virtual bool step(Frame& f, uint32_t now) = 0;
  // Default frame interval; an item's params.speed overrides it.
  virtual uint16_t defaultFrameMs() const { return 50; }
};
