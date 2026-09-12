from pathlib import Path

import pytest
from fastapi import HTTPException

from app.services import filesafe


def test_rejects_traversal(tmp_path, monkeypatch):
    monkeypatch.setattr(filesafe, "server_dir", lambda _sid: tmp_path)
    (tmp_path / "world").mkdir()
    with pytest.raises(HTTPException):
        filesafe.safe_join("x", "../secret")
    with pytest.raises(HTTPException):
        filesafe.safe_join("x", "world/../../etc/passwd")
    inner = filesafe.safe_join("x", "world")
    assert inner == (tmp_path / "world").resolve()
