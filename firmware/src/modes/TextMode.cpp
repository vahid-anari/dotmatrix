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
  } else if (phased(app, item)) {
    _anim = nullptr;
    _brightness = _shownBrightness = app.brightnessFor(item.brightness);
    _base.clear();
    // Text wider than the display starts at the left edge, except after
    // scrolling in from the right: Parola stops once the last column is in.
    int offset = 0;
    uint16_t w = app.display.textWidth(_current.text);
    if (w > DISPLAY_WIDTH && effectAt(_current.effectIn).effect == PA_SCROLL_LEFT)
      offset = (int)DISPLAY_WIDTH - (int)w;
    app.display.drawText(_base, _current.text, _current.align, offset);
    beginIn(app, now);
  } else {
    _anim = nullptr;
    app.display.playText(_current);
    _state = State::Text;
  }
}

bool TextMode::phased(App& app, const Item& item) const {
  if (effectAt(item.effectIn).fx != FxKind::None || effectAt(item.effectOut).fx != FxKind::None)
    return true;
  // Overlays need the whole text on the display: a longer one scrolls through,
  // and Parola leaves it somewhere our frames can't match.
  return item.overlay && app.display.textWidth(item.text) <= DISPLAY_WIDTH;
}

void TextMode::show(App& app, const Frame& f) {
  _frame = f;
  if (_current.invert) _frame.invert();
  app.display.push(_frame);
}

void TextMode::beginIn(App& app, uint32_t now) {
  const EffectInfo& in = effectAt(_current.effectIn);
  if (in.fx != FxKind::None) {
    _fx.begin(_base, in.fx, true);
    _frameMs = _current.speedIn;
    _lastFrame = now - _frameMs;  // first frame right away
    app.display.clear();
    _state = State::FxIn;
  } else if (effectIsNone(_current.effectIn)) {
    beginHold(app, now);
  } else {
    app.display.playTextIn(_current);
    _state = State::ParolaIn;
  }
}

void TextMode::beginHold(App& app, uint32_t now) {
  _holdStart = _lastFrame = now;
  _overlay.begin(_base, (OverlayKind)_current.overlay, _brightness, now);
  show(app, _base);
  _state = State::Hold;
}

void TextMode::beginOut(App& app, uint32_t now) {
  _brightness = app.brightnessFor(_current.brightness);  // night dimming may have started meanwhile
  if (_shownBrightness != _brightness) app.display.setBrightness(_brightness);
  _shownBrightness = _brightness;
  show(app, _base);  // undo whatever the overlay was showing
  const EffectInfo& out = effectAt(_current.effectOut);
  if (out.fx != FxKind::None) {
    _fx.begin(_base, out.fx, false);
    _frameMs = _current.speedOut;
    _lastFrame = now - _frameMs;
    _state = State::FxOut;
  } else if (effectIsNone(_current.effectOut)) {
    startGap(app, now);  // the text stays up
  } else {
    app.display.playTextOut(_current);
    _state = State::ParolaOut;
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
  if (!(_current.type == ItemType::Text && effectIsNone(_current.effectOut)))
    app.display.clear();
}

void TextMode::loop(App& app, uint32_t now) {
  switch (_state) {
    case State::Idle:
      next(app, now);
      break;

    case State::Text:
    case State::ParolaOut:
      if (app.display.animate()) startGap(app, now);
      break;

    case State::ParolaIn:
      if (app.display.animate()) beginHold(app, now);
      break;

    case State::FxIn:
    case State::FxOut:
      if (now - _lastFrame >= _frameMs) {
        _lastFrame = now;
        Frame f;
        bool more = _fx.step(f);
        show(app, f);
        if (!more) {
          if (_state == State::FxIn)
            beginHold(app, now);
          else
            startGap(app, now);
        }
      }
      break;

    case State::Hold:
      if (_current.overlay && now - _lastFrame >= _overlay.frameMs()) {
        _lastFrame = now;
        Frame f;
        uint8_t b = _overlay.step(f, now);
        show(app, f);
        if (b != _shownBrightness) app.display.setBrightness(_shownBrightness = b);
      }
      if (now - _holdStart >= _current.pause) beginOut(app, now);
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
