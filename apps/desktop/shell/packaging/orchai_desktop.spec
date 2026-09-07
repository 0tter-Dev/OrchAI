# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for OrchAI Desktop (ADR-017, Phase 7.6 hardening).

Build (from the repository root, after building the frontend once --
see apps/desktop/README.md):

    uv run --extra desktop --with pyinstaller pyinstaller apps/desktop/shell/packaging/orchai_desktop.spec

Produces a onedir build at dist/OrchAI/OrchAI.exe. Two things a bare
`pyinstaller apps/desktop/shell/main.py` would not get right on its own,
both handled explicitly below:

1. `main.py` imports its siblings with absolute `apps.desktop.shell.*`
   imports (Phase 7.6, replacing sibling-module imports that only
   resolved by relying on a plain script's own directory landing on
   `sys.path`) -- `pathex` must include the repository root so
   PyInstaller's import analysis can resolve them the same way.
2. Migrations (`src/orchai/infrastructure/persistence/db/migrations/*.sql`)
   and the built frontend (`apps/desktop/frontend/dist/`) are data files,
   not Python modules -- PyInstaller never collects either automatically,
   so both are added explicitly below. The migrations are placed at the
   same relative path `importlib.resources` looks them up at
   (`orchai/infrastructure/persistence/db/migrations`, read by
   `SQLAlchemyDatabase.migrate()`); the frontend is placed at
   `apps/desktop/frontend/dist`, matching
   `server_runner._frontend_dist_dir()`'s frozen-build lookup.
"""

from pathlib import Path

from PyInstaller.building.api import COLLECT, EXE, PYZ
from PyInstaller.building.build_main import Analysis
from PyInstaller.building.datastruct import Tree
from PyInstaller.utils.hooks import collect_data_files

# SPECPATH (injected by PyInstaller) is this file's own directory:
# apps/desktop/shell/packaging -- four levels below the repository root.
REPO_ROOT = Path(SPECPATH).resolve().parents[3]  # noqa: F821
MIGRATIONS_DIR = (
    REPO_ROOT
    / "src"
    / "orchai"
    / "infrastructure"
    / "persistence"
    / "db"
    / "migrations"
)
FRONTEND_DIST = REPO_ROOT / "apps" / "desktop" / "frontend" / "dist"

if not FRONTEND_DIST.is_dir():
    raise SystemExit(
        f"No frontend build found at {FRONTEND_DIST}. Run:\n"
        "  cd apps/desktop/frontend && npm install && npm run build\n"
        "before building the desktop package."
    )

migration_datas = [
    (str(sql_file), "orchai/infrastructure/persistence/db/migrations")
    for sql_file in sorted(MIGRATIONS_DIR.glob("*.sql"))
]
if not migration_datas:
    raise SystemExit(f"No migration files found under {MIGRATIONS_DIR}.")

# litellm ships its own data file (model_prices_and_context_window_backup.json)
# that its own import-time code reads directly off disk -- PyInstaller's
# standard analysis only follows Python imports, not a library's own
# runtime file reads, so this must be collected explicitly (confirmed
# necessary by actually running a build: without it, startup fails with
# a FileNotFoundError deep inside litellm's own __init__).
litellm_datas = collect_data_files("litellm")

# litellm imports tiktoken for token counting; tiktoken registers its
# built-in encodings (e.g. "cl100k_base") through a `tiktoken_ext`
# namespace-package plugin discovered at runtime via `pkgutil.iter_modules`
# -- static analysis has no way to follow that, so the plugin module is
# never bundled unless named explicitly (also confirmed necessary by
# actually running a build: without it, startup fails with
# `ValueError: Unknown encoding cl100k_base`).
tiktoken_hidden_imports = ["tiktoken_ext.openai_public", "tiktoken_ext"]

block_cipher = None

a = Analysis(
    [str(REPO_ROOT / "apps" / "desktop" / "shell" / "main.py")],
    pathex=[str(REPO_ROOT)],
    binaries=[],
    datas=migration_datas + litellm_datas,
    hiddenimports=tiktoken_hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    cipher=block_cipher,
)
a.datas += Tree(str(FRONTEND_DIST), prefix="apps/desktop/frontend/dist")

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="OrchAI",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    name="OrchAI",
)
