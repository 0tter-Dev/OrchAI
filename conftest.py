"""Repository-wide pytest configuration.

This exists to work around a broken environment, not to establish a
project convention -- see `pytest_configure` below.
"""

from __future__ import annotations

from pathlib import Path

import pytest


@pytest.hookimpl(tryfirst=True)
def pytest_configure(config: pytest.Config) -> None:
    """Default `tmp_path`'s base directory to a project-local path.

    pytest's own default base temp directory
    (`<tempfile.gettempdir()>/pytest-of-<user>`) has a broken ACL in
    this checkout's environment -- created under a different Windows
    account/session, denying access (including listing or deleting it)
    to every account tested since -- which makes every test that uses
    `tmp_path`/`tmp_path_factory` fail outright unless `--basetemp` is
    passed explicitly on every invocation. `tryfirst=True` ensures this
    runs before `_pytest.tmpdir`'s own `pytest_configure`, which reads
    `config.option.basetemp` to build the session's `tmp_path_factory`.
    An explicit `--basetemp` passed on the command line is respected,
    never overridden.
    """

    if not config.option.basetemp:
        config.option.basetemp = str(Path(config.rootpath) / ".cache" / "pytest-tmp")
