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
    "sprite_hourglass",
]
DEFAULT_ANIMATIONS = ["matrix_rain", "matrix_reveal"]

_NAMES = {
    "no_effect": "None", "scan_horiz_x": "Scan horizontal X", "scan_horiz": "Scan horizontal",
    "scan_vert_x": "Scan vertical X", "scan_vert": "Scan vertical",
    "sprite_pacman2": "Pacman & ghost", "sprite_arrow2": "Arrow (outward)",
    "sprite_invader": "Space invader", "sprite_walker": "Walking man", "sprite_heart": "Beating heart",
    "matrix_rain": "Matrix rain", "matrix_reveal": "Matrix reveal",
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
        "align": "center", "invert": False,
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
    return f"{fx}, stays {item.get('pause', 400) / 1000:g} s"


DEMO_NAME = "Demo"


def demo_items(effects: list[str] = DEFAULT_EFFECTS, animations: list[str] = DEFAULT_ANIMATIONS) -> list[dict]:
    """One item per animation, then one per effect (like the old app's Demo)."""
    items = []
    if "matrix_reveal" in animations:
        items.append({**new_animation_item("matrix_reveal", "DEMO"), "duration": 8000})
    if "matrix_rain" in animations:
        items.append({**new_animation_item("matrix_rain", ""), "duration": 5000})
    for fx in effects:
        if fx == "no_effect":
            continue
        speed = 10 if fx == "slice" else 40
        items.append({**new_text_item(nice_name(fx)), "effect_in": fx, "effect_out": fx,
                      "speed_in": speed, "speed_out": speed, "pause": 700})
    return items
