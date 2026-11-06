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



def test_capabilities_are_truthful_for_fake_infrastructure_backend() -> None:
    response = client.get("/v1/capabilities")
    assert response.status_code == 200
    body = response.json()
    assert body["levels"]["foundation"] is False
    assert body["levels"]["production"] is False
    assert body["levels"]["tools_mcp"] is True
    assert body["levels"]["rag"] is True
    if body["llm_backend"] == "fake":
        assert body["levels"]["core"] is False


def test_capabilities_report_real_configured_llm_provider() -> None:
    from app.agent import AeroAssistAgent
    from app.main import create_app

    class LocalModel:
        model_name = "test-configured-model"

        async def generate(self, *, system: str, user: str) -> str:
            return "Respuesta sintética"

    agent = AeroAssistAgent(provider=LocalModel(), generate_grounded=True)
    with TestClient(create_app(agent=agent)) as test_app:
        response = test_app.get("/v1/capabilities")
    assert response.status_code == 200
    assert response.json()["levels"]["core"] is True
    assert response.json()["levels"]["foundation"] is False
