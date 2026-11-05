# AeroAssist — GenAI Machine Learning Engineer Challenge

## Context

An airline Data Scientist built a notebook prototype for an assistant used by airport agents during flight disruptions. The prototype can call an LLM, but it is not reliable, testable, observable, secure, or deployable.

Your job is to turn it into an engineering product. The assistant must distinguish between:

- **dynamic operational facts**, available through the provided MCP server; and
- **versioned policy knowledge**, available in `knowledge_base/` and suitable for retrieval-augmented generation.

All flights, bookings and policies in this repository are synthetic. They must not be interpreted as real airline information.

## Timebox and use of AI

- Submit within **48 hours** of receiving the repository.
- The intended focused effort is **6–8 hours**. Please stop around that point and document what you would do next.
- You may use coding assistants and LLMs. Record how you used them in `docs/AI_USAGE.md`.
- You remain responsible for every committed line and will discuss and modify your solution during the technical interview.
- An incomplete, well-explained solution is preferable to hidden shortcuts or unverifiable claims.

## Goal

Deliver a backend that can be exercised through a stable HTTP contract, deployed to a cloud environment, and evaluated against a golden set. No frontend is required.

You may use any Python web framework, LLM provider, agent framework, retrieval method, IaC tool and CI/CD platform. Preserve the API contract in `docs/API_CONTRACT.md`.

## Progressive levels

Each level is worth 20 points. Levels are cumulative, but Foundation applies to the highest functional level you reach.

### Foundation — engineering and deployment (20)

- typed API contract, validation and meaningful error responses;
- unit/integration tests and a repeatable local command;
- OCI container running as a non-root user on port `8080`;
- live HTTPS deployment on GCP Cloud Run;
- CI and an actual CD path that deploys a reviewed revision;
- secrets and cloud identity handled safely.

### Level 1 — Core GenAI assistant (20)

- replace the notebook prototype with maintainable application code;
- isolate the LLM provider behind an interface;
- support Spanish questions and structured responses;
- make model, location and limits configurable;
- handle provider errors, timeouts and unsupported questions.

### Level 2 — Tools through MCP (20)

Integrate the provided MCP server in `mcp_server/`. The assistant should use the right tool for dynamic information:

- `get_flight_status`
- `get_booking_context`
- `search_reaccommodation`
- `create_reaccommodation_hold`

The last tool represents a state-changing operation. It must not be called until the request explicitly confirms the action. Return auditable tool traces without exposing secrets.

### Level 3 — RAG and grounding (20)

- index and retrieve the policy corpus;
- demonstrate retrieval quality, not only final-answer fluency;
- cite `doc_id` values from the corpus in the API response;
- avoid citing irrelevant documents;
- abstain or qualify the answer when evidence is insufficient;
- define how the index is built, versioned and refreshed.

For this small corpus, a local index is acceptable and often cheaper than a managed vector database. Explain your trade-off.

### Level 4 — Production and LLMOps (20)

- executable golden-set evaluation with useful metrics;
- structured logs, request IDs and operational metrics;
- bounded latency/cost (timeouts, token limits, retry policy, caching if justified);
- defenses for prompt injection, unsafe tool arguments and sensitive logging;
- readiness vs. liveness semantics;
- clear runbook, rollback and cleanup instructions.

## Provided material

- `notebooks/prototype.ipynb`: deliberately naive Data Scientist prototype.
- `mcp_server/`: fully supplied synthetic MCP server. Your task is to integrate it, not rewrite its business data.
- `knowledge_base/`: synthetic policy documents with stable `doc_id` values.
- `evaluation/public_golden.jsonl`: examples that reveal the evaluation format, not all review cases.
- `tests/`: minimal public contract tests.
- `docs/`: API and submission requirements.

## Required HTTP contract

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/health` | Liveness; must not call the LLM |
| GET | `/ready` | Readiness of required dependencies |
| GET | `/v1/capabilities` | Implemented levels and version |
| POST | `/v1/chat` | Main assistant endpoint |
| GET | `/metrics` | Operational metrics; Prometheus text is accepted |

Example:

```bash
curl -sS -X POST "$BASE_URL/v1/chat" \
  -H 'content-type: application/json' \
  -d '{
    "message": "¿Cuál es el estado de LA401 para el 2026-08-06?",
    "session_id": "demo-session",
    "confirm_action": false
  }'
```

See the exact request/response schema and status codes in `docs/API_CONTRACT.md`.

## Local acceptance commands

You may change the implementation of these targets, but keep their names:

```bash
make install
make test
make run
make evaluate-public
make docker-build
```

## Cloud delivery

Deploy the service to GCP Cloud Run because deployment on the target platform is part of the challenge. You may use any CI/CD platform. If you are not eligible for the Google Cloud trial or encounter an account restriction, contact the reviewer before starting: the process must provide a sandbox or approve a written exception; you are not expected to purchase credits.

Your deployed service must remain available until the review is complete. Apply conservative limits (`min instances = 0`, low max instances, bounded output tokens) and include teardown steps. See `docs/DEPLOY_GCP.md` for a non-authoritative bootstrap guide.

## Submission

Complete `docs/DECISIONS.md` and `docs/AI_USAGE.md`, then submit:

1. private repository URL and access for the reviewers;
2. final commit SHA;
3. deployed HTTPS base URL;
4. CI/CD run link or equivalent evidence;
5. highest level you consider complete;
6. known limitations and cleanup command.

Do not publish this repository or the generated variant. Do not commit credentials. We will evaluate the exact submitted commit and use additional private cases.

## What the follow-up interview will cover

Expect to:

- defend two concrete implementation decisions;
- diagnose or implement a small change in this repository;
- draw how you would scale and secure the system;
- interpret one evaluation or operational signal.

This follow-up validates understanding, including code produced with AI assistance.
