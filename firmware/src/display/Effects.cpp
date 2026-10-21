#include "Effects.h"

#include "Sprites.h"

static const EffectInfo EFFECTS[] = {
    {"no_effect", PA_NO_EFFECT},
    {"print", PA_PRINT},
    {"scroll_up", PA_SCROLL_UP},
    {"scroll_down", PA_SCROLL_DOWN},
    {"scroll_left", PA_SCROLL_LEFT},
    {"scroll_right", PA_SCROLL_RIGHT},
    {"slice", PA_SLICE},
    {"mesh", PA_MESH},
    {"fade", PA_FADE},
    {"dissolve", PA_DISSOLVE},
    {"blinds", PA_BLINDS},
    {"random", PA_RANDOM},
    {"wipe", PA_WIPE},
    {"wipe_cursor", PA_WIPE_CURSOR},
    {"opening", PA_OPENING},
    {"opening_cursor", PA_OPENING_CURSOR},
    {"closing", PA_CLOSING},
    {"closing_cursor", PA_CLOSING_CURSOR},
    {"scroll_up_left", PA_SCROLL_UP_LEFT},
    {"scroll_up_right", PA_SCROLL_UP_RIGHT},
    {"scroll_down_left", PA_SCROLL_DOWN_LEFT},
    {"scroll_down_right", PA_SCROLL_DOWN_RIGHT},
    {"scan_horiz", PA_SCAN_HORIZ},
    {"scan_horiz_x", PA_SCAN_HORIZX},
    {"scan_vert", PA_SCAN_VERT},
    {"scan_vert_x", PA_SCAN_VERTX},
    {"grow_up", PA_GROW_UP},
    {"grow_down", PA_GROW_DOWN},
    {"sprite_pacman", PA_SPRITE},
    {"sprite_pacman2", PA_SPRITE},
    {"sprite_wave", PA_SPRITE},
    {"sprite_rolling_square", PA_SPRITE},
    {"sprite_rolling_octagon", PA_SPRITE},
    {"sprite_lines", PA_SPRITE},
    {"sprite_arrow", PA_SPRITE},
    {"sprite_arrow2", PA_SPRITE},
    {"sprite_sailboat", PA_SPRITE},
    {"sprite_steamboat", PA_SPRITE},
    {"sprite_heart", PA_SPRITE},
    {"sprite_invader", PA_SPRITE},
    {"sprite_rocket", PA_SPRITE},
    {"sprite_fireball", PA_SPRITE},
    {"sprite_chevron", PA_SPRITE},
    {"sprite_walker", PA_SPRITE},
    {"sprite_wheel", PA_SPRITE},
    {"sprite_hourglass", PA_SPRITE},
    // Our own, drawn by TextFx. New effects go at the end so indexes stay put.
    {"laser_write", PA_NO_EFFECT, FxKind::LaserWrite},
    {"laser_scan", PA_NO_EFFECT, FxKind::LaserScan},
    {"laser_cut", PA_NO_EFFECT, FxKind::LaserCut},
};

static constexpr uint8_t COUNT = sizeof(EFFECTS) / sizeof(EFFECTS[0]);

uint8_t effectIndex(const char* id) {
  if (id == nullptr) return 0;
  for (uint8_t i = 0; i < COUNT; i++)
    if (strcmp(EFFECTS[i].id, id) == 0) return i;
  return 0;
}

const char* effectSpriteName(uint8_t index) {
  if (index >= COUNT || EFFECTS[index].effect != PA_SPRITE) return nullptr;
  return EFFECTS[index].id + 7;  // skip "sprite_"
}

const EffectInfo& effectAt(uint8_t index) { return EFFECTS[index < COUNT ? index : 0]; }
uint8_t effectCount() { return COUNT; }
