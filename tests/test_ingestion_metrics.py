import json
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

    def upsert(self, **_kwargs):
        return None


def test_ingestion_metrics_logged(monkeypatch, tmp_path, capsys):
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
    ingest.ingest_epub(str(fixture_path))

    stdout = capsys.readouterr().out
    metrics = None
    for line in stdout.splitlines():
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if payload.get("event") == "ingestion_metrics":
            metrics = payload
            break

    assert metrics is not None

    epub_book = ingest.epub.read_epub(str(fixture_path))
    stream, chapters = ingest.build_sentence_stream(epub_book)
    expected_chunks = len(ingest.create_fixed_window_chunks(stream, chapters=chapters))

    assert metrics["chunks_processed"] == expected_chunks
    assert metrics["total_time_s"] >= 0
    assert metrics["embedding_time_s"] >= 0
    assert metrics["qdrant_upsert_time_s"] >= 0
    assert metrics["chunks_per_sec"] >= 0
