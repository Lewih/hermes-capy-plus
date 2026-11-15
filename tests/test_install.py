"""Offline tests: run with  uv run --with pytest python -m pytest -q tests"""
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("capy_install", ROOT / "capy_install.py")
capy_install = importlib.util.module_from_spec(spec)
spec.loader.exec_module(capy_install)


def test_installs_then_noop_then_refreshes(tmp_path):
    dest, changed = capy_install.ensure_pet(tmp_path)
    assert changed and dest == tmp_path / "capy-plus"
    assert {p.name for p in dest.iterdir()} == {"pet.json", "spritesheet.webp"} | {
        capy_install.sheet_for(s) for s in capy_install.SEASONS}
    assert capy_install.ensure_pet(tmp_path) == (dest, False)
    (dest / "spritesheet.webp").write_bytes(b"stale")
    assert capy_install.ensure_pet(tmp_path)[1] is True
    assert capy_install.is_current(dest)
    assert not (tmp_path / ".capy-plus.staging").exists()


def test_sheet_geometry_matches_declared_rows():
    from PIL import Image

    meta = json.loads((ROOT / "pet" / "pet.json").read_text())
    with Image.open(ROOT / "pet" / "spritesheet.webp") as im:
        assert im.size == (192 * 8, 208 * len(meta["stateRows"]))
    assert meta["stateRows"][:9] == ["idle", "running-right", "running-left", "waving", "jumping",
                                      "failed", "waiting", "running", "review"]  # stock Hermes order kept
    assert meta["id"] == capy_install.SLUG == "capy-plus"


def test_behaviors_point_at_declared_rows():
    meta = json.loads((ROOT / "pet" / "pet.json").read_text())
    known = {"idle", "wave", "run", "failed", "review", "jump", "waiting", "sleep", "poke", "held", "fall", "land", "wake"}
    for state, spec in meta["behaviors"].items():
        assert state in known
        assert all(r in meta["stateRows"] for r in spec.get("rows", [spec.get("row")]))
    # running rows are reserved for actually roaming the window
    assert not ({"running", "running-left", "running-right"} & set(meta["behaviors"]["run"]["rows"]))
    assert meta["behaviors"]["sleep"]["afterSeconds"] > 0
    # desktop pointer interactions each get their own row
    assert {meta["behaviors"][k]["row"] for k in ("poke", "held", "fall", "land")} == {"poked", "held", "falling", "landing"}
    # poked while asleep: the tub wake-up, in the same yuzu costume as the nap (no hat intro)
    assert meta["behaviors"]["wake"]["row"] == "waking"
    assert {"onsen", "waking"} <= set(meta["costumes"]["yuzu"]["rows"])


def test_every_row_but_intros_wears_a_costume_with_an_intro():
    meta = json.loads((ROOT / "pet" / "pet.json").read_text())
    intros = {c["intro"] for c in meta["costumes"].values()}
    members = [r for c in meta["costumes"].values() for r in c["rows"]]
    assert len(members) == len(set(members))
    assert set(members) | intros == set(meta["stateRows"])
    assert intros <= set(meta["stateRows"]) and not (intros & set(members))


def test_season_for_boundaries():
    from datetime import date

    cases = {(10, 19): None, (10, 20): "halloween", (11, 2): "halloween", (11, 3): None, (11, 30): None,
             (12, 1): "winter", (12, 31): "winter", (1, 1): None, (6, 30): None, (7, 1): "summer",
             (8, 31): "summer", (9, 1): None}
    for (m, d), want in cases.items():
        assert capy_install.season_for(date(2026, m, d)) == want, (m, d)
    assert capy_install.resolve("off", date(2026, 12, 25)) is None
    assert capy_install.resolve("summer", date(2026, 12, 25)) == "summer"
    assert capy_install.resolve("auto", date(2026, 12, 25)) == "winter"


def test_apply_season_rewrites_only_the_sheet_path_and_is_idempotent(tmp_path):
    dest, _ = capy_install.ensure_pet(tmp_path)
    before = json.loads((dest / "pet.json").read_text())
    assert capy_install.apply_season(dest, "winter") is True
    after = json.loads((dest / "pet.json").read_text())
    assert after.pop("spritesheetPath") == "spritesheet-winter.webp"
    before.pop("spritesheetPath")
    assert after == before
    mtime = (dest / "pet.json").stat().st_mtime_ns
    assert capy_install.apply_season(dest, "winter") is False
    assert (dest / "pet.json").stat().st_mtime_ns == mtime
    assert not list(dest.glob(".*.tmp"))
    # the refresh-on-load must not fight the season...
    assert capy_install.is_current(dest) and capy_install.ensure_pet(tmp_path) == (dest, False)
    # ...and sync puts it back to the default top hat when seasons are off
    assert capy_install.sync(tmp_path, pref="off")[1:] == (True, None)
    assert json.loads((dest / "pet.json").read_text())["spritesheetPath"] == "spritesheet.webp"


def test_season_pref_roundtrip(tmp_path):
    path = tmp_path / "settings.json"
    assert capy_install.load_pref(path) == "auto"
    capy_install.save_pref("halloween", path)
    assert capy_install.load_pref(path) == "halloween"
    path.write_text("{oops")
    assert capy_install.load_pref(path) == "auto"


def test_every_season_ships_a_sheet_with_the_same_geometry():
    from PIL import Image

    pet = ROOT / "pet"
    with Image.open(pet / "spritesheet.webp") as im:
        size = im.size
    sheets = {p.name for p in pet.glob("spritesheet-*.webp")}
    assert sheets == {capy_install.sheet_for(s) for s in capy_install.SEASONS}
    assert set(capy_install.LOOKS) == {None, *capy_install.SEASONS}
    for name in sheets:
        with Image.open(pet / name) as im:
            assert im.size == size, name
