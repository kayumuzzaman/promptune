"""Shared pytest fixtures.

The autouse ``_isolate_home`` fixture redirects ``$HOME`` (and ``XDG_DATA_HOME``)
to a per-test temp directory so the suite never reads or writes the real user's
history DB, config, or daemon files. Without it, ``enhance()`` — which now records
to the history store — would pollute ``~/.local/share/promptune/history.db`` and
let dedup cache hits leak across tests.
"""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _isolate_home(
    tmp_path_factory: pytest.TempPathFactory,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    home = tmp_path_factory.mktemp("home")
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("XDG_DATA_HOME", str(home / ".local" / "share"))
