"""Capy Plus — Hermes plugin.

On load it makes sure the pet sprite is in ``<HERMES_HOME>/pets/capy-plus`` (and refreshes it
after ``hermes plugins update``), wearing the seasonal hat for today's date (``hermes capy season``). It adds ``hermes capy …`` and ``/capy``. The speech-bubble
reactions live in ``desktop/plugin.js``.
"""

from __future__ import annotations

import logging
import random

from . import capy_install

logger = logging.getLogger(__name__)

LINES = ["*munch munch*", "cache hit!", "all chill here", "squeak", "we vibe", "patience is a build step"]


def _select() -> str:
    from hermes_cli.config import load_config, save_config

    capy_install.sync()
    cfg = load_config()
    pet = cfg.setdefault("display", {}).setdefault("pet", {})
    pet.update(slug=capy_install.SLUG, enabled=True)
    save_config(cfg)
    return f"Capy Plus is now your pet (display.pet.slug={capy_install.SLUG})."


def _status() -> str:
    from hermes_cli.config import load_config

    dest = capy_install.default_pets_dir() / capy_install.SLUG
    pet = (load_config().get("display") or {}).get("pet") or {}
    active = pet.get("slug") == capy_install.SLUG and bool(pet.get("enabled"))
    return "\n".join([
        f"installed: {'yes' if capy_install.is_current(dest) else 'no / outdated'} ({dest})",
        f"active:    {'yes' if active else 'no — run: hermes capy select'}",
        _season_line(),
    ])


def _season_line() -> str:
    pref = capy_install.load_pref()
    look = capy_install.LOOKS[capy_install.resolve(pref)]
    return f"season:    {pref} — wearing the {look} (hermes capy season {'|'.join(capy_install.CHOICES)})"


def _season(choice: str | None = None) -> str:
    if choice:
        if choice not in capy_install.CHOICES:
            return f"unknown season {choice!r}; pick one of: {', '.join(capy_install.CHOICES)}"
        capy_install.save_pref(choice)
        capy_install.sync()
    return _season_line()


def _cli(args) -> None:
    sub = getattr(args, "capy_command", None) or "status"
    if sub == "select":
        print(_select())
    elif sub == "install":
        dest, changed, _ = capy_install.sync(force=True)
        print(f"{'installed' if changed else 'up to date'}: {dest}")
    elif sub == "say":
        print(f"🦫 {random.choice(LINES)}")
    elif sub == "season":
        print(_season(getattr(args, "choice", None)))
    else:
        print(_status())


def _setup(parser) -> None:
    subs = parser.add_subparsers(dest="capy_command")
    subs.add_parser("select", help="Install (if needed) and make Capy Plus the active pet")
    subs.add_parser("install", help="Reinstall the pet files")
    subs.add_parser("status", help="Show install / active state")
    subs.add_parser("say", help="Ask the capybara for wisdom")
    season = subs.add_parser("season", help="Seasonal hat: auto (by date, default), off, or a fixed season")
    season.add_argument("choice", nargs="?", choices=capy_install.CHOICES, help="omit to show the current look")
    parser.set_defaults(func=_cli)


def _slash(raw: str) -> str:
    arg = (raw or "").strip()
    if arg.split()[:1] == ["season"]:
        return _season((arg.split()[1:] or [None])[0])
    if arg == "select":
        return _select()
    if arg == "status":
        return _status()
    return f"🦫 {random.choice(LINES)}"


def register(ctx) -> None:
    try:
        dest, changed, season = capy_install.sync()  # refresh + today's seasonal hat (per `hermes capy season`)
        if changed:
            logger.info("capy-plus: pet installed/updated at %s (season: %s)", dest, season or "none")
    except Exception as exc:  # never break Hermes over a mascot
        logger.warning("capy-plus: could not install pet: %s", exc)
    ctx.register_cli_command(name="capy", help="Capy Plus pet", setup_fn=_setup, handler_fn=_cli)
    ctx.register_command("capy", handler=_slash, description="Capy Plus: /capy [select|status|season [auto|off|winter|halloween|summer]]")
