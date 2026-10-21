#pragma once
#include <Arduino.h>

struct Sprite {
  const char* id;       // e.g. "pacman"
  const uint8_t* data;  // frames × width column bytes, bit 0 = top row
  uint8_t width;        // columns per frame
  uint8_t frames;
};

const Sprite* findSprite(const char* id);
size_t spriteCount();
const Sprite& spriteAt(size_t i);
