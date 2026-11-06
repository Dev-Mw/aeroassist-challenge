"""Real stdio MCP integration; requires the runtime SDK from pyproject.toml."""

import pytest

pytest.importorskip("mcp", reason="Install the project dependencies for real MCP integration")

from app.mcp_client import MCPStdioClient


@pytest.mark.asyncio
async def test_real_stdio_mcp_flight_status():
    response = await MCPStdioClient().call("get_flight_status", {
        "flight_number": "LA401", "departure_date": "2026-08-06",
    })
    assert response["status"] == "CANCELLED"


@pytest.mark.asyncio
async def test_real_stdio_mcp_read_only_options():
    response = await MCPStdioClient().call("search_reaccommodation", {
        "origin": "SCL", "destination": "LIM", "departure_date": "2026-08-06",
        "max_results": 3,
    })
    assert {item["flight_number"] for item in response["options"]} >= {"LA2376", "LA2696"}
