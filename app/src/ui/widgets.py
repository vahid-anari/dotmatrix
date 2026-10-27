"""Small building blocks shared by the screens."""
import asyncio
from typing import Callable

import flet as ft

from core import preview



def led(png: bytes, height: int | None = None, radius: int = 10) -> ft.Container:
    """The LED strip: the one bold element in the app."""
    return ft.Container(
        content=ft.Image(src=png, fit=ft.BoxFit.CONTAIN, filter_quality=ft.FilterQuality.MEDIUM,
                         gapless_playback=True),
        bgcolor=preview.bg_hex(), padding=ft.Padding.symmetric(horizontal=8, vertical=8 if height is None else 5),
        border_radius=radius, height=height,
    )


def led_item(item: dict, height: int | None = None) -> ft.Container:
    return led(preview.render_item(item), height)


BOTTOM_ROOM = 96  # every scrolling list ends with this much room, so the last row clears the bar


def bottom_room() -> ft.Container:
    return ft.Container(height=BOTTOM_ROOM)


def section(title: str, *controls: ft.Control, note: str | None = None) -> ft.Column:
    head = [ft.Text(title, size=15, weight=ft.FontWeight.W_600)]
    if note:
        head.append(ft.Text(note, size=13, color=ft.Colors.ON_SURFACE_VARIANT))
    return ft.Column([ft.Column(head, spacing=2), *controls], spacing=10)


def muted(text: str, size: int = 13) -> ft.Text:
    return ft.Text(text, size=size, color=ft.Colors.ON_SURFACE_VARIANT)


class LabeledSlider(ft.Column):
    """A slider with its label and current value on one line above it."""

    def __init__(self, label: str, value: float, lo: float, hi: float, step: float,
                 fmt: Callable[[float], str], on_change: Callable[[float], None], on_release=None):
        self._fmt = fmt
        self._on_change = on_change
        self.value_text = ft.Text(fmt(value), size=14, color=ft.Colors.ON_SURFACE_VARIANT)
        self.slider = ft.Slider(min=lo, max=hi, value=max(lo, min(hi, value)),
                                divisions=max(1, round((hi - lo) / step)),
                                on_change=self._changed, on_change_end=on_release, padding=0)
        super().__init__([
            ft.Row([ft.Text(label, size=14), self.value_text], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            self.slider,
        ], spacing=2)

    def _changed(self, e):
        v = e.control.value
        self.value_text.value = self._fmt(v)
        self.value_text.update()
        self._on_change(v)

    def set(self, value: float):
        self.slider.value = max(self.slider.min, min(self.slider.max, value))
        self.value_text.value = self._fmt(self.slider.value)


class Debouncer:
    """Run an async function once things have been quiet for `delay` seconds."""

    def __init__(self, page: ft.Page, delay: float, fn):
        self.page, self.delay, self.fn = page, delay, fn
        self._task = None

    def __call__(self, *args):
        if self._task and not self._task.done():
            self._task.cancel()
        self._task = self.page.run_task(self._later, *args)

    async def _later(self, *args):
        await asyncio.sleep(self.delay)
        await self.fn(*args)


def status_dot(color: str) -> ft.Container:
    return ft.Container(width=9, height=9, border_radius=5, bgcolor=color)
