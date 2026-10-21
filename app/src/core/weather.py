"""Finding a place for the weather, with Open-Meteo's free place search.

The display fetches the weather itself (firmware/src/net/Weather.cpp); the app
only helps choose where, and shows what the display last read.
"""
import asyncio
import json
import urllib.parse
import urllib.request
from dataclasses import dataclass

from .updates import _SSL

SEARCH = "https://geocoding-api.open-meteo.com/v1/search"
MAX_PLACE = 39  # the display keeps 39 characters of the name


@dataclass
class Place:
    name: str
    region: str
    country: str
    lat: float
    lon: float

    @property
    def label(self) -> str:
        """Short, for the display's settings: "Burlington, Ontario"."""
        text = f"{self.name}, {self.region}" if self.region else self.name
        return text if len(text) <= MAX_PLACE else self.name[:MAX_PLACE]

    @property
    def full(self) -> str:
        """For the list of results: "Burlington, Ontario, Canada"."""
        return ", ".join(p for p in (self.name, self.region, self.country) if p)


def parse_places(data: dict) -> list[Place]:
    return [Place(r.get("name", ""), r.get("admin1", ""), r.get("country", ""),
                  round(float(r["latitude"]), 4), round(float(r["longitude"]), 4))
            for r in data.get("results") or [] if "latitude" in r and "longitude" in r]


async def search(name: str, count: int = 8) -> list[Place]:
    q = urllib.parse.urlencode({"name": name.strip(), "count": count, "language": "en", "format": "json"})

    def get():
        req = urllib.request.Request(f"{SEARCH}?{q}", headers={"User-Agent": "dotmatrix-app"})
        with urllib.request.urlopen(req, timeout=15, context=_SSL) as r:
            return json.loads(r.read())

    return parse_places(await asyncio.to_thread(get))


def describe(state_weather: dict | None) -> str:
    """'8°C, rain' from the display's state, or '' if it has no reading."""
    if not state_weather:
        return ""
    unit = "F" if state_weather.get("units") == "f" else "C"
    text = state_weather.get("text", "")
    t = state_weather.get("temp", 0)
    temp = int(abs(t) + 0.5) * (1 if t >= 0 else -1)  # halves away from zero, like the display
    return f"{temp}°{unit}" + (f", {text.lower()}" if text else "")
