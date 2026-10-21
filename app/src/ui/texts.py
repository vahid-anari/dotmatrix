"""Texts: groups → items → editor.

A group is a playlist kept on the phone. "Play" sends it to the display, which
stores it and keeps playing it on its own. Editing the group that is playing
updates the display straight away.
"""
import asyncio
import copy
import logging
import time

import flet as ft

from core import preview
from core.player import Player, is_exact
from core.device import DeviceError
from core.items import (ANIMATION_INFO, DEMO_NAME, is_sprite, new_animation_item, new_text_item, nice_name,
                        normalized, summary)

from .widgets import Debouncer, LabeledSlider, heading, led, muted, section

log = logging.getLogger(__name__)


def _text_dialog(app, title: str, value: str, action: str, on_ok, hint: str = "", after=None):
    """on_ok(text) returns an error message or None. `after` runs once the dialog
    has closed: navigate there, never inside on_ok, or the dialog stays behind
    on the screen you came from."""
    field = ft.TextField(value=value, autofocus=True, hint_text=hint, max_length=32,
                         on_submit=lambda e: done(e))

    succeeded = []

    def done(e):
        err = on_ok(field.value or "")
        if err:
            field.error = err
            field.update()
            return
        succeeded.append(True)
        app.page.pop_dialog()

    def dismissed(e):
        # Only now is the dialog really gone (it closes with an animation).
        if succeeded and after:
            after()

    app.page.show_dialog(ft.AlertDialog(
        title=ft.Text(title), content=field, on_dismiss=dismissed,
        actions=[ft.TextButton("Cancel", on_click=lambda e: app.page.pop_dialog()),
                 ft.FilledButton(action, on_click=done)]))


def _confirm(app, title: str, body: str, action: str, on_yes):
    def yes(e):
        app.page.pop_dialog()
        on_yes()

    app.page.show_dialog(ft.AlertDialog(
        title=ft.Text(title), content=ft.Text(body),
        actions=[ft.TextButton("Cancel", on_click=lambda e: app.page.pop_dialog()),
                 ft.FilledButton(action, on_click=yes)]))


def _count(n: int) -> str:
    return "No items" if n == 0 else ("1 item" if n == 1 else f"{n} items")


# ============================================================= group list tab

class TextsTab:
    def __init__(self, app):
        self.app = app
        self.list = ft.Column(spacing=10)
        self.view = ft.Column([
            ft.Row([heading("Texts"),
                    ft.FilledButton("New group", icon=ft.Icons.ADD, on_click=self._new_group)],
                   alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            muted("Each group is a playlist. Play one to send it to the display; "
                  "it keeps playing even when your phone is away."),
            self.list,
        ], spacing=14, scroll=ft.ScrollMode.AUTO, expand=True)
        self.refresh()

    def refresh(self):
        lib, p = self.app.library, self.app.palette()
        playing = self.app.active_group() if self.app.device.state.get("mode") == "text" else None
        rows = []
        for g in lib.groups:
            is_playing = g is playing
            first = g["items"][0] if g["items"] else new_text_item("")
            title = ft.Row([ft.Text(g["name"], size=17, weight=ft.FontWeight.W_600)], spacing=8)
            if is_playing:
                title.controls.append(ft.Container(ft.Text("Playing", size=12, color="#1D1600"),
                                                   bgcolor=p["gold"], border_radius=6,
                                                   padding=ft.Padding.symmetric(horizontal=7, vertical=1)))
            rows.append(ft.Container(
                content=ft.Column([
                    ft.Row([ft.Column([title, muted(_count(len(g["items"])))], spacing=0, expand=True),
                            ft.IconButton(ft.Icons.PLAY_ARROW, tooltip="Play on the display",
                                          on_click=lambda e, g=g: self.play(g)),
                            self._menu(g)]),
                    led_strip(first, 40),
                ], spacing=8, horizontal_alignment=ft.CrossAxisAlignment.STRETCH),
                bgcolor=ft.Colors.SURFACE_CONTAINER_LOWEST, border_radius=14, padding=ft.Padding.only(left=14, right=6, top=8, bottom=12),
                border=ft.Border.all(2, p["gold"]) if is_playing else ft.Border.all(1, p["line"]),
                on_click=lambda e, g=g: self.open(g),
            ))
        self.list.controls = rows

    def _menu(self, g):
        items = [ft.PopupMenuItem("Rename", icon=ft.Icons.EDIT, on_click=lambda e: self.rename(g)),
                 ft.PopupMenuItem("Duplicate", icon=ft.Icons.COPY, on_click=lambda e: self.duplicate(g))]
        if g["name"] == DEMO_NAME:
            items.append(ft.PopupMenuItem("Restore demo", icon=ft.Icons.RESTORE, on_click=lambda e: self.restore_demo()))
        else:
            items.append(ft.PopupMenuItem("Delete", icon=ft.Icons.DELETE_OUTLINE, on_click=lambda e: self.delete(g)))
        return ft.PopupMenuButton(items=items, icon=ft.Icons.MORE_VERT)

    # --------------------------------------------------------------- actions
    def open(self, g):
        GroupScreen(self.app, g).show()

    def play(self, g):
        if not self.app.need_device():
            return
        if not g["items"]:
            self.app.toast("This group is empty. Add an item first.")
            return
        if len(g["items"]) > self.app.device.max_items:
            self.app.toast(f"The display holds up to {self.app.device.max_items} items.")
            return
        self.app.run(self.app.device.play_group, g["name"], g["items"], ok=f"Playing “{g['name']}”")

    def _new_group(self, e):
        created = []

        def ok(name):
            created.append(self.app.library.add_group(name or "New group"))
            self.app.refresh()

        _text_dialog(self.app, "New group", "", "Create", ok, hint="e.g. Kitchen",
                     after=lambda: self.open(created[0]))

    def rename(self, g):
        old = g["name"]

        def ok(name):
            err = self.app.library.rename_group(g, name)
            if not err:
                self.app.sync_renamed(old, g)
                self.app.refresh()
            return err

        _text_dialog(self.app, "Rename group", g["name"], "Rename", ok)

    def duplicate(self, g):
        self.app.library.duplicate_group(g)
        self.app.refresh()

    def delete(self, g):
        def yes():
            self.app.library.delete_group(g)
            self.app.refresh()

        _confirm(self.app, f"Delete “{g['name']}”?",
                 "The group is removed from this phone. If the display is playing it, it keeps playing.",
                 "Delete", yes)

    def restore_demo(self):
        def yes():
            d = self.app.device
            self.app.library.restore_demo(d.effects, d.animations, d.overlays)
            self.app.refresh()

        _confirm(self.app, "Restore the demo?", "The Demo group goes back to one item per effect and animation.", "Restore", yes)


def led_strip(item: dict, height: int) -> ft.Container:
    return led(preview.render_item(item), height=height, radius=8)


# ================================================================ group view

class GroupScreen:
    def __init__(self, app, group: dict):
        self.app, self.group = app, group
        self.title = ft.Text(group["name"])
        self.items = ft.ReorderableListView(on_reorder=self._reordered, spacing=8,
                                            show_default_drag_handles=False, expand=True)
        self.empty = ft.Container(muted("No items yet. Add a text, or an animation like Matrix rain."),
                                  padding=ft.Padding.symmetric(vertical=24))
        self.view = ft.View(
            route="/group",
            appbar=ft.AppBar(title=self.title, actions=[
                ft.IconButton(ft.Icons.PLAY_ARROW, tooltip="Play on the display", on_click=self._play),
                ft.PopupMenuButton(icon=ft.Icons.MORE_VERT, items=[
                    ft.PopupMenuItem("Rename", icon=ft.Icons.EDIT, on_click=self._rename)]),
            ]),
            controls=[
                ft.Row([ft.FilledButton("Add text", icon=ft.Icons.TEXT_FIELDS, on_click=self._add_text),
                        ft.OutlinedButton("Add animation", icon=ft.Icons.GRAIN, on_click=self._add_anim)],
                       spacing=10),
                self.empty,
                self.items,
            ],
            padding=16, spacing=12,
        )
        self.refresh()

    def show(self):
        self.app.push(self.view, self)

    def refresh(self):
        p = self.app.palette()
        self.title.value = self.group["name"]
        self.empty.visible = not self.group["items"]
        rows = []
        for i, it in enumerate(self.group["items"]):
            label = it.get("text") or nice_name(it.get("animation", ""))
            rows.append(ft.Container(
                key=f"{i}",
                content=ft.Row([
                    ft.ReorderableDragHandle(ft.Icon(ft.Icons.DRAG_INDICATOR, color=ft.Colors.ON_SURFACE_VARIANT)),
                    ft.Column([
                        led_strip(it, 34),
                        ft.Column([ft.Text(label, size=15, weight=ft.FontWeight.W_500,
                                           max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
                                   ft.Text(summary(it), size=12, color=ft.Colors.ON_SURFACE_VARIANT,
                                           max_lines=1, overflow=ft.TextOverflow.ELLIPSIS)], spacing=0),
                    ], spacing=6, expand=True, horizontal_alignment=ft.CrossAxisAlignment.STRETCH),
                    ft.PopupMenuButton(icon=ft.Icons.MORE_VERT, items=[
                        ft.PopupMenuItem("Duplicate", icon=ft.Icons.COPY, on_click=lambda e, i=i: self._duplicate(i)),
                        ft.PopupMenuItem("Delete", icon=ft.Icons.DELETE_OUTLINE, on_click=lambda e, i=i: self._delete(i)),
                    ]),
                ], spacing=4),
                bgcolor=ft.Colors.SURFACE_CONTAINER_LOWEST, border_radius=12, border=ft.Border.all(1, p["line"]),
                padding=ft.Padding.only(left=2, right=0, top=8, bottom=8),
                on_click=lambda e, i=i: self._edit(i),
            ))
        self.items.controls = rows

    def changed(self):
        self.app.library.save()
        self.app.sync_if_active(self.group)
        self.app.refresh()

    # --------------------------------------------------------------- actions
    def _reordered(self, e):
        items = self.group["items"]
        old, new = e.old_index, e.new_index
        if old is None or new is None or old == new:
            return
        if new > old:
            new -= 1  # Flutter reports the index before removal
        items.insert(new, items.pop(old))
        self.changed()

    def _edit(self, i):
        EditorScreen(self.app, self, i).show()

    def _add_text(self, e):
        if self._full():
            return
        EditorScreen(self.app, self, None, new_text_item("Hello")).show()

    def _add_anim(self, e):
        if self._full():
            return
        EditorScreen(self.app, self, None, new_animation_item("matrix_reveal", "Hello")).show()

    def _full(self) -> bool:
        if len(self.group["items"]) >= self.app.device.max_items:
            self.app.toast(f"A group can hold up to {self.app.device.max_items} items.")
            return True
        return False

    def _duplicate(self, i):
        if self._full():
            return
        self.group["items"].insert(i + 1, copy.deepcopy(self.group["items"][i]))
        self.changed()

    def _delete(self, i):
        self.group["items"].pop(i)
        self.changed()

    def _play(self, e):
        TextsTab.play(self, self.group)  # same checks as the list

    def _rename(self, e):
        TextsTab.rename(self, self.group)


# =================================================================== editor

class EditorScreen:
    """Edits one item. Changes show live on the display while editing."""

    def __init__(self, app, group_screen: GroupScreen, index: int | None, new_item: dict | None = None):
        self.app, self.gs, self.index = app, group_screen, index
        src = new_item if index is None else group_screen.group["items"][index]
        self.item = normalized(src)
        self.is_anim = self.item.get("type") == "animation"
        self._live_on = False
        self._send_preview = Debouncer(app.page, 0.25, self._preview_now)

        self.led = led(preview.render_item(self.item), radius=12)
        # The LED plays the item over and over, like the display will.
        self.player = Player(self.item)
        self._t0 = time.monotonic()
        self._anim_task = None
        self.preview_note = muted("")
        self._update_note()
        self.live = ft.Switch(label="Show on the display while editing",
                              value=app.library.prefs.get("live_preview", True), on_change=self._live_toggled)
        self.text = ft.TextField(label="Text", value=self.item.get("text", ""),
                                 max_length=app.device.max_text, on_change=lambda e: self.set("text", e.control.value))
        self.view = ft.View(
            route="/group/edit",
            appbar=ft.AppBar(title=ft.Text("Animation" if self.is_anim else "Text"), actions=[
                ft.TextButton("Done", icon=ft.Icons.CHECK, on_click=lambda e: self.app.pop())]),
            # The LED stays pinned at the top so every change is visible while scrolling.
            controls=[ft.Column([self.led, self.preview_note], spacing=4),
                      ft.Column([self.live, *self._fields(), ft.Container(height=24)], spacing=18,
                                scroll=ft.ScrollMode.AUTO, expand=True,
                                horizontal_alignment=ft.CrossAxisAlignment.STRETCH)],
            padding=16, spacing=14,
        )

    # ------------------------------------------------------------- fields
    def _dropdown(self, label, key, options):
        return ft.Dropdown(label=label, value=self.item.get(key), expand=True, menu_height=420,
                           options=[ft.DropdownOption(key=o, text=nice_name(o) + ("  (sprite)" if is_sprite(o) else ""))
                                    for o in options],
                           on_select=lambda e: self.set(key, e.control.value))

    def _slider(self, label, key, lo, hi, step, fmt, scale=1.0):
        return LabeledSlider(label, self.item.get(key, lo) / scale, lo, hi, step, fmt,
                             lambda v: self.set(key, int(round(v * scale))))

    def _align(self):
        return ft.SegmentedButton(
            segments=[ft.Segment(value=v, label=v.capitalize()) for v in ("left", "center", "right")],
            selected=[self.item.get("align", "center")], show_selected_icon=False,
            on_change=lambda e: self.set("align", next(iter(e.control.selected), "center")))

    def _looks(self):
        own = self.item.get("brightness") is not None
        bright = self._slider("Brightness", "brightness", 0, 15, 1, lambda v: f"{int(v)} of 15")
        bright.visible = own
        if not own:
            bright.set(self.app.device.settings.get("brightness", 6))

        def toggle(e):
            bright.visible = e.control.value
            self.set("brightness", int(bright.slider.value) if e.control.value else None)
            bright.update()

        return section("Look",
                       ft.Column([muted("Alignment", 14), self._align()], spacing=6),
                       ft.Switch(label="Invert (dark text on lit background)", value=bool(self.item.get("invert")),
                                 on_change=lambda e: self.set("invert", e.control.value)),
                       ft.Switch(label="Own brightness for this item", value=own, on_change=toggle),
                       bright)

    def _fields(self):
        d = self.app.device
        secs = lambda v: f"{v:g} s"  # noqa: E731
        ms = lambda v: f"{int(v)} ms per step"  # noqa: E731
        if self.is_anim:
            dd = self._dropdown("Animation", "animation", d.animations)
            dd.on_select = self._animation_changed
            self.anim_settings = ft.Column(self._animation_settings(), spacing=10)
            return [
                section("Animation", dd, self.text),
                section("Timing",
                        self._slider("Runs for", "duration", 2, 60, 1, secs, scale=1000),
                        self._slider("Blank before the next item", "gap", 0, 3, 0.1, secs, scale=1000)),
                section("Settings", self.anim_settings, note="Lower speed values move faster."),
                self._looks(),
            ]
        return [
            self.text,
            section("Movement",
                    ft.Row([self._dropdown("Comes in with", "effect_in", d.effects)]),
                    self._slider("Entry speed", "speed_in", 5, 150, 5, ms),
                    ft.Row([self._dropdown("Leaves with", "effect_out", d.effects)]),
                    self._slider("Exit speed", "speed_out", 5, 150, 5, ms),
                    note="Lower values move faster."),
            section("Timing",
                    self._slider("Stays still for", "pause", 0, 10, 0.1, secs, scale=1000),
                    self._slider("Blank before the next item", "gap", 0, 3, 0.1, secs, scale=1000)),
            *([section("While it stays", ft.Row([self._dropdown("Effect", "overlay", d.overlays)]),
                       note="Plays over the text while it stays still (when it fits on the display).")]
              if len(d.overlays) > 1 else []),
            self._looks(),
        ]

    def _animation_settings(self) -> list[ft.Control]:
        """The sliders and pickers that the chosen animation uses."""
        anim = self.item.get("animation", "matrix_rain")
        info = ANIMATION_INFO.get(anim, {})
        params = self.item.setdefault("params", {})
        self.text.visible = bool(info.get("text"))
        out = []
        if "density" in info:
            label, lo, hi, default = info["density"]
            out.append(LabeledSlider(label, params.get("density", default), lo, hi, 1, lambda v: f"{int(v)}",
                                     lambda v: self._param("density", int(v))))
        if info.get("sprite"):
            sprites = self.app.device.sprites
            out.append(ft.Dropdown(label="Sprite", value=params.get("sprite", sprites[0]), menu_height=420,
                                   options=[ft.DropdownOption(key=s, text=nice_name(s)) for s in sprites],
                                   on_select=lambda e: self._param("sprite", e.control.value)))
        speed = info.get("speed", 50)
        out.append(LabeledSlider("Speed", params.get("speed", speed), max(10, speed // 3), speed * 3, 5,
                                 lambda v: f"{int(v)} ms per frame", lambda v: self._param("speed", int(v))))
        return out

    def _animation_changed(self, e):
        # Settings mean different things per animation, so they start fresh.
        self.item["params"] = {}
        self.set("animation", e.control.value)
        self.anim_settings.controls = self._animation_settings()
        self.anim_settings.update()
        self.text.update()

    # -------------------------------------------------------------- updates
    def set(self, key, value):
        if value is None:
            self.item.pop(key, None)
        else:
            self.item[key] = value
        self.player = Player(self.item)  # start the preview again, with the change
        self._t0 = time.monotonic()
        self._update_note()
        self._save()
        if self.live.value:
            self._send_preview()

    def _param(self, key, value):
        self.item.setdefault("params", {})[key] = value
        self.set("params", self.item["params"])

    def _save(self):
        """Every change is kept; there's nothing to lose by going back."""
        items = self.gs.group["items"]
        if self.index is None:
            items.append(copy.deepcopy(self.item))
            self.index = len(items) - 1
        else:
            items[self.index] = copy.deepcopy(self.item)
        self.app.library.save()

    async def _preview_now(self):
        if not (self.app.device.connected and self.live.value):
            return
        try:
            await self.app.device.request("preview", item=self.item)
            self._live_on = True
        except DeviceError as ex:
            self.app.toast(f"Preview: {ex}")

    def _live_toggled(self, e):
        self.app.library.prefs["live_preview"] = e.control.value
        self.app.library.save()
        if e.control.value:
            self._send_preview()
        elif self._live_on:
            self._live_on = False
            self.app.device.send("preview_end")

    def _update_note(self):
        rough = [] if self.is_anim else list(dict.fromkeys(
            nice_name(e) for e in (self.item.get("effect_in"), self.item.get("effect_out"))
            if e and not is_exact(e)))
        self.preview_note.value = (f"The preview shows {' and '.join(rough)} only roughly; "
                                   "the display shows it exactly.") if rough else ""
        self.preview_note.visible = bool(rough)
        try:
            self.preview_note.update()
        except RuntimeError:  # not on screen yet
            pass

    async def _animate(self):
        """About 25 frames a second while the editor is open."""
        while True:
            t = int((time.monotonic() - self._t0) * 1000)
            try:
                cols, level = self.player.frame(t)
                self.led.content.src = preview.render_frame(cols, level)
            except Exception:  # noqa: BLE001 — a preview bug mustn't stop the editor
                log.exception("preview frame failed")
                await asyncio.sleep(1)
                continue
            try:
                self.led.update()
            except RuntimeError:  # the view is gone
                return
            await asyncio.sleep(0.04)

    def show(self):
        self.app.push(self.view, self)
        self._anim_task = self.app.page.run_task(self._animate)
        if self.index is None:
            self._save()  # a new item exists as soon as its editor opens
        if self.live.value:
            self._send_preview()

    def on_close(self):
        if self._anim_task:
            self._anim_task.cancel()
            self._anim_task = None
        if self._live_on:
            self.app.device.send("preview_end")
        self.gs.changed()

    def refresh(self):
        pass
