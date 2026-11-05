"""Provided MCP server using stdio transport."""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from mcp_server import store


mcp = FastMCP("aeroassist-operations")


@mcp.tool()
def get_flight_status(flight_number: str, departure_date: str) -> dict:
    """Return current synthetic status for one flight and date."""
    return store.get_flight_status(flight_number, departure_date)


@mcp.tool()
def get_booking_context(booking_code: str) -> dict:
    """Return minimum synthetic context required to assist one booking."""
    return store.get_booking_context(booking_code)


@mcp.tool()
def search_reaccommodation(
    origin: str,
    destination: str,
    departure_date: str,
    max_results: int = 3,
) -> dict:
    """Search synthetic flight alternatives with available seats."""
    return store.search_reaccommodation(origin, destination, departure_date, max_results)


@mcp.tool()
def create_reaccommodation_hold(
    booking_code: str,
    flight_number: str,
    idempotency_key: str,
) -> dict:
    """Create a synthetic 15-minute hold. The client must obtain confirmation first."""
    return store.create_reaccommodation_hold(booking_code, flight_number, idempotency_key)


if __name__ == "__main__":
    mcp.run(transport="stdio")

