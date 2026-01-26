from fastapi.testclient import TestClient

import main


def test_list_tasks_returns_current_tasks(monkeypatch):
    tasks = {"task-1": {"status": "pending", "message": "Queued"}}
    monkeypatch.setattr(main, "tasks", tasks)

    client = TestClient(main.app)
    response = client.get("/tasks")

    assert response.status_code == 200
    assert response.json() == tasks
