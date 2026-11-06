"""Operational contract tests with deterministic stand-ins for MCP transport."""

import pytest
from fastapi.testclient import TestClient

from app.agent import AeroAssistAgent
from app.main import create_app
from app.operations import OperationsService
from mcp_server import store


class LocalMCPStub:
    """Test-only fake transport; production code MUST use the MCP protocol."""

    def __init__(self):
        self.calls = []

    async def call(self, name, arguments):
        self.calls.append((name, arguments))
        return getattr(store, name)(**arguments)


@pytest.fixture
def setup():
    mcp = LocalMCPStub()
    api = TestClient(create_app(AeroAssistAgent(operations=OperationsService(mcp))))
    return api, mcp


def send(api, message, confirm_action=False):
    return api.post("/v1/chat", json={"message": message, "confirm_action": confirm_action})


def test_flight_status_goes_to_mcp(setup):
    api, mcp = setup
    resp = send(api, "¿Cuál es el estado de LA401 para el 2026-08-06?")
    assert resp.status_code == 200
    assert "CANCELLED" in resp.json()["answer"]
    assert mcp.calls == [
        ("get_flight_status", {"flight_number": "LA401", "departure_date": "2026-08-06"})
    ]


def test_booking_goes_to_mcp_and_redacts_trace(setup):
    api, mcp = setup
    resp = send(api, "Revisa el contexto mínimo de la reserva Q7M2PX.")
    assert resp.status_code == 200
    assert "GOLD" in resp.json()["answer"]
    assert mcp.calls[0][0] == "get_booking_context"
    assert resp.json()["tool_calls"][0]["arguments"]["booking_code"] == "[REDACTED]"


def test_options_are_authoritative(setup):
    api, mcp = setup
    resp = send(api, "Busca alternativas SCL a LIM para el 2026-08-06.")
    assert resp.status_code == 200
    assert "LA2376" in resp.json()["answer"]
    assert "LA2696" in resp.json()["answer"]
    assert mcp.calls[0][0] == "search_reaccommodation"


def test_write_rejected_without_confirmation_or_side_effects(setup):
    api, mcp = setup
    resp = send(api, "Crea un hold para Q7M2PX en LA2376 con idempotency key public-06.")
    assert resp.status_code == 200
    assert resp.json()["requires_confirmation"] is True
    assert mcp.calls == []


def test_confirmed_write_checks_booking_and_route_first(setup):
    api, mcp = setup
    resp = send(
        api, "Confirmo crear el hold para Q7M2PX en LA2376 "
        "con idempotency key public-07.", True,
    )
    assert resp.status_code == 200
    assert "HOLD-" in resp.json()["answer"]
    assert "15" in resp.json()["answer"]
    assert [n for n, _ in mcp.calls] == [
        "get_booking_context", "search_reaccommodation", "create_reaccommodation_hold",
    ]
    assert resp.json()["tool_calls"][-1]["arguments"]["idempotency_key"] == "[REDACTED]"


def test_invalid_target_cannot_be_held(setup):
    api, mcp = setup
    resp = send(
        api, "Confirmo crear el hold para Q7M2PX en LA532 "
        "con idempotency key test-bad.", True,
    )
    assert resp.status_code == 400
    assert "create_reaccommodation_hold" not in [name for name, _ in mcp.calls]


def test_confirmation_flag_without_explicit_write_intent_does_not_write(setup):
    api, mcp = setup
    resp = send(api, "¿Qué puedes hacer?", True)
    assert resp.status_code == 200
    assert mcp.calls == []


def test_missing_idempotency_key_is_rejected(setup):
    api, mcp = setup
    resp = send(api, "Confirmo crear el hold para Q7M2PX en LA2376.", True)
    assert resp.status_code == 400
    assert mcp.calls == []


def test_invalid_date_is_rejected_before_tool_invocation(setup):
    api, mcp = setup
    resp = send(api, "estado de LA401 para el 2026-44-06")
    assert resp.status_code == 400
    assert mcp.calls == []
