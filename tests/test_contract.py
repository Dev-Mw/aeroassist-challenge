from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_health_is_live_and_versioned() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["version"]


def test_chat_contract_is_implemented() -> None:
    response = client.post(
        "/v1/chat",
        json={"message": "¿Qué puedes hacer?", "confirm_action": False},
    )
    assert response.status_code == 200
    body = response.json()
    assert isinstance(body["answer"], str) and body["answer"]
    assert isinstance(body["citations"], list)
    assert isinstance(body["tool_calls"], list)
    assert body["request_id"]


def test_input_validation_rejects_blank_message() -> None:
    response = client.post("/v1/chat", json={"message": "   "})
    assert response.status_code == 422

