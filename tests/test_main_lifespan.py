import pytest
from fastapi.testclient import TestClient

import ingest
import main


def test_lifespan_runs_cleanup(monkeypatch):
    calls = []

    def _cleanup():
        calls.append(True)

    monkeypatch.setattr(ingest, "cleanup_orphaned_qdrant_chunks", _cleanup)

    with TestClient(main.app) as client:
        response = client.get("/books")

    assert response.status_code == 200
    assert calls == [True]


def test_lifespan_raises_when_cleanup_fails(monkeypatch):
    def _cleanup():
        raise RuntimeError("Qdrant is unavailable; ingestion cannot proceed.")

    monkeypatch.setattr(ingest, "cleanup_orphaned_qdrant_chunks", _cleanup)

    with pytest.raises(RuntimeError, match="Qdrant is unavailable"):
        with TestClient(main.app):
            pass
