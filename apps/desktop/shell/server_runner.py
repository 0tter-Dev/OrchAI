"""Starts the existing OrchAI FastAPI application in-process for the
desktop shell (ADR-017), and provisions the single local user OrchAI
Desktop attributes work to (ADR-016).

This module introduces no new business logic: it configures environment
defaults appropriate for a single-user desktop deployment, then reuses
`orchai.bootstrap.runtime` and `orchai.interfaces.api.main.create_app()`
exactly as the CLI and any other API caller already do.
"""

from __future__ import annotations

import asyncio
import contextlib
import getpass
import os
import secrets
import socket
import sys
import threading
import time
from pathlib import Path

import httpx
import uvicorn
from fastapi import FastAPI

from orchai.application.identity import CreateUserCommand
from orchai.bootstrap.runtime import build_identity_runtime_from_settings
from orchai.domain.identity import DuplicateUsernameError
from orchai.infrastructure.configuration import DatabaseSettings, load_settings
from orchai.interfaces.api.main import create_app


def _frontend_dist_dir() -> Path:
    """Locate the built frontend, whether running from source or frozen.

    A frozen PyInstaller build extracts (or ships, for a onedir build)
    bundled data files under `sys._MEIPASS`, not next to this source
    file -- `orchai_desktop.spec` places the built `frontend/dist/` tree
    at `apps/desktop/frontend/dist` inside the bundle to mirror this
    exact relative layout, so the same lookup logic works either way.
    """

    frozen_base = getattr(sys, "_MEIPASS", None)
    if frozen_base is not None:
        return Path(frozen_base) / "apps" / "desktop" / "frontend" / "dist"
    return Path(__file__).resolve().parent.parent / "frontend" / "dist"


#: Where the desktop frontend's build output lives, once one exists
#: (docs/architecture/DESKTOP-APPLICATION.md). Absent in Phase 1's
#: hand-authored placeholder is also acceptable -- `configure_desktop_environment`
#: only points the backend at it when the directory actually exists.
FRONTEND_DIST = _frontend_dist_dir()


def app_data_dir() -> Path:
    """Return the per-user OrchAI Desktop data directory.

    `%APPDATA%/OrchAI` on Windows (the confirmed target platform, ADR-017);
    falls back to `~/.orchai/OrchAI` if `APPDATA` is somehow unset, so this
    never crashes outright on a non-Windows dev machine.
    """

    base = os.environ.get("APPDATA")
    root = Path(base) if base else Path.home() / ".orchai"
    directory = root / "OrchAI"
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def configure_desktop_environment() -> None:
    """Point OrchAI's existing settings loader at desktop-appropriate defaults.

    Only overrides the database URL when nothing explicit was configured
    anywhere `load_settings()` looks (an `ORCHAI_DATABASE_URL` environment
    variable -- including one a tool like `uv run` loaded from a `.env`
    file into the process environment before this code even runs -- or a
    `.env` value `load_settings()` reads directly): `ORCHAI_DATABASE_URL`
    then defaults to a local SQLite file under the per-user app data
    directory instead of `DatabaseSettings.DEFAULT_URL` (a local
    PostgreSQL server), since a desktop install has no PostgreSQL server
    to reach out of the box. Checking "does the fully-resolved URL equal
    the hardcoded fallback" (rather than just `"ORCHAI_DATABASE_URL" not
    in os.environ`) is what makes this correct even when a `.env` file --
    not an environment variable -- is what set it, e.g. when running the
    desktop shell from within a source checkout that has its own
    development `.env`.
    """

    if load_settings().database.url == DatabaseSettings.DEFAULT_URL:
        db_path = app_data_dir() / "orchai.db"
        os.environ["ORCHAI_DATABASE_URL"] = f"sqlite:///{db_path.as_posix()}"
    if FRONTEND_DIST.is_dir():
        os.environ.setdefault("ORCHAI_DESKTOP_STATIC_DIR", str(FRONTEND_DIST))


def find_free_port(host: str = "127.0.0.1") -> int:
    """Return a free TCP port on `host`, chosen by the OS."""

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind((host, 0))
        return sock.getsockname()[1]


async def _ensure_local_desktop_user() -> None:
    settings = load_settings()
    identity_runtime = build_identity_runtime_from_settings(settings)
    existing_users = await identity_runtime.identity_service.list_users(limit=1)
    if existing_users:
        return
    username = f"desktop-{getpass.getuser()}"
    with contextlib.suppress(DuplicateUsernameError):
        await identity_runtime.identity_service.create_user(
            CreateUserCommand(
                username=username,
                # Never checked: ORCHAI_AUTH_ENFORCED stays false for the
                # desktop build (ADR-016) -- this user exists only so
                # Task/Authorization/Audit records carry a real identity.
                plain_password=secrets.token_urlsafe(32),
                is_superuser=True,
            )
        )


def ensure_local_desktop_user() -> None:
    """Silently provision the single local user, if none exists yet (ADR-016).

    Mirrors `orchai auth bootstrap-admin`'s "only when zero users exist"
    rule, but never prompts for credentials -- there is no login screen.
    """

    asyncio.run(_ensure_local_desktop_user())


def build_desktop_app() -> FastAPI:
    """Configure the desktop environment and build the existing FastAPI app."""

    configure_desktop_environment()
    ensure_local_desktop_user()
    return create_app()


class BackendServerThread(threading.Thread):
    """Runs the FastAPI app's `uvicorn` server in a background thread.

    The desktop window and the backend live in the same process (ADR-017);
    this just keeps `uvicorn`'s blocking event loop off the thread that
    will drive the native window.
    """

    def __init__(self, app: FastAPI, host: str, port: int) -> None:
        super().__init__(daemon=True, name="orchai-desktop-backend")
        config = uvicorn.Config(app, host=host, port=port, log_level="warning")
        self.server = uvicorn.Server(config)

    def run(self) -> None:
        self.server.run()

    def stop(self) -> None:
        self.server.should_exit = True


def wait_until_ready(host: str, port: int, *, timeout_seconds: float = 10.0) -> bool:
    """Poll `GET /health` until it responds, or `timeout_seconds` elapses."""

    deadline = time.monotonic() + timeout_seconds
    url = f"http://{host}:{port}/health"
    while time.monotonic() < deadline:
        with contextlib.suppress(httpx.HTTPError):
            response = httpx.get(url, timeout=1.0)
            if response.status_code == 200:
                return True
        time.sleep(0.1)
    return False
