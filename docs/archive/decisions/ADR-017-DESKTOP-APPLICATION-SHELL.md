# ADR-017 --- Desktop Application Shell

## Status

Accepted --- Design only; implementation is follow-up work, phased per
`docs/architecture/DESKTOP-APPLICATION.md`.

## Context

OrchAI has never had a UI of any kind --- confirmed by the absence of any
frontend code, `package.json`, or GUI framework dependency anywhere in
the repository. `docs/architecture/API-UI-BOUNDARY.md` and
`ARCHITECTURAL-CONTRACT.md` §2.18 already anticipate "desktop
applications" as a future client without committing to a specific
technology.

The product direction now requires a real, first-class Windows desktop
client with the visual polish and interaction model of Claude Desktop,
ChatGPT, or Cursor: a native window, a project/folder picker, a
sidebar, a chat view with streaming responses, and module navigation
(ADR-015). The confirmed target platform is Windows 11, and the
existing backend investment (the entire `src/orchai/` hexagonal core)
is Python and must be preserved (per the decision to extend, not
rewrite, the backend).

## Decision

1. **Shell technology: `pywebview`, backed by Windows' built-in
   WebView2 (Edge Chromium) runtime.** Windows 11 ships WebView2
   pre-installed, so `pywebview` needs no bundled Chromium (unlike
   Electron or `PySide6`'s `QtWebEngine`, which bundle roughly
   150--200 MB of Chromium each) and exposes a minimal API
   (`webview.create_window`, `webview.create_file_dialog`, a Python
   `js_api` object callable from the frontend). `PySide6`/
   `QtWebEngine` is recorded as the fallback option if a future
   requirement needs deeper native integration than `pywebview`
   provides (a native system tray icon, more elaborate native
   drag-and-drop, native OS notifications beyond what WebView2 itself
   offers) --- not adopted now because no current requirement needs it.
2. **Frontend: a modern web UI (Vite + React, or an equivalent
   component framework), built to static assets, loaded into the
   `pywebview` window.** Node.js/the chosen framework are **build-time
   tools only** --- nothing about them is bundled or run in the shipped
   application; the final artifact is `apps/desktop/frontend/dist/`,
   a folder of static HTML/CSS/JS. This is the same pattern used by
   Electron- and Tauri-based apps, without adopting either of those
   full shells.
3. **The backend runs in-process, not as a separate service the user
   manages.** `apps/desktop/shell/main.py` reuses the existing
   composition root (`bootstrap/runtime.py` and
   `interfaces/api/main.py::create_app()`) unmodified, starts a
   `uvicorn.Server` bound to `127.0.0.1` on an available port (chosen
   at startup, never `0.0.0.0` --- this is a single-user local process,
   never exposed to the network), and opens
   `webview.create_window(url="http://127.0.0.1:<port>/app/", js_api=NativeBridge())`.
   `apps/desktop/frontend/dist/` is mounted as `StaticFiles` under `/app`
   inside the same `create_app()` (not `/`, which the API already owns
   as its JSON entry-points index), active only when the directory
   exists --- still one process, one origin, no CORS configuration
   needed.
4. **Repository layout:**

   ```text
   apps/desktop/
     shell/
       main.py            # entrypoint: starts uvicorn in-process, opens the window
       server_runner.py   # wires bootstrap/runtime.py + interfaces/api/main.py::create_app()
       native_bridge.py   # js_api: folder picker, "recent projects" (%APPDATA%/OrchAI/)
       packaging/         # PyInstaller/briefcase config (Phase 7 hardening)
     frontend/
       package.json
       src/{app,screens,api,state}/
       dist/              # build output, mounted as StaticFiles
     README.md
   ```

   `apps/desktop/` is a new top-level sibling of `src/orchai/`, never
   imported by it --- the dependency direction is one-way (desktop shell
   depends on the existing FastAPI app; the reverse never happens),
   preserving the existing rule that `domain`/`application` code never
   depends on an interface.
5. **"Recent projects" is shell-local state, not backend state.**
   `%APPDATA%/OrchAI/recent_projects.json`, managed entirely by
   `native_bridge.py`, cross-referenced at render time with
   `GET /projects/readiness` / `GET /projects/security` for status
   badges. This keeps the backend itself headless-testable and
   free of desktop-shell-specific concerns, consistent with
   `ARCHITECTURAL-CONTRACT.md` §2.18 (Environment Agnosticism).

## Rationale

- **`pywebview` over Electron/Tauri**: both alternatives require
  bundling and coordinating a second full runtime (Node or Rust)
  alongside the existing Python backend as a "sidecar" process,
  adding packaging complexity and a second language surface for no
  capability gain given the confirmed Windows 11 target already
  provides WebView2 for free.
- **`pywebview` over `PySide6`/`QtWebEngine`**: functionally
  equivalent (both embed a web view for the actual UI), but
  `QtWebEngine` bundles its own Chromium regardless of the OS's own
  WebView, and Qt's broader native-widget surface is unnecessary when
  the entire visual chrome (sidebar, chat view, module switcher) is
  built in the frontend, not as native widgets.
- **In-process backend, not a managed background service**: avoids
  asking the user to run or manage a separate server process, and
  avoids network exposure entirely by binding only to `127.0.0.1`.
- **Reusing `create_app()` unmodified**: the desktop shell becomes just
  another caller of the same composition root the CLI and any other
  API client already use, per the existing "CLI and API share
  application services" invariant (`docs/architecture/API-UI-BOUNDARY.md`)
  --- now extended to "CLI, API, and Desktop share application
  services."

## Consequences

Positive:

- ships as a single Python-based application with no second runtime to
  install or bundle;
- the backend gains a third caller (desktop) at zero cost to its own
  architecture --- no FastAPI route needs to know whether its caller is
  the CLI, a raw HTTP client, or the desktop shell;
- packaging (Phase 7) is a single-ecosystem problem (PyInstaller/
  briefcase), not a multi-runtime one.

Trade-offs:

- `pywebview`'s native integration ceiling is lower than a full native
  toolkit (Qt/WinUI) --- acceptable given the chosen UI is
  web-rendered by design, but a real constraint if deeper native
  Windows integration (jump lists, live tiles, deep notification
  actions) becomes a requirement later;
- the frontend build toolchain (Node/Vite) is a new development-time
  dependency for anyone building the desktop shell, even though it
  never ships in the final artifact;
- binding to a dynamically chosen `127.0.0.1` port means the frontend
  must learn its own backend port at startup (e.g. via a value injected
  into the served `index.html`, or a fixed well-known local port with a
  fallback search) --- a small but real coordination detail Phase 1
  must resolve concretely.

## Non-Goals (this ADR)

- Cross-platform desktop support (macOS/Linux) --- Windows 11 is the
  explicitly confirmed target; `pywebview` happens to support other
  platforms, but nothing here commits to testing or shipping them.
- Auto-update / installer distribution mechanics --- deferred to Phase
  7 hardening.
- Any native OS integration beyond a folder picker and a native window
  --- tray icon, jump lists, and notifications are explicitly deferred,
  not designed here.

## Supersedes

None. Extends ADR-004 (API-First Interface Boundary) and
`docs/architecture/API-UI-BOUNDARY.md` by adding a concrete desktop
client alongside the existing CLI and API, and depends on ADR-016 for
how the desktop shell resolves a caller identity.
