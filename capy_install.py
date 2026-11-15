"""Copy the bundled pet into the active profile's pets dir and pick its seasonal sheet (no Hermes
imports at module level, so it is testable on its own)."""

from __future__ import annotations

import filecmp
import json
import os
import shutil
from datetime import date
from pathlib import Path

PET_SRC = Path(__file__).parent / "pet"
SLUG = json.loads((PET_SRC / "pet.json").read_text())["id"]
PLUGIN = "capy-plus"  # plugin.yaml name, keys the plugin-data dir

# Seasonal looks swap only the default top hat; every season ships pet/spritesheet-<name>.webp.
SEASONS = {  # name: (first (month, day), last (month, day)), inclusive
    "halloween": ((10, 20), (11, 2)),
    "winter": ((12, 1), (12, 31)),
    "summer": ((7, 1), (8, 31)),
}
LOOKS = {None: "top hat", "winter": "Santa hat", "halloween": "pumpkin hat", "summer": "straw sun hat + sunglasses"}
CHOICES = ("auto", "off", *SEASONS)


def default_pets_dir() -> Path:
    from hermes_constants import get_hermes_home  # public plugin API; profile-aware

    return get_hermes_home() / "pets"


def settings_path() -> Path:
    from plugins.plugin_storage import plugin_data_dir  # public plugin API: <HERMES_HOME>/plugin-data/<name>/

    return plugin_data_dir(PLUGIN) / "settings.json"


def _write_json(path: Path, data: dict) -> None:
    tmp = path.with_name(f".{path.name}.tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
    os.replace(tmp, path)  # atomic: readers see the old or the new file, never half of one


def load_pref(path: Path | None = None) -> str:
    try:
        pref = json.loads((path or settings_path()).read_text()).get("season", "auto")
    except (ImportError, OSError, ValueError, AttributeError):
        return "auto"
    return pref if pref in CHOICES else "auto"


def save_pref(pref: str, path: Path | None = None) -> None:
    if pref not in CHOICES:
        raise ValueError(f"season must be one of {', '.join(CHOICES)}")
    _write_json(path or settings_path(), {"season": pref})


def season_for(day: date) -> str | None:
    md = (day.month, day.day)
    return next((name for name, (first, last) in SEASONS.items() if first <= md <= last), None)


def resolve(pref: str, today: date | None = None) -> str | None:
    """The season to wear for a preference: auto = by date, off = never, else that season."""
    return pref if pref in SEASONS else None if pref == "off" else season_for(today or date.today())


def sheet_for(season: str | None) -> str:
    return f"spritesheet-{season}.webp" if season else "spritesheet.webp"


def apply_season(dest: Path, season: str | None) -> bool:
    """Point the installed pet.json at the season's sheet; rewrites only when it changes."""
    meta = json.loads((dest / "pet.json").read_text())
    if meta.get("spritesheetPath") == sheet_for(season):
        return False
    meta["spritesheetPath"] = sheet_for(season)
    _write_json(dest / "pet.json", meta)
    return True


def _same(src: Path, dst: Path) -> bool:
    if src.name != "pet.json":
        return filecmp.cmp(src, dst, shallow=False)
    strip = lambda p: {k: v for k, v in json.loads(p.read_text()).items() if k != "spritesheetPath"}  # noqa: E731
    try:
        return strip(src) == strip(dst)  # the season owns spritesheetPath
    except ValueError:
        return False


def is_current(dest: Path) -> bool:
    return dest.is_dir() and all((dest / f.name).is_file() and _same(f, dest / f.name) for f in PET_SRC.iterdir() if f.is_file())


def ensure_pet(pets_dir: Path | None = None, *, force: bool = False) -> tuple[Path, bool]:
    """Install/refresh the pet; returns ``(dest, changed)``. Staged + renamed so a crash never leaves half a pet."""
    root = pets_dir or default_pets_dir()
    dest = root / SLUG
    if not force and is_current(dest):
        return dest, False
    root.mkdir(parents=True, exist_ok=True)
    stage = root / f".{SLUG}.staging"
    shutil.rmtree(stage, ignore_errors=True)
    shutil.copytree(PET_SRC, stage)
    shutil.rmtree(dest, ignore_errors=True)
    stage.rename(dest)
    return dest, True


def sync(pets_dir: Path | None = None, *, force: bool = False, pref: str | None = None,
         today: date | None = None) -> tuple[Path, bool, str | None]:
    """ensure_pet + the preferred season's sheet; returns ``(dest, changed, season)``."""
    dest, changed = ensure_pet(pets_dir, force=force)
    season = resolve(pref or load_pref(), today)
    return dest, apply_season(dest, season) or changed, season
