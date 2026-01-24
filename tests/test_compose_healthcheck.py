import urllib.error

import pytest

import scripts.compose_healthcheck as healthcheck


class _FakeResponse:
    def __init__(self, status=200):
        self.status = status

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


def test_healthcheck_wait_for_success(monkeypatch):
    monkeypatch.setattr(healthcheck, "TIMEOUT", 0.5)
    monkeypatch.setattr(healthcheck, "INTERVAL", 0)
    monkeypatch.setattr(healthcheck.time, "sleep", lambda _seconds: None)

    def _fake_urlopen(_url, timeout=5):
        return _FakeResponse(status=204)

    monkeypatch.setattr(healthcheck.urllib.request, "urlopen", _fake_urlopen)

    healthcheck._wait_for("http://example", "app")


def test_healthcheck_wait_for_failure(monkeypatch):
    monkeypatch.setattr(healthcheck, "TIMEOUT", 0.1)
    monkeypatch.setattr(healthcheck, "INTERVAL", 0)
    monkeypatch.setattr(healthcheck.time, "sleep", lambda _seconds: None)

    def _fake_urlopen(_url, timeout=5):
        raise urllib.error.URLError("offline")

    monkeypatch.setattr(healthcheck.urllib.request, "urlopen", _fake_urlopen)

    with pytest.raises(SystemExit, match="app error:"):
        healthcheck._wait_for("http://example", "app")
