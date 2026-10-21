#include "TextMode.h"

#include "../App.h"
#include "../animations/Registry.h"
#include "../display/Effects.h"

// Shown when the playlist is empty.
static Item placeholderItem() {
  Item it;
  strlcpy(it.text, "Hello!", sizeof(it.text));
  it.pause = 1500;
  it.gap = 300;
  return it;
}

void TextMode::begin(App& app) { restart(app); }

void TextMode::end(App& app) {
  _state = State::Idle;
  _anim = nullptr;
  app.display.clear();
}

void TextMode::restart(App& app) {
  _index = -1;
  _state = State::Idle;
  app.display.clear();
  next(app, millis());
}

void TextMode::startPreview(App& app, const Item& item) {
  _preview = item;
  _previewing = true;
  play(app, _preview, millis());
}

void TextMode::stopPreview(App& app) {
  if (!_previewing) return;
  _previewing = false;
  restart(app);
}

void TextMode::play(App& app, const Item& item, uint32_t now) {
  _current = item;
  app.display.setBrightness(app.brightnessFor(item.brightness));
  if (item.type == ItemType::Animation && (_anim = animationAt(item.animation))) {
    _anim->begin(_current, app.display);
    _frameMs = item.frameMs ? item.frameMs : _anim->defaultFrameMs();
    _started = _lastFrame = now;
    _frame.clear();
    app.display.clear();
    _state = State::Anim;
  } else {
    _anim = nullptr;
    app.display.playText(_current);
    _state = State::Text;
  }
}

void TextMode::next(App& app, uint32_t now) {
  if (_previewing) {
    play(app, _preview, now);  // loop the preview item
    return;
  }
  if (items.empty()) {
    static const Item placeholder = placeholderItem();
    play(app, placeholder, now);
    return;
  }
  _index = (_index + 1) % (int)items.size();
  play(app, items[_index], now);
}

void TextMode::startGap(App& app, uint32_t now) {
  _anim = nullptr;
  _gapStart = now;
  _state = State::Gap;
  // A text whose exit effect is "no effect" stays up during the gap.
  if (!(_current.type == ItemType::Text && effectAt(_current.effectOut).effect == PA_NO_EFFECT))
    app.display.clear();
}

void TextMode::loop(App& app, uint32_t now) {
  switch (_state) {
    case State::Idle:
      next(app, now);
      break;

    case State::Text:
      if (app.display.animate()) startGap(app, now);
      break;

    case State::Anim:
      if (now - _lastFrame >= _frameMs) {
        _lastFrame = now;
        bool more = _anim->step(_frame, now);
        if (_current.invert) _frame.invert();
        app.display.push(_frame);
        if (!more) startGap(app, now);
      }
      if (_state == State::Anim && now - _started >= _current.duration) startGap(app, now);
      break;

    case State::Gap:
      if (now - _gapStart >= _current.gap) next(app, now);
      break;
  }
}
