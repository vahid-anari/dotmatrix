#include "Item.h"

#include "JsonUtil.h"

#include "../animations/Registry.h"
#include "../display/Effects.h"
#include "../display/Overlay.h"
#include "../display/Sprites.h"

static Align parseAlign(const char* s) {
  if (s && strcmp(s, "left") == 0) return Align::Left;
  if (s && strcmp(s, "right") == 0) return Align::Right;
  return Align::Center;
}

static const char* alignName(Align a) {
  switch (a) {
    case Align::Left: return "left";
    case Align::Right: return "right";
    default: return "center";
  }
}

template <typename T>
static T clampTo(long v, long lo, long hi) {
  return (T)(v < lo ? lo : (v > hi ? hi : v));
}

bool itemFromJson(JsonObjectConst o, Item& out, const char*& err) {
  Item it;  // start from defaults
  const char* type = o["type"] | "text";

  if (strcmp(type, "animation") == 0) {
    it.type = ItemType::Animation;
    const char* anim = o["animation"] | "";
    int idx = animationIndex(anim);
    if (idx < 0) {
      err = "unknown animation";
      return false;
    }
    it.animation = (uint8_t)idx;
    it.duration = clampTo<uint32_t>(jsonNum(o["duration"], 10000), 500, 600000);
    JsonObjectConst p = o["params"];
    it.density = clampTo<uint8_t>(jsonNum(p["density"], 0), 0, 64);
    it.frameMs = clampTo<uint16_t>(jsonNum(p["speed"], 0), 0, 1000);
    const char* sprite = p["sprite"] | "";
    for (size_t i = 0; i < spriteCount(); i++)
      if (strcmp(spriteAt(i).id, sprite) == 0) it.sprite = (uint8_t)i;
  } else if (strcmp(type, "text") != 0) {
    err = "unknown item type";
    return false;
  }

  const char* text = o["text"] | "";
  if (strlen(text) > MAX_TEXT) {
    err = "text too long";
    return false;
  }
  strlcpy(it.text, text, sizeof(it.text));

  it.effectIn = effectIndex(o["effect_in"] | "scroll_left");
  it.effectOut = effectIndex(o["effect_out"] | "scroll_left");
  it.speedIn = clampTo<uint16_t>(jsonNum(o["speed_in"], 50), 1, 1000);
  it.speedOut = clampTo<uint16_t>(jsonNum(o["speed_out"], 50), 1, 1000);
  it.pause = clampTo<uint16_t>(jsonNum(o["pause"], 400), 0, 60000);
  it.gap = clampTo<uint16_t>(jsonNum(o["gap"], 100), 0, 10000);
  it.align = parseAlign(o["align"] | "center");
  it.invert = o["invert"] | false;
  it.brightness = clampTo<int8_t>(jsonNum(o["brightness"], -1), -1, 15);
  it.overlay = overlayIndex(o["overlay"] | "none");

  out = it;
  return true;
}

void itemToJson(const Item& it, JsonObject o) {
  if (it.type == ItemType::Animation) {
    o["type"] = "animation";
    o["animation"] = animationId(it.animation);
    o["duration"] = it.duration;
    if (it.density || it.frameMs || it.sprite) {
      JsonObject p = o["params"].to<JsonObject>();
      if (it.density) p["density"] = it.density;
      if (it.frameMs) p["speed"] = it.frameMs;
      if (it.sprite) p["sprite"] = spriteAt(it.sprite).id;
    }
  } else {
    o["type"] = "text";
  }
  o["text"] = it.text;
  o["effect_in"] = effectAt(it.effectIn).id;
  o["effect_out"] = effectAt(it.effectOut).id;
  o["speed_in"] = it.speedIn;
  o["speed_out"] = it.speedOut;
  o["pause"] = it.pause;
  o["gap"] = it.gap;
  o["align"] = alignName(it.align);
  o["invert"] = it.invert;
  if (it.brightness >= 0) o["brightness"] = it.brightness;
  if (it.overlay) o["overlay"] = overlayId(it.overlay);
}
