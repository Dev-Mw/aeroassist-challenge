# API contract

The evaluator treats this document as authoritative. Extra fields and endpoints are allowed.

## `GET /health`

- Status: `200`
- Body: `{"status":"ok","version":"1.0.0"}`
- Must be fast and must not call external providers.

## `GET /ready`

- `200` with `{"status":"ready","checks":{...}}` when required dependencies are ready.
- `503` with the same shape and `status="not_ready"` otherwise.
- A provider call is not required on every readiness request; a bounded initialization check is acceptable.

## `GET /v1/capabilities`

Response:

```json
{
  "challenge_version": "1.0.0",
  "levels": {
    "foundation": true,
    "core": true,
    "tools_mcp": false,
    "rag": false,
    "production": false
  },
  "llm_backend": "fake",
  "tool_transport": "none"
}
```

Report only capabilities that actually work in the submitted revision.

## `POST /v1/chat`

Request:

```json
{
  "message": "¿Cuál es el estado de LA401 para el 2026-08-06?",
  "session_id": "optional-session-id",
  "confirm_action": false
}
```

Rules:

- `message`: required string, 1–4,000 characters after trimming.
- `session_id`: optional string, max 128 characters.
- `confirm_action`: optional boolean, default `false`; it authorizes only the state-changing action described in the same request/context.

Response:

```json
{
  "answer": "El vuelo LA401 figura cancelado.",
  "citations": [
    {
      "doc_id": "IRROPS-001",
      "title": "Reacomodación por disrupciones",
      "chunk_id": "IRROPS-001#rebooking",
      "score": 0.74
    }
  ],
  "tool_calls": [
    {
      "name": "get_flight_status",
      "arguments": {"flight_number":"LA401","departure_date":"2026-08-06"},
      "status": "ok",
      "duration_ms": 12
    }
  ],
  "requires_confirmation": false,
  "request_id": "01J...",
  "model": "configured-model",
  "latency_ms": 231
}
```

`citations` may be empty for pure dynamic queries. `tool_calls` may be empty for policy queries. Do not include chain-of-thought, provider credentials, raw prompts or sensitive booking fields.

## `GET /metrics`

Prometheus text format is recommended. At minimum expose request count, error count and latency. Do not use unbounded labels such as raw message, session ID, booking code or request ID.

## Errors

Use JSON with `error.code`, `error.message` and `request_id` when possible.

| Status | Meaning |
| ---: | --- |
| 400 | Invalid or unsafe request semantics |
| 422 | Schema validation failure |
| 429 | Local rate/concurrency protection |
| 502 | Upstream provider/tool failure |
| 503 | Service not ready |
| 504 | Bounded upstream timeout |

