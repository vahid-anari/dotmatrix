"""Choosing the display's location: one search that sets both its time zone and
where the weather comes from."""
import flet as ft

from core import weather
from core.timezones import posix_tz

from .widgets import muted


def location_changes(place: weather.Place) -> dict:
    """The settings a chosen place sends to the display: the weather's place
    (with its country, which picks the weather model) and, when the zone is
    known, the time zone."""
    changes = {"weather": {"place": place.label, "lat": place.lat, "lon": place.lon, "country": place.cc}}
    tz = posix_tz(place.tz)
    if tz:
        changes["timezone"] = tz
    return changes


def choose_place(app, on_pick):
    """Search by name; tapping a result closes the dialog and calls on_pick(place)."""
    query = ft.TextField(label="Town or city", autofocus=True, expand=True,
                         value=(app.device.settings.get("weather", {}).get("place") or "").split(",")[0])
    results = ft.Column(spacing=0, scroll=ft.ScrollMode.AUTO, height=300)
    note = muted("")

    def pick(place):
        app.page.pop_dialog()
        on_pick(place)

    async def find(ev=None):
        name = (query.value or "").strip()
        if len(name) < 2:
            return
        note.value = "Searching…"
        results.controls = []
        note.update()
        results.update()
        try:
            places = await weather.search(name)
        except Exception:  # noqa: BLE001 — offline
            note.value = "Couldn't search. Check the phone's internet connection."
            note.update()
            return
        note.value = "" if places else "Nothing found. Try another spelling."
        results.controls = [ft.ListTile(title=ft.Text(p.name), subtitle=ft.Text(p.full),
                                        on_click=lambda ev, p=p: pick(p)) for p in places]
        note.update()
        results.update()

    query.on_submit = find
    app.page.show_dialog(ft.AlertDialog(
        title=ft.Text("Where is the display?"),
        content=ft.Column([ft.Row([query, ft.IconButton(ft.Icons.SEARCH, on_click=find)]), note, results],
                          tight=True, width=360),
        actions=[ft.TextButton("Cancel", on_click=lambda ev: app.page.pop_dialog())]))
