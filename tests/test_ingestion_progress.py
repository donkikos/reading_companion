from pathlib import Path
from types import SimpleNamespace

import db
import ingest


class _FakeQdrantClient:
    def __init__(self, vector_dim):
        self._vector_dim = vector_dim
        self._collection_exists = True

    def get_collections(self):
        return []

    def collection_exists(self, _name):
        return self._collection_exists

    def get_collection(self, _name):
        return SimpleNamespace(
            config=SimpleNamespace(
                params=SimpleNamespace(vectors=SimpleNamespace(size=self._vector_dim))
            )
        )

    def create_collection(self, **_kwargs):
        self._collection_exists = True

    def upsert(self, collection_name, points):
        return None


def test_ingestion_reports_stage_progress(monkeypatch, tmp_path):
    db_path = tmp_path / "state.db"
    monkeypatch.setattr(db, "DB_PATH", str(db_path))
    db.init_db()

    vector_dim = ingest.QDRANT_VECTOR_DIM or 8
    fake_qdrant = _FakeQdrantClient(vector_dim)
    monkeypatch.setattr(ingest, "_get_qdrant_client", lambda: fake_qdrant)
    monkeypatch.setattr(ingest, "_ensure_qdrant_available", lambda _client: None)
    monkeypatch.setattr(
        ingest,
        "_tei_embed",
        lambda texts, **_kwargs: [
            ingest._hash_embedding(text, dim=vector_dim) for text in texts
        ],
    )

    fixture_path = Path(__file__).parent / "fixtures" / "minimal.epub"
    updates = []

    def record_progress(message, percent):
        updates.append((message, percent))

    ingest.ingest_epub(str(fixture_path), progress_callback=record_progress)

    messages = [message for message, _ in updates]
    percents = [percent for _, percent in updates]

    expected = [
        ("1/6", "Hashing"),
        ("2/6", "Parsing"),
        ("3/6", "Chunking"),
        ("4/6", "Embedding"),
        ("5/6", "Qdrant upsert"),
        ("6/6", "Metadata save"),
    ]
    for stage_prefix, marker in expected:
        assert any(
            stage_prefix in message and marker in message for message in messages
        )

    assert percents == sorted(percents)
    assert percents[-1] == 100
