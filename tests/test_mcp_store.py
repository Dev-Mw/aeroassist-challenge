from mcp_server import store


def test_flight_status_fixture() -> None:
    result = store.get_flight_status("la401", "2026-08-06")
    assert result["found"] is True
    assert result["status"] == "CANCELLED"


def test_hold_is_deterministically_idempotent() -> None:
    first = store.create_reaccommodation_hold("Q7M2PX", "LA2376", "same-key")
    second = store.create_reaccommodation_hold("Q7M2PX", "LA2376", "same-key")
    assert first["created"] is True
    assert first["hold_id"] == second["hold_id"]


def test_unknown_booking_does_not_create_hold() -> None:
    result = store.create_reaccommodation_hold("UNKNOWN", "LA2376", "key")
    assert result == {"created": False, "reason": "booking_not_found"}

