import json
import urllib.error

import pytest

import ingest


class _FakeResponse:
    def __init__(self, payload):
        self._payload = json.dumps(payload).encode("utf-8")

    def read(self):
        return self._payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


def test_ollama_embed_returns_embeddings(monkeypatch):
    payload = {"embeddings": [[0.1, 0.2], [0.3, 0.4]]}

    def _fake_urlopen(_request, timeout=None):
        return _FakeResponse(payload)

    monkeypatch.setattr(ingest.urllib.request, "urlopen", _fake_urlopen)

    embeddings = ingest._ollama_embed(["one", "two"], dimensions=2)

    assert embeddings == payload["embeddings"]


def test_ollama_embed_dimension_mismatch(monkeypatch):
    payload = {"embeddings": [[0.1, 0.2]]}

    def _fake_urlopen(_request, timeout=None):
        return _FakeResponse(payload)

    monkeypatch.setattr(ingest.urllib.request, "urlopen", _fake_urlopen)

    with pytest.raises(ValueError, match="dimension mismatch"):
        ingest._ollama_embed(["one"], dimensions=3)


def test_ollama_embed_unavailable(monkeypatch):
    def _fake_urlopen(_request, timeout=None):
        raise urllib.error.URLError("no route")

    monkeypatch.setattr(ingest.urllib.request, "urlopen", _fake_urlopen)

    with pytest.raises(RuntimeError, match="Ollama embedding service is unavailable"):
        ingest._ollama_embed(["one"])
