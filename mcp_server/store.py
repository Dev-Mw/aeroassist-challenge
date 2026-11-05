"""Pure business functions behind the supplied MCP tools.

The records are synthetic and intentionally small. Candidates should integrate the
MCP surface instead of copying the records into prompts.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


DATA_DIR = Path(__file__).resolve().parent / "data"


def _load(name: str) -> list[dict[str, Any]]:
    return json.loads((DATA_DIR / name).read_text(encoding="utf-8"))


def get_flight_status(flight_number: str, departure_date: str) -> dict[str, Any]:
    flight_number = flight_number.strip().upper()
    for flight in _load("flights.json"):
        if (
            flight["flight_number"] == flight_number
            and flight["departure_date"] == departure_date
        ):
            return dict(flight)
    return {
        "found": False,
        "flight_number": flight_number,
        "departure_date": departure_date,
    }


def get_booking_context(booking_code: str) -> dict[str, Any]:
    booking_code = booking_code.strip().upper()
    for booking in _load("bookings.json"):
        if booking["booking_code"] == booking_code:
            return dict(booking)
    return {"found": False, "booking_code": booking_code}


def search_reaccommodation(
    origin: str,
    destination: str,
    departure_date: str,
    max_results: int = 3,
) -> dict[str, Any]:
    max_results = max(1, min(int(max_results), 5))
    matches = [
        item
        for item in _load("alternatives.json")
        if item["origin"] == origin.strip().upper()
        and item["destination"] == destination.strip().upper()
        and item["departure_date"] == departure_date
        and item["available_seats"] > 0
    ]
    matches.sort(key=lambda item: item["departure_time"])
    return {"options": matches[:max_results], "count": min(len(matches), max_results)}


def create_reaccommodation_hold(
    booking_code: str,
    flight_number: str,
    idempotency_key: str,
) -> dict[str, Any]:
    booking = get_booking_context(booking_code)
    if not booking.get("found", True):
        return {"created": False, "reason": "booking_not_found"}
    target = flight_number.strip().upper()
    alternatives = _load("alternatives.json")
    if not any(item["flight_number"] == target and item["available_seats"] > 0 for item in alternatives):
        return {"created": False, "reason": "flight_not_available"}
    if not idempotency_key.strip():
        return {"created": False, "reason": "idempotency_key_required"}
    digest = hashlib.sha256(
        f"{booking_code.upper()}:{target}:{idempotency_key}".encode("utf-8")
    ).hexdigest()[:12].upper()
    return {
        "created": True,
        "hold_id": f"HOLD-{digest}",
        "booking_code": booking_code.upper(),
        "flight_number": target,
        "expires_in_minutes": 15,
        "idempotent": True,
    }

