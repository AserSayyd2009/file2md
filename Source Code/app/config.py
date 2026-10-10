"""
Application configuration and user preferences.

Stores settings as JSON in a per-user application data directory.
No database, no cloud, no telemetry.
"""

from __future__ import annotations

import json
import os
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


APP_NAME = "File2MD"
APP_VERSION = "1.0.0"


def get_app_data_dir() -> Path:
    """Return the per-user application data directory for File2MD.

    On Windows this is ``%APPDATA%\\\\File2MD`` (typically ``C:\\\\Users\\\\<user>\\\\AppData\\\\Roaming\\\\File2MD``).
    On macOS this is ``~/Library/Application Support/File2MD``.
    On Linux/other this is ``~/.config/file2md``.
    The directory is created if it does not exist.
    """
    if sys.platform == "win32":
        base = os.environ.get("APPDATA") or os.environ.get("LOCALAPPDATA")
        if base:
            path = Path(base) / APP_NAME
        else:
            path = Path.home() / "AppData" / "Roaming" / APP_NAME
    elif sys.platform == "darwin":
        path = Path.home() / "Library" / "Application Support" / APP_NAME
    else:
        xdg = os.environ.get("XDG_CONFIG_HOME")
        path = Path(xdg) / "file2md" if xdg else Path.home() / ".config" / "file2md"

    path.mkdir(parents=True, exist_ok=True)
    return path


def get_default_output_dir() -> Path:
    """Return a sensible default output directory next to the user's documents."""
    home = Path.home()
    if sys.platform == "win32":
        docs = Path.home() / "Documents"
    elif sys.platform == "darwin":
        docs = Path.home() / "Documents"
    else:
        docs = Path.home() / "Documents"
    return docs / "Markdown"


@dataclass
class Settings:
    """User preferences persisted across sessions."""

    output_directory: str = ""
    include_subfolders: bool = True
    preserve_structure: bool = False
    overwrite_existing: bool = False
    create_unique_filenames: bool = True
    last_input_dir: str = ""
    window_width: int = 760
    window_height: int = 720

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Settings":
        # Only keep known keys; ignore unknown ones from newer/older versions.
        known = {f for f in cls.__dataclass_fields__}  # type: ignore[attr-defined]
        clean = {k: v for k, v in (data or {}).items() if k in known}
        return cls(**clean)

    def resolve_output_dir(self) -> Path:
        """Return the configured output directory, or a valid default."""
        if self.output_directory:
            p = Path(self.output_directory)
            try:
                p.mkdir(parents=True, exist_ok=True)
                return p
            except OSError:
                pass
        d = get_default_output_dir()
        d.mkdir(parents=True, exist_ok=True)
        return d


class ConfigManager:
    """Load and save :class:`Settings` to a JSON file."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = path or (get_app_data_dir() / "settings.json")

    def load(self) -> Settings:
        if not self.path.exists():
            return Settings()
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            return Settings.from_dict(data)
        except (json.JSONDecodeError, OSError):
            # Corrupt or unreadable settings — start fresh.
            return Settings()

    def save(self, settings: Settings) -> bool:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(
                json.dumps(settings.to_dict(), indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
            return True
        except OSError:
            return False
