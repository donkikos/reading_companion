from pathlib import Path


def test_docker_compose_includes_app_qdrant_and_healthcheck():
    compose = Path("docker-compose.yml").read_text()

    assert "app:" in compose
    assert "qdrant:" in compose
    assert "healthcheck:" in compose
    assert "compose_healthcheck.py" in compose
    assert "QDRANT_URL" in compose
