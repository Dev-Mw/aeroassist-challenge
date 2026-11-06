# Technical decisions

## Highest completed level

- **Claimed level:** Level 3 (MCP + RAG), with selected Level 4 practices demonstrated locally. Foundation is not fully complete without the required GCP deployment.
- **Working:** typed FastAPI contract, Ollama locally, MCP operations and confirmation checks, policy retrieval and citations, logs/metrics, Docker non-root, GitHub Actions CI.
- **Incomplete:** Cloud Run HTTPS, Vertex AI end-to-end and live CD. No cloud production claim.

## Architecture

- **Request flow:** `main.py` validates HTTP → `AeroAssistAgent` orchestrates → `OperationsService` handles operational requests through `MCPStdioClient`, or `Retriever` selects policy excerpts for grounded generation. `grounding.py` can reject or fall back to extractive evidence.
- **LLM abstraction:** `LLMProvider` isolates model-specific code. Ollama is the locally tested adapter; Vertex AI is implemented but not verified against GCP.
- **Tools:** deterministic routing and application-side validation. A state-changing hold requires `confirm_action=true`, an idempotency key and booking/flight checks before the MCP write.
- **Retrieval:** local TF-IDF over a small synthetic corpus; no database or embedding service needed. Stable `doc_id` citations, content-hash index version and explicit refresh. Lexical retrieval has limits with paraphrases.

## Evaluation

- **Evidence:** 74 local pytest tests, Ruff passing, public golden set 8/8; GitHub CI passing with tests, offline RAG and Docker smoke test. Docker runs as non-root and responds on port 8080.
- **RAG offline:** Recall@5 = 1.0, Precision@5 = 0.9375 on five predefined cases; these are small deterministic tests, not broad semantic accuracy or RAGAS scores.
- **Failure investigated:** the model confused a cancelled-flight refund with a baggage refund. Added targeted grounding checks and a policy-based fallback; repeated manual compound queries returned the refund and baggage policies.

## Reliability, security and cost

- **Timeouts:** bounded LLM/MCP calls and provider-error handling; the RAG path can return policy excerpts if generation is rejected. No blanket retry of state-changing writes.
- **Confirmation:** text alone cannot set `confirm_action`; unsafe hold requests are refused before a write. Idempotency keys are validated.
- **Prompt injection:** explicit checks on tool operations and grounded response heuristics. These checks reduce known risks but do not guarantee full prompt-injection resistance.
- **Logging:** request IDs, structured operational events and Prometheus metrics, without raw user questions or booking secrets. A process-local concurrency cap returns 429 when saturated.
- **Cost:** local TF-IDF, bounded context/output, no managed vector store; for Cloud Run, proposed scale-to-zero and limited instances. No GCP consumption has been validated.

## Cloud delivery

- **Target:** GCP Cloud Run, region not configured.
- **CI:** GitHub Actions on push/PR, without cloud credentials. Container smoke uses a fake provider **only** to verify infrastructure, not model quality.
- **CD:** separate manual workflow, disabled unless explicitly configured. Workload Identity Federation, dedicated runtime identity and digest-based deployment are prepared but not verified.
- **Rollback:** redeploy a previously approved image digest or roll back to a prior Cloud Run revision (pending deployment).
- **Cleanup:** remove the Cloud Run service and Artifact Registry images/repository when a GCP environment becomes available; no cloud resources were created for this submission.
- **Access restriction:** Google Cloud billing verification/access is unresolved. Request a reviewer sandbox or written exception as required by the challenge.

## Next three improvements

1. Validate Vertex AI, MCP and HTTPS end-to-end in the provided GCP environment.
2. Expand held-out evaluation (paraphrases, injection attempts and operational failures); calibrate grounding heuristics.
3. Add dependency-aware readiness and production-level rate limits/alerts.
