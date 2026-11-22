# SPDX-License-Identifier: GPL-3.0-or-later
"""Configuration file handling for the GOO CLI.

Two JSON files are read, later entries win:

``%APPDATA%/goo-port/config.json`` (Windows)
``~/Library/Application Support/goo-port/config.json`` (macOS)
``$XDG_CONFIG_HOME/goo-port/config.json`` or ``~/.config/goo-port/config.json``
    User wide defaults.
``./.goo/config.json``
    Per project overrides, relative to the current working directory.

Recognised keys::

    {
      "blender": "C:/Program Files/Blender Foundation/Blender 5.2/blender.exe",
      "addon_path": null,          # optional goo_npr parent directory
      "output_dir": "C:/renders",
      "samples": 32,
      "format": "exr",             # "exr" or "png"
      "resolution_percentage": 100
    }
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any, Optional

from .errors import ConfigError
from .util import json_dumps, read_json

CONFIG_DIRNAME = "goo-port"
LOCAL_DIRNAME = ".goo"
CONFIG_FILENAME = "config.json"

DEFAULTS: dict[str, Any] = {
    "blender": None,
    "addon_path": None,
    "output_dir": None,
    "samples": None,
    "format": "exr",
    "resolution_percentage": None,
}

KNOWN_KEYS = tuple(DEFAULTS)


def home_directory() -> Path:
    """Return the current user's home directory.

    Kept as a separate function so path portability can be unit tested with a
    fake home on any host platform.
    """
    return Path.home()


def user_config_path() -> Path:
    """Return the platform specific user configuration path."""
    if os.name == "nt":
        base = os.environ.get("APPDATA") or os.environ.get("LOCALAPPDATA")
        if base:
            return Path(base) / CONFIG_DIRNAME / CONFIG_FILENAME
        return home_directory() / "AppData" / "Roaming" / CONFIG_DIRNAME / CONFIG_FILENAME
    if sys.platform == "darwin":
        return home_directory() / "Library" / "Application Support" / CONFIG_DIRNAME / CONFIG_FILENAME
    xdg = os.environ.get("XDG_CONFIG_HOME")
    base = Path(xdg) if xdg else home_directory() / ".config"
    return base / CONFIG_DIRNAME / CONFIG_FILENAME


def local_config_path(cwd: Optional[os.PathLike[str] | str] = None) -> Path:
    return Path(cwd or os.getcwd()) / LOCAL_DIRNAME / CONFIG_FILENAME


def config_paths(cwd: Optional[os.PathLike[str] | str] = None) -> list[Path]:
    """All configuration files that are consulted, in priority order."""
    return [local_config_path(cwd), user_config_path()]


def load_config(cwd: Optional[os.PathLike[str] | str] = None) -> dict[str, Any]:
    """Load merged configuration (defaults + user + local).

    Malformed files raise :class:`ConfigError` instead of being silently
    ignored, so a typo never results in "Blender not found" confusion.
    """
    merged: dict[str, Any] = dict(DEFAULTS)
    for path in reversed(config_paths(cwd)):  # user first, local overrides
        if not path.is_file():
            continue
        try:
            with open(path, "r", encoding="utf-8-sig") as fh:
                data = json.load(fh)
        except OSError as exc:
            raise ConfigError(f"cannot read config file {path}: {exc}", hint="Fix the file permissions or delete it.")
        except ValueError as exc:
            raise ConfigError(
                f"config file {path} is not valid JSON: {exc}",
                hint="Fix the JSON syntax (a trailing comma is the usual culprit) / 请修复 JSON 语法",
            )
        if not isinstance(data, dict):
            raise ConfigError(f"config file {path} must contain a JSON object")
        for key, value in data.items():
            if key in KNOWN_KEYS:
                merged[key] = value
    return merged


def save_config(
    updates: dict[str, Any],
    *,
    scope: str = "user",
    cwd: Optional[os.PathLike[str] | str] = None,
) -> Path:
    """Merge *updates* into one config file and return its path."""
    if scope not in ("user", "local"):
        raise ConfigError(f"unknown config scope {scope!r}", hint="Use --scope user or --scope local")
    path = user_config_path() if scope == "user" else local_config_path(cwd)
    current = read_json(path) or {}
    for key, value in updates.items():
        if key not in KNOWN_KEYS:
            raise ConfigError(f"unknown config key {key!r}", hint=f"Known keys: {', '.join(KNOWN_KEYS)}")
        if value is None:
            current.pop(key, None)
        else:
            current[key] = value

    # never store paths that do not exist, to fail early and loudly later
    blender = current.get("blender")
    if blender and not Path(blender).is_file():
        raise ConfigError(
            f"cannot store blender path {blender!r}: file does not exist",
            hint="Pass the full path to blender.exe / 请给出 blender.exe 的完整路径",
        )
    addon_path = current.get("addon_path")
    if addon_path and not Path(addon_path).exists():
        raise ConfigError(f"cannot store addon_path {addon_path!r}: directory does not exist")

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(current, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def describe(config: Optional[dict[str, Any]] = None) -> str:
    cfg = config if config is not None else load_config()
    return json_dumps(cfg, ensure_ascii=False)
