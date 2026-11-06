"""Bounded-label, in-process Prometheus metrics and privacy-safe JSON events.

In-memory counters are per process: production multi-instance aggregation belongs to
an external metrics backend. Never attach prompts, user/session IDs, or booking codes.
"""
from __future__ import annotations

import json
import logging
from collections import Counter
from threading import Lock

logger = logging.getLogger("aeroassist.operations")


class JsonFormatter(logging.Formatter):
    """Serialize only explicitly provided, low-cardinality operational fields."""

    def format(self, record: logging.LogRecord) -> str:
        payload = {"level": record.levelname, "event": record.getMessage()}
        for name in ("request_id", "path", "method", "status_code", "duration_ms", "error_type"):
            value = getattr(record, name, None)
            if value is not None:
                payload[name] = value
        return json.dumps(payload, ensure_ascii=False)


def configure_logging() -> None:
    """Opt in via LOG_FORMAT=json; never replace host logging handlers."""
    import os
    if os.getenv("LOG_FORMAT", "text").lower() != "json":
        return
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    logger.handlers.clear()
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False


class Metrics:
    """Thread-safe counters with a fixed, bounded label vocabulary."""

    BUCKETS = (0.1, 0.5, 1.0, 3.0, 10.0)

    def __init__(self) -> None:
        self.lock = Lock()
        self.requests: Counter[tuple[str, str]] = Counter()
        self.errors = 0
        self.duration_sum = 0.0
        self.duration_count = 0
        self.buckets: Counter[float] = Counter()
        self.tools: Counter[tuple[str, str]] = Counter()

    def observe(self, *, endpoint: str, status: int, seconds: float) -> None:
        # Do not accept arbitrary URL paths or exception strings as labels.
        if endpoint not in {"/v1/chat", "/health", "/ready", "/v1/capabilities", "/metrics"}:
            endpoint = "other"
        status_class = f"{status // 100}xx" if 100 <= status < 600 else "other"
        with self.lock:
            self.requests[(endpoint, status_class)] += 1
            if status >= 400:
                self.errors += 1
            self.duration_count += 1
            self.duration_sum += seconds
            for bound in self.BUCKETS:
                if seconds <= bound:
                    self.buckets[bound] += 1

    def observe_tool(self, name: str, status: str) -> None:
        allowed = {
            "get_flight_status", "get_booking_context",
            "search_reaccommodation", "create_reaccommodation_hold",
        }
        if name in allowed:
            with self.lock:
                self.tools[(name, "ok" if status == "ok" else "error")] += 1

    def render(self) -> str:
        with self.lock:
            requests = self.requests.copy()
            errors, total, count = self.errors, self.duration_sum, self.duration_count
            buckets, tools = self.buckets.copy(), self.tools.copy()
        output = [
            "# HELP aeroassist_requests_total HTTP requests by route and status class",
            "# TYPE aeroassist_requests_total counter",
            f"aeroassist_requests_total {sum(requests.values())}",
            "# HELP aeroassist_errors_total HTTP responses with status >= 400",
            "# TYPE aeroassist_errors_total counter",
            f"aeroassist_errors_total {errors}",
            "# HELP aeroassist_http_requests_total HTTP requests by route and status",
            "# TYPE aeroassist_http_requests_total counter",
        ]
        for (endpoint, status_class), value in sorted(requests.items()):
            output.append(
                f'aeroassist_http_requests_total{{endpoint="{endpoint}",'
                f'status_class="{status_class}"}} {value}'
            )
        output.extend([
            "# HELP aeroassist_request_duration_seconds HTTP request duration",
            "# TYPE aeroassist_request_duration_seconds histogram",
        ])
        for bound in self.BUCKETS:
            output.append(
                f'aeroassist_request_duration_seconds_bucket{{le="{bound}"}} {buckets[bound]}'
            )
        output += [
            f'aeroassist_request_duration_seconds_bucket{{le="+Inf"}} {count}',
            f"aeroassist_request_duration_seconds_sum {total:.6f}",
            f"aeroassist_request_duration_seconds_count {count}",
            "# HELP aeroassist_mcp_calls_total Completed MCP calls by tool and status",
            "# TYPE aeroassist_mcp_calls_total counter",
        ]
        for (name, status), value in sorted(tools.items()):
            output.append(f'aeroassist_mcp_calls_total{{tool="{name}",status="{status}"}} {value}')
        return "\n".join(output) + "\n"
