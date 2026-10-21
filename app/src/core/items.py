"""Playlist items: defaults, readable names, and the built-in Demo group.

Items are plain dicts in the device's JSON format (docs/DESIGN.md §6), so a
group's items can be sent to the device as they are.
"""
import copy

# Used until the device has sent its own lists in `hello`.
DEFAULT_EFFECTS = [
    "no_effect", "print", "scroll_up", "scroll_down", "scroll_left", "scroll_right", "slice",
    "mesh", "fade", "dissolve", "blinds", "random", "wipe", "wipe_cursor", "opening",
    "opening_cursor", "closing", "closing_cursor", "scroll_up_left", "scroll_up_right",
    "scroll_down_left", "scroll_down_right", "scan_horiz", "scan_horiz_x", "scan_vert",
    "scan_vert_x", "grow_up", "grow_down", "sprite_pacman", "sprite_pacman2", "sprite_wave",
    "sprite_rolling_square", "sprite_rolling_octagon", "sprite_lines", "sprite_arrow",
    "sprite_arrow2", "sprite_sailboat", "sprite_steamboat", "sprite_heart", "sprite_invader",
    "sprite_rocket", "sprite_fireball", "sprite_chevron", "sprite_walker", "sprite_wheel",
    "sprite_hourglass", "laser_write", "laser_scan", "laser_cut",
    "laser_beam",
]
DEFAULT_ANIMATIONS = ["matrix_rain", "matrix_reveal", "starfield", "life", "fireworks", "equalizer",
                      "snake", "sprite_run"]
DEFAULT_OVERLAYS = ["none", "wave", "sparkle", "pulse", "border"]
DEFAULT_SPRITES = ["pacman", "pacman2", "wave", "rolling_square", "rolling_octagon", "lines", "arrow",
                   "arrow2", "sailboat", "steamboat", "heart", "invader", "rocket", "fireball", "chevron",
                   "walker", "wheel", "hourglass"]

# Settings for each animation: which text and parameter sliders the editor shows.
# density = (label, lowest, highest, default); speed = the default frame time (ms),
# the same as defaultFrameMs() in the firmware.
ANIMATION_INFO = {
    "matrix_rain": {"density": ("Number of drops", 4, 40, 18), "speed": 45},
    "matrix_reveal": {"density": ("Number of drops", 4, 40, 18), "speed": 45, "text": True},
    "starfield": {"density": ("Number of stars", 6, 48, 24), "speed": 40},
    "life": {"density": ("Cells alive at the start (%)", 5, 60, 35), "speed": 140},
    "fireworks": {"density": ("Rockets in the air", 1, 4, 2), "speed": 35},
    "equalizer": {"speed": 60},
    "snake": {"speed": 70},
    "sprite_run": {"speed": 50, "sprite": True},
}

_NAMES = {
    "no_effect": "None", "scan_horiz_x": "Scan horizontal X", "scan_horiz": "Scan horizontal",
    "scan_vert_x": "Scan vertical X", "scan_vert": "Scan vertical",
    "sprite_pacman2": "Pacman & ghost", "sprite_arrow2": "Arrow (outward)",
    "sprite_invader": "Space invader", "sprite_walker": "Walking man", "sprite_heart": "Beating heart",
    "matrix_rain": "Matrix rain", "matrix_reveal": "Matrix reveal", "life": "Game of Life",
    "sprite_run": "Running sprite", "none": "Nothing", "pacman2": "Pacman & ghost",
    "arrow2": "Arrow (outward)", "invader": "Space invader", "walker": "Walking man",
    "heart": "Beating heart",
}


def nice_name(effect_id: str) -> str:
    """'scroll_up_left' → 'Scroll up left', 'sprite_pacman' → 'Pacman'."""
    if effect_id in _NAMES:
        return _NAMES[effect_id]
    name = effect_id.removeprefix("sprite_").replace("_", " ")
    return name[:1].upper() + name[1:]


def is_sprite(effect_id: str) -> bool:
    return effect_id.startswith("sprite_")


def new_text_item(text: str = "Hello") -> dict:
    return {
        "type": "text", "text": text,
        "effect_in": "scroll_left", "effect_out": "scroll_left",
        "speed_in": 40, "speed_out": 40, "pause": 1000, "gap": 100,
        "align": "center", "invert": False, "overlay": "none",
    }


def new_animation_item(animation: str = "matrix_reveal", text: str = "Hello") -> dict:
    return {
        "type": "animation", "animation": animation, "text": text,
        "duration": 10000, "align": "center", "invert": False, "gap": 200,
    }


def normalized(item: dict) -> dict:
    """Fill in missing fields so the editor always has every key."""
    base = new_animation_item(item.get("animation", "matrix_rain")) if item.get("type") == "animation" \
        else new_text_item("")
    out = {**base, **copy.deepcopy(item)}
    out.setdefault("text", "")
    return out


def summary(item: dict) -> str:
    """One line describing how an item plays, for lists."""
    if item.get("type") == "animation":
        return f"{nice_name(item.get('animation', ''))}, {item.get('duration', 10000) / 1000:g} s"
    a, b = item.get("effect_in", "scroll_left"), item.get("effect_out", "scroll_left")
    fx = nice_name(a) if a == b else f"{nice_name(a)} in, {nice_name(b).lower()} out"
    out = f"{fx}, stays {item.get('pause', 400) / 1000:g} s"
    if item.get("overlay", "none") != "none":
        out += f" with {nice_name(item['overlay']).lower()}"
    return out


DEMO_NAME = "Demo"


def demo_items(effects: list[str] = DEFAULT_EFFECTS, animations: list[str] = DEFAULT_ANIMATIONS,
               overlays: list[str] = DEFAULT_OVERLAYS) -> list[dict]:
    """One item per animation, then one per effect, then one per overlay
    (like the old app's Demo)."""
    items = []
    if "matrix_reveal" in animations:
        items.append({**new_animation_item("matrix_reveal", "DEMO"), "duration": 8000})
    for anim in animations:
        if anim != "matrix_reveal":
            items.append({**new_animation_item(anim, ""), "duration": 6000})
    for fx in effects:
        if fx == "no_effect":
            continue
        speed = 10 if fx == "slice" else 40
        items.append({**new_text_item(nice_name(fx)), "effect_in": fx, "effect_out": fx,
                      "speed_in": speed, "speed_out": speed, "pause": 700})
    for ov in overlays:
        if ov != "none":
            items.append({**new_text_item(nice_name(ov)), "effect_in": "print", "effect_out": "print",
                          "pause": 3500, "overlay": ov})
    return items
