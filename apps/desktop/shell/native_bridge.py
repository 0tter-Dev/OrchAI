"""Native OS integration exposed to the frontend as pywebview's `js_api`.

Keeps "recent projects" as shell-local state (ADR-017 §5) -- it is a UI
convenience, not backend/domain state, so it lives in a plain JSON file
under the per-user app data directory rather than a database table.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

import webview

from apps.desktop.shell.server_runner import app_data_dir

_RECENT_PROJECTS_LIMIT = 10


def _recent_projects_path() -> Path:
    return app_data_dir() / "recent_projects.json"


def _read_recent_projects() -> list[dict[str, Any]]:
    path = _recent_projects_path()
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []
    return data if isinstance(data, list) else []


def _write_recent_projects(entries: list[dict[str, Any]]) -> None:
    _recent_projects_path().write_text(
        json.dumps(entries, indent=2), encoding="utf-8"
    )


class NativeBridge:
    """Methods callable from the frontend via `window.pywebview.api.*`.

    `window` is set by `main.py` right after the window is created --
    `create_file_dialog` is a method on the `Window` instance, not a
    module-level function.
    """

    def __init__(self) -> None:
        self.window: webview.Window | None = None

    def pick_folder(self) -> str | None:
        """Open a native folder picker; return the chosen path, or None."""

        if self.window is None:
            return None
        result = self.window.create_file_dialog(webview.FOLDER_DIALOG)
        if not result:
            return None
        return result[0]

    def list_recent_projects(self) -> list[dict[str, Any]]:
        """Return recent projects, most recently opened first."""

        return _read_recent_projects()

    def add_recent_project(self, path: str, name: str) -> list[dict[str, Any]]:
        """Record `path` as just-opened; return the updated list."""

        entries = [entry for entry in _read_recent_projects() if entry.get("path") != path]
        entries.insert(0, {"path": path, "name": name, "last_opened": time.time()})
        entries = entries[:_RECENT_PROJECTS_LIMIT]
        _write_recent_projects(entries)
        return entries
