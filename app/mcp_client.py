"""MCP client over the supplied server's stdio protocol (no direct store imports)."""

from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Any


class MCPToolError(Exception):
    """The MCP server could not complete a tool invocation."""


class MCPStdioClient:
    """Short-lived stdio session per request; safe for concurrent HTTP invocations.

    A dedicated process per call is simple and isolates failures. For higher throughput,
    reuse a managed connection during application lifespan instead.
    """

    async def call(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        if name not in {
            "get_flight_status", "get_booking_context", "search_reaccommodation",
            "create_reaccommodation_hold",
        }:
            raise ValueError("Unsupported MCP tool")
        try:
            from mcp import ClientSession, StdioServerParameters
            from mcp.client.stdio import stdio_client
        except ImportError as exc:
            raise MCPToolError("MCP SDK is unavailable") from exc

        root = Path(__file__).resolve().parent.parent
        server = StdioServerParameters(
            command=os.getenv("MCP_PYTHON", sys.executable),
            args=["-m", "mcp_server.server"],
            cwd=str(root),
            env=None,
        )
        try:
            async with asyncio.timeout(float(os.getenv("MCP_TIMEOUT_SECONDS", "10"))):
                async with stdio_client(server) as (reader, writer):
                    async with ClientSession(reader, writer) as session:
                        await session.initialize()
                        result = await session.call_tool(name, arguments)
            if result.isError:
                raise MCPToolError("MCP tool returned an error")
            structured = getattr(result, "structuredContent", None)
            if isinstance(structured, dict):
                # FastMCP can wrap result dictionaries in an RPC output envelope.
                if set(structured) == {"result"} and isinstance(structured["result"], dict):
                    return structured["result"]
                return structured
            for block in result.content:
                if getattr(block, "type", None) == "text":
                    value = json.loads(block.text)
                    if isinstance(value, dict):
                        return value
            raise MCPToolError("MCP response does not contain an object")
        except TimeoutError:
            raise
        except MCPToolError:
            raise
        except Exception as exc:
            raise MCPToolError("MCP invocation failed") from exc
