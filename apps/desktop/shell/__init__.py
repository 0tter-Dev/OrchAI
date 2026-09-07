"""OrchAI Desktop shell package.

Turning this directory into a real package (Phase 7.6) -- rather than a
flat set of sibling modules relying on the entry script's own directory
landing on `sys.path` -- is what lets `main.py`, `server_runner.py`, and
`native_bridge.py` import each other with absolute imports
(`apps.desktop.shell.x`) that resolve identically whether run directly
(`python -m apps.desktop.shell.main`) or from a frozen PyInstaller build,
where a raw script's directory is not implicitly importable the same way.
"""
