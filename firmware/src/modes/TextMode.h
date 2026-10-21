#pragma once
#include <vector>

#include "../animations/Animation.h"
#include "../display/Frame.h"
#include "../model/Item.h"
#include "Mode.h"

// Plays the playlist: text items through Parola, animation items frame by frame.
// Also plays a single "preview" item in a loop while the app is editing it.
class TextMode : public Mode {
 public:
  const char* id() const override { return "text"; }
  void begin(App& app) override;
  void loop(App& app, uint32_t now) override;
  void end(App& app) override;

  std::vector<Item> items;
  char playlistName[33] = "";

  void restart(App& app);
  void startPreview(App& app, const Item& item);
  void stopPreview(App& app);
  bool previewing() const { return _previewing; }
  int index() const { return _index; }

 private:
  enum class State : uint8_t { Idle, Text, Anim, Gap };
  State _state = State::Idle;
  int _index = -1;
  bool _previewing = false;
  Item _preview;
  Item _current;  // copy of the item playing (the list may change meanwhile)
  Animation* _anim = nullptr;
  Frame _frame;
  uint32_t _started = 0;
  uint32_t _lastFrame = 0;
  uint16_t _frameMs = 50;
  uint32_t _gapStart = 0;

  void play(App& app, const Item& item, uint32_t now);
  void next(App& app, uint32_t now);
  void startGap(App& app, uint32_t now);
};
