"""Validated, deterministic routing for the four synthetic operational MCP tools.

The LLM is never authorized to produce arbitrary tool names or write arguments.
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Protocol

from app.schemas import ChatRequest, ToolCallTrace


class MCPCaller(Protocol):
    async def call(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]: ...


class UnsafeOperation(ValueError):
    """Request lacks adequate, internally consistent operational arguments."""


@dataclass
class OperationsResult:
    answer: str
    traces: list[ToolCallTrace] = field(default_factory=list)
    requires_confirmation: bool = False


FLIGHT = re.compile(r"\b([A-Z]{2}\s?\d{2,5})\b", re.IGNORECASE)
DATE = re.compile(r"\b(\d{4}-\d{2}-\d{2})\b")
BOOKING = re.compile(r"\b(?:reserva\s+|para\s+)([A-Z0-9]{6})\b", re.IGNORECASE)
ROUTE = re.compile(r"\b([A-Z]{3})\s+(?:a|hacia|->|→)\s+([A-Z]{3})\b", re.IGNORECASE)
KEY = re.compile(
    r"\b(?:idempotency\s*key|clave\s+de\s+idempotencia)\s*[:=]?\s*([A-Za-z0-9_-]{1,64})",
    re.IGNORECASE,
)


def _date(text: str) -> str:
    match = DATE.search(text)
    if match is None:
        raise UnsafeOperation("Indica la fecha de salida en formato YYYY-MM-DD.")
    try:
        date.fromisoformat(match.group(1))
    except ValueError as exc:
        raise UnsafeOperation("La fecha indicada no es válida.") from exc
    return match.group(1)


def _flight(text: str) -> str:
    match = FLIGHT.search(text)
    if match is None:
        raise UnsafeOperation("Indica un número de vuelo válido.")
    return match.group(1).replace(" ", "").upper()


def _booking(text: str) -> str:
    match = BOOKING.search(text)
    if match is None:
        raise UnsafeOperation("Indica el código de reserva de seis caracteres.")
    return match.group(1).upper()


class OperationsService:
    def __init__(self, client: MCPCaller) -> None:
        self.client = client

    async def _call(
        self, name: str, arguments: dict[str, Any], traces: list[ToolCallTrace]
    ) -> dict[str, Any]:
        started = time.perf_counter()
        safe_arguments = {
            key: ("[REDACTED]" if key in {"booking_code", "idempotency_key"} else value)
            for key, value in arguments.items()
        }
        try:
            result = await self.client.call(name, arguments)
        except Exception:
            traces.append(ToolCallTrace(
                name=name, arguments=safe_arguments, status="error",
                duration_ms=int((time.perf_counter() - started) * 1000),
            ))
            raise
        traces.append(ToolCallTrace(
            name=name, arguments=safe_arguments, status="ok",
            duration_ms=int((time.perf_counter() - started) * 1000),
        ))
        return result

    async def handle(self, request: ChatRequest) -> OperationsResult | None:
        text = request.message
        normalized = text.casefold()
        traces: list[ToolCallTrace] = []
        # The user must explicitly request a hold; confirmation flag by itself
        # never creates an operation.
        if ("hold" in normalized or "retención" in normalized) and any(
            term in normalized for term in ("crea", "crear", "confirmo", "genera", "generar")
        ):
            booking, flight = _booking(text), _flight(text)
            match = KEY.search(text)
            if not match:
                raise UnsafeOperation("Indica una clave de idempotencia explícita.")
            key = match.group(1)
            if not request.confirm_action:
                return OperationsResult(
                    answer=(
                        f"Para crear un hold de la reserva {booking} en {flight}, "
                        "confirma la acción estableciendo confirm_action=true "
                        "en esta misma solicitud."
                    ),
                    requires_confirmation=True,
                )
            # Verify reservation and route+date+flight against authoritative MCP data
            # before changing anything. No LLM-generated argument is trusted.
            context = await self._call("get_booking_context", {"booking_code": booking}, traces)
            if not context.get("found", True):
                raise UnsafeOperation("La reserva indicada no existe.")
            options = await self._call("search_reaccommodation", {
                "origin": context["origin"], "destination": context["destination"],
                "departure_date": context["departure_date"], "max_results": 5,
            }, traces)
            eligible = any(
                candidate.get("flight_number") == flight
                and candidate.get("available_seats", 0) >= context.get("passengers", 1)
                for candidate in options.get("options", [])
            )
            if not eligible:
                raise UnsafeOperation("El vuelo no es una alternativa válida para esa reserva.")
            result = await self._call("create_reaccommodation_hold", {
                "booking_code": booking, "flight_number": flight, "idempotency_key": key,
            }, traces)
            if not result.get("created"):
                return OperationsResult(
                    "No se pudo crear el hold: "
                    + str(result.get("reason", "no disponible")),
                    traces,
                )
            return OperationsResult(
                f"Hold confirmado: {result['hold_id']} para {flight}. "
                f"Vigencia: {result['expires_in_minutes']} minutos.",
                traces,
            )

        if (
            any(
                term in normalized
                for term in ("alternativa", "alternativas", "reacomod", "opciones", "busca vuelos")
            )
            and ROUTE.search(text)
        ):
            route = ROUTE.search(text)
            assert route is not None
            origin, destination = route.group(1).upper(), route.group(2).upper()
            result = await self._call("search_reaccommodation", {
                "origin": origin, "destination": destination,
                "departure_date": _date(text), "max_results": 3,
            }, traces)
            choices = result.get("options", [])
            if not choices:
                return OperationsResult(
                    "No se encontraron alternativas disponibles para esa ruta y fecha.",
                    traces,
                )
            summary = "; ".join(
                f"{item['flight_number']} "
                f"({item['departure_time']}, {item['available_seats']} asientos)"
                for item in choices
            )
            return OperationsResult("Alternativas disponibles: " + summary, traces)

        if "reserva" in normalized and any(
            term in normalized
            for term in ("contexto", "revisa", "consulta", "información", "informacion")
        ):
            booking = _booking(text)
            result = await self._call("get_booking_context", {"booking_code": booking}, traces)
            if not result.get("found", True):
                return OperationsResult(f"No encontré la reserva {booking}.", traces)
            return OperationsResult(
                f"Reserva {booking}: vuelo {result['flight_number']}, "
                f"tarifa {result['fare_family']}, nivel {result['loyalty_tier']}.",
                traces,
            )

        if (
            any(
                term in normalized
                for term in ("estado", "retras", "cancelado", "cancelación", "cancelacion", "vuelo")
            )
            and FLIGHT.search(text)
            and DATE.search(text)
        ):
            result = await self._call("get_flight_status", {
                "flight_number": _flight(text), "departure_date": _date(text),
            }, traces)
            if not result.get("found", True):
                return OperationsResult("No encontré ese vuelo para la fecha indicada.", traces)
            return OperationsResult(
                f"El vuelo {result['flight_number']} del {result['departure_date']} "
                f"tiene estado {result['status']} "
                f"({'cancelado' if result['status'] == 'CANCELLED' else 'operativo'}).",
                traces,
            )
        return None
