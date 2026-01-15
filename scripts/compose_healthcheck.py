import os
import time
import urllib.request


APP_URL = os.environ.get("APP_URL", "http://app:8000/books")
QDRANT_URL = os.environ.get("QDRANT_URL", "http://qdrant:6333/healthz")
TIMEOUT = float(os.environ.get("HEALTHCHECK_TIMEOUT", "30"))
INTERVAL = float(os.environ.get("HEALTHCHECK_INTERVAL", "1"))


def _wait_for(url: str, label: str) -> None:
    deadline = time.time() + TIMEOUT
    last_error = None
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=5) as response:
                if 200 <= response.status < 300:
                    return
                last_error = f"{label} returned {response.status}"
        except Exception as exc:  # pragma: no cover - best-effort polling
            last_error = f"{label} error: {exc}"
        time.sleep(INTERVAL)
    raise SystemExit(last_error or f"{label} not reachable")


if __name__ == "__main__":
    _wait_for(APP_URL, "app")
    _wait_for(QDRANT_URL, "qdrant")
    print("healthcheck: ok")
