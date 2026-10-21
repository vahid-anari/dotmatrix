#pragma once
#include <Arduino.h>

class Animation;

// Index of an animation ID ("matrix_rain"), or -1 if unknown.
int animationIndex(const char* id);
const char* animationId(uint8_t index);
uint8_t animationCount();
// The single shared instance for an index (only one animation runs at a time).
Animation* animationAt(uint8_t index);
