"""OrchAI Desktop entrypoint (ADR-017).

Starts the existing OrchAI backend in-process (bound to 127.0.0.1 only)
and opens it in a native window via `pywebview`, backed by Windows'
built-in WebView2 runtime.

Run with (from the repository root):

    uv run --extra desktop python -m apps.desktop.shell.main

`-m` (rather than a raw script path) is what makes the absolute
`apps.desktop.shell.*` imports below resolve -- the same reason they also
resolve correctly from a frozen PyInstaller build
(`apps/desktop/shell/packaging/orchai_desktop.spec`), unlike the sibling-
module imports (`from server_runner import ...`) this replaced, which
only worked by relying on Python adding a plain script's own directory to
`sys.path`.
"""

from __future__ import annotations

import sys

from apps.desktop.shell.server_runner import (
    FRONTEND_DIST,
    BackendServerThread,
    build_desktop_app,
    find_free_port,
    wait_until_ready,
)

_HOST = "127.0.0.1"


def main() -> int:
    app = build_desktop_app()
    port = find_free_port(_HOST)

    server_thread = BackendServerThread(app, _HOST, port)
    server_thread.start()

    if not wait_until_ready(_HOST, port):
        print(f"OrchAI backend did not become ready on {_HOST}:{port}.", file=sys.stderr)
        server_thread.stop()
        return 1

    try:
        import webview
    except ImportError:
        print(
            "pywebview is not installed. Install the desktop extra with:\n"
            "  uv sync --extra desktop",
            file=sys.stderr,
        )
        server_thread.stop()
        return 1

    from apps.desktop.shell.native_bridge import NativeBridge

    if FRONTEND_DIST.is_dir():
        window_url = f"http://{_HOST}:{port}/app/"
    else:
        # No build output yet -- fall back to the API's own JSON index
        # rather than opening a bare 404. See apps/desktop/README.md.
        print(
            f"No frontend build found at {FRONTEND_DIST}. Run:\n"
            "  cd apps/desktop/frontend && npm install && npm run build\n"
            "Opening the API index instead.",
            file=sys.stderr,
        )
        window_url = f"http://{_HOST}:{port}/"

    bridge = NativeBridge()
    window = webview.create_window(
        "OrchAI",
        # /app, not "/": the backend's own root ("/") is the API's JSON
        # entry-points index (interfaces/api/main.py), not the frontend.
        url=window_url,
        js_api=bridge,
        width=1280,
        height=840,
        min_size=(960, 600),
    )
    bridge.window = window
    webview.start()

    server_thread.stop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
