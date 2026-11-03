import os
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

REPO = Path(__file__).resolve().parents[2]


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    db_url = os.environ.get("TRACELUME_TEST_DATABASE_URL") or f"sqlite:///{tmp_path}/t.db"
    monkeypatch.setenv("TRACELUME_DATABASE_URL", db_url)
    monkeypatch.setenv("TRACELUME_EVIDENCE_DIR", str(tmp_path / "evidence"))
    monkeypatch.setenv("TRACELUME_WORKSPACE_DIR", str(tmp_path / "work"))
    monkeypatch.setenv("TRACELUME_IMPORT_DIR", str(tmp_path / "import"))
    monkeypatch.setenv("TRACELUME_PLUGINS_DIR", str(REPO / "plugins"))
    monkeypatch.setenv("TRACELUME_JOB_QUEUE", "inline")
    monkeypatch.setenv("TRACELUME_RUNNER", "fake")
    from tracelume.config import get_settings
    from tracelume.db import get_engine
    from tracelume.plugins.registry import load_plugins

    get_settings.cache_clear()
    get_engine.cache_clear()
    load_plugins.cache_clear()
    from tracelume.main import create_app

    with TestClient(create_app()) as c:
        yield c
    from sqlmodel import SQLModel

    SQLModel.metadata.drop_all(get_engine())
    get_engine().dispose()
    get_settings.cache_clear()
    get_engine.cache_clear()
