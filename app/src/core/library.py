"""The phone's library of groups, plus app preferences, in one JSON file.

The file lives in the app's private storage (FLET_APP_STORAGE_DATA), so it
survives app updates. Writes go to a temp file first, then replace.
"""
import copy
import json
import os
from pathlib import Path

from .items import DEFAULT_ANIMATIONS, DEFAULT_EFFECTS, DEFAULT_OVERLAYS, DEMO_NAME, demo_items

FILE_VERSION = 1


def _storage_dir() -> Path:
    d = os.getenv("FLET_APP_STORAGE_DATA")
    path = Path(d) if d else Path(__file__).resolve().parent.parent / "storage"
    path.mkdir(parents=True, exist_ok=True)
    return path


class Library:
    def __init__(self, path: Path | None = None):
        self.path = path or _storage_dir() / "library.json"
        self.groups: list[dict] = []  # [{"name": str, "items": [item, ...]}]
        self.prefs: dict = {"host": "", "live_preview": True}
        self._load()

    # ------------------------------------------------------------ persistence
    def _load(self):
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            self.groups = [g for g in data.get("groups", []) if isinstance(g, dict) and "name" in g]
            for g in self.groups:
                g.setdefault("items", [])
            self.prefs.update(data.get("prefs", {}))
        except (OSError, ValueError):
            pass
        if not self.find(DEMO_NAME):
            self.groups.insert(0, {"name": DEMO_NAME, "items": demo_items()})
            self.save()

    def save(self):
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps({"version": FILE_VERSION, "groups": self.groups, "prefs": self.prefs},
                                  ensure_ascii=False, indent=1), encoding="utf-8")
        os.replace(tmp, self.path)

    # ----------------------------------------------------------------- groups
    def find(self, name: str) -> dict | None:
        return next((g for g in self.groups if g["name"] == name), None)

    def names(self) -> list[str]:
        return [g["name"] for g in self.groups]

    def unique_name(self, base: str) -> str:
        if not self.find(base):
            return base
        n = 2
        while self.find(f"{base} {n}"):
            n += 1
        return f"{base} {n}"

    def add_group(self, name: str) -> dict:
        g = {"name": self.unique_name(name.strip() or "Group"), "items": []}
        self.groups.append(g)
        self.save()
        return g

    def rename_group(self, group: dict, new_name: str) -> str | None:
        """Returns an error message, or None on success."""
        new_name = new_name.strip()
        if not new_name:
            return "The name can't be empty."
        if new_name != group["name"] and self.find(new_name):
            return "A group with this name already exists."
        group["name"] = new_name
        self.save()
        return None

    def duplicate_group(self, group: dict) -> dict:
        g = {"name": self.unique_name(group["name"] + " copy"), "items": copy.deepcopy(group["items"])}
        self.groups.insert(self.groups.index(group) + 1, g)
        self.save()
        return g

    def delete_group(self, group: dict):
        self.groups.remove(group)
        self.save()

    def restore_demo(self, effects: list[str] | None = None, animations: list[str] | None = None,
                     overlays: list[str] | None = None):
        g = self.find(DEMO_NAME)
        items = demo_items(effects or DEFAULT_EFFECTS, animations or DEFAULT_ANIMATIONS,
                           overlays or DEFAULT_OVERLAYS)
        if g:
            g["items"] = items
        else:
            self.groups.insert(0, {"name": DEMO_NAME, "items": items})
        self.save()

    # ----------------------------------------------------------- import/export
    def export_bytes(self) -> bytes:
        return json.dumps({"format": "dotmatrix-library", "version": FILE_VERSION, "groups": self.groups},
                          ensure_ascii=False, indent=1).encode("utf-8")

    def import_bytes(self, data: bytes) -> int:
        """Merge groups from an exported file; returns how many were added."""
        doc = json.loads(data.decode("utf-8"))
        if doc.get("format") != "dotmatrix-library":
            raise ValueError("This isn't a Dot Matrix library file.")
        added = 0
        for g in doc.get("groups", []):
            if not isinstance(g, dict) or not isinstance(g.get("items"), list):
                continue
            self.groups.append({"name": self.unique_name(str(g.get("name", "Imported"))), "items": g["items"]})
            added += 1
        self.save()
        return added
