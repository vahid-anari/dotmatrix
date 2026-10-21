#pragma once
#include <ArduinoJson.h>

#include "../config.h"

enum class ItemType : uint8_t { Text, Animation };
enum class Align : uint8_t { Left, Center, Right };

// One playlist entry. Fixed-size so a playlist never fragments the heap.
struct Item {
  ItemType type = ItemType::Text;
  char text[MAX_TEXT + 1] = "";
  uint8_t effectIn = 4;   // index into the effects table (4 = scroll_left)
  uint8_t effectOut = 4;
  uint16_t speedIn = 50;  // ms per frame
  uint16_t speedOut = 50;
  uint16_t pause = 400;   // ms shown between in and out
  uint16_t gap = 100;     // ms blank before the next item
  Align align = Align::Center;
  bool invert = false;
  int8_t brightness = -1;  // 0..15, -1 = use global

  // Animation items
  uint8_t animation = 0;    // index into the animation registry
  uint32_t duration = 10000;
  uint8_t density = 0;      // 0 = animation default
  uint16_t frameMs = 0;     // 0 = animation default
};

// Parse an item; returns false with a message in err on invalid input.
bool itemFromJson(JsonObjectConst o, Item& out, const char*& err);
void itemToJson(const Item& item, JsonObject o);
