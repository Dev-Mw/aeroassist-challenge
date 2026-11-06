# Operational validation — iteration 6

## What is implemented

- `app/observability.py`: standard-library Prometheus counters and duration histogram, per process. Fixed route/status/tool labels prevent unbounded cardinality. No external metrics dependency.
- `app/main.py`: request ID generated once at the HTTP boundary, also returned as `X-Request-ID`; request-duration and HTTP status tracked for all endpoints; completed MCP traces counted by allowlisted tool names.
- `LOG_FORMAT=json` enables structured service audit events with **allowlisted** fields (event, request ID, route, status, duration, exception type). Raw messages, retrieved context, session IDs, booking codes, idempotency keys and provider secrets are not logged by this instrumentation.
- `/health`: no model call. `/ready`: bounded provider probe (2 seconds) with 503 on failure. **Not a complete dependency readiness check**: MCP and RAG readiness still require dedicated checks.

## Local verification

```bash
make test
make lint
OLLAMA_MODEL=llama3.2:latest LOG_FORMAT=json make run-local
# Another terminal:
curl -i http://127.0.0.1:8080/health
curl -i http://127.0.0.1:8080/ready
curl -sS http://127.0.0.1:8080/metrics
make evaluate-public
python -m scripts.evaluate_rag --base-url http://127.0.0.1:8080
```

Three API smoke cases (send as JSON files, as previously): simple baggage question; baggage + refund; baggage + refund + GOLD priority. Confirm correct evidence IDs, absence of prompt/session values in logs and metrics, and consistent request ID header and response. Also test blank message -> 422, unavailable local model -> `/ready` 503, and a write without explicit confirmation -> no tool action.

## Engineering practices and limits

- **Separation of concerns:** HTTP middleware handles cross-cutting request telemetry, not business policy; `Metrics` owns in-process counters.
- **Dependency inversion:** `AeroAssistAgent` uses `LLMProvider` and an operations boundary, not a specific provider implementation.
- **Security by design:** least disclosure, bounded metric labels, no user text in telemetry, deterministic tool arguments and explicit write confirmation.
- **Repeatability:** deterministic unit tests verify telemetry independently of Ollama/GCP. HTTP smoke and public golden still required on a real environment.
- **Limitations:** in-memory metrics reset at restart and are per-instance; aggregate externally for Cloud Run. Current counters do not cover failed MCP subcalls that raise before the agent returns. Some semantic grounding checks remain heuristic. No rate/concurrency limiter or full MCP/RAG readiness probe has been added yet. Prompt injection defenses are partial, not a formal security guarantee.

## Future final diagrams

Prepare `docs/ARCHITECTURE.md` when the deployment implementation stabilizes: (1) class diagram (`LLMProvider`, implementations, agent, operations, retriever, observability); (2) sequence for policy+LLM; (3) sequence for flight query through MCP; (4) sequence for confirmed hold; (5) cloud deployment/CI flow. These are planned documentation, not completed artifacts.

## Iteration 6b — Prometheus and lint verification

- `aeroassist_requests_total` is the existing aggregate counter;
  `aeroassist_http_requests_total{endpoint,status_class}` has its own HELP/TYPE
  metadata. Histogram samples are now grouped immediately after their metadata.
- A standard Prometheus text parser accepted the exported metrics during local
  verification; the repository's unit test also checks the relevant metric headers.
- Ruff runs on first-party `app/`, `scripts/`, `tests/`, and other applicable project
  files; `mcp_server/` is excluded because it is challenge-supplied code. We did not
  disable `S310` globally: evaluator requests verify HTTP(S) schemes and use narrow,
  documented suppressions at urllib call sites.
- To verify on the intended Windows development environment:

```bash
make test
make lint
make evaluate-public
python -m scripts.evaluate_rag --base-url http://127.0.0.1:8080
curl -sS http://127.0.0.1:8080/metrics
```

- Documentation and quality checks do not imply a production security audit or
  complete MCP/RAG readiness. Keep the remaining limitations from above.
