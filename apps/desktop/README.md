# OrchAI Desktop

The Windows desktop shell for OrchAI (ADR-017,
`docs/architecture/DESKTOP-APPLICATION.md`). Runs the existing
`src/orchai` backend in-process and renders it in a native window via
`pywebview`, backed by Windows' built-in WebView2 runtime.

This directory is a separate deployment shape from the headless
CLI/API (`orchai api serve`) — it introduces no business logic of its
own and depends only on the existing FastAPI application
(`orchai.interfaces.api.main.create_app()`), never the reverse.

## Layout

```text
apps/desktop/
  shell/
    __init__.py         makes this a real package (Phase 7.6) -- see "Packaging" below
    main.py              entrypoint: starts uvicorn in-process, opens the window
    server_runner.py     wires bootstrap/runtime.py + interfaces/api/main.py::create_app()
    native_bridge.py     js_api: folder picker, recent projects
    packaging/
      orchai_desktop.spec   PyInstaller spec (Phase 7.6)
  frontend/
    src/               Vite + React source (Project Picker, Module Select, Forge)
    dist/              build output served by the backend under /app/ (gitignored, build it locally)
```

Node.js is a build-time tool only — nothing about it is bundled into
the shipped application; the final artifact is the static
`frontend/dist/` folder.

## Running from source

Install the desktop extra once:

```bash
uv sync --extra desktop
```

Build the frontend once (and again after changing anything under
`frontend/src/`):

```bash
cd apps/desktop/frontend
npm install
npm run build
```

Then run the shell from the repository root, as a module (`-m`, not a
raw script path — `main.py` imports its siblings with absolute
`apps.desktop.shell.*` imports, which only resolve when the repository
root is on `sys.path`, exactly as `-m` arranges):

```bash
uv run python -m apps.desktop.shell.main
```

This starts the OrchAI backend on a free `127.0.0.1` port (never the
network), waits for `GET /health` to respond, and opens it in a native
window at `/app/` (the built frontend). If `frontend/dist/` was never
built, it falls back to opening the API's own JSON index at `/` and
prints a reminder to run the build. Backend data is stored per-user
under `%APPDATA%/OrchAI/` (SQLite, per ADR-016 — no PostgreSQL server
is required for the desktop build) unless `ORCHAI_DATABASE_URL` (or a
`.env` file) already points somewhere else.

## Packaging (PyInstaller)

`apps/desktop/shell/packaging/orchai_desktop.spec` builds a onedir
Windows executable. Build the frontend first (see above), then from the
repository root:

```bash
uv run --extra desktop --with pyinstaller pyinstaller apps/desktop/shell/packaging/orchai_desktop.spec
```

The result is `dist/OrchAI/OrchAI.exe` plus its `_internal/` support
files (migrations and the built frontend are bundled in automatically —
see the spec file's own comments for exactly where and why). Smoke-test
it manually before distributing a build:

1. Run `dist/OrchAI/OrchAI.exe` on a clean checkout of the target
   machine (or at least outside this repository, so no `.env`/dev
   Postgres is accidentally picked up).
2. Confirm the native window opens and shows the Project Picker.
3. Open a folder and confirm the module screens work (a fresh SQLite
   database should appear under `%APPDATA%/OrchAI/`).
4. Close the window and confirm the process exits cleanly.

This packaging step is a separate, independent deployment shape from
the headless Docker image (`Dockerfile`, repository root) — see
`docs/architecture/DEPLOYMENT-MODEL.md`.

## Identity

Per ADR-016, there is no login screen. On first launch, a single local
superuser is provisioned silently and used only for attribution on
`Task`/`Authorization`/`Audit` records; `ORCHAI_AUTH_ENFORCED` is never
enabled by the desktop shell.
