#pragma once
#include <MD_Parola.h>

#include "TextFx.h"

// Text entry/exit effects, addressed by a stable string ID in the protocol.
// IDs starting with "sprite_" use PA_SPRITE with the sprite of that name.
// Effects with an FxKind are our own (TextFx), the rest are Parola's.
struct EffectInfo {
  const char* id;
  textEffect_t effect;
  FxKind fx = FxKind::None;
};

// Returns the effect index for an ID, or 0 (no_effect) if unknown.
uint8_t effectIndex(const char* id);
// "sprite_pacman" → "pacman"; nullptr for non-sprite effects.
const char* effectSpriteName(uint8_t index);
const EffectInfo& effectAt(uint8_t index);
uint8_t effectCount();
// True for "no_effect": the text simply stays (out) or isn't animated (in).
inline bool effectIsNone(uint8_t index) { return index == 0; }
