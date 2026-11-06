# Technical decisions

Complete this file. Concise, evidence-based answers are preferred.

## Highest completed level

- Claimed level: No full level claimed as of iteration 4. Local functionality was demonstrated through iteration 3; Foundation and Level 1 require additional verification and deployment.
- What is demonstrably working: On the user’s Windows/Git Bash environment after iteration 3: `make test` 29 passed (one third-party deprecation warning); `make evaluate-public` 8/8 passed; retrieval evaluation precision@1 6/6, hit@3 6/6, and negative abstention 2/2. Real HTTP calls returned MCP flight status with an auditable tool trace and policy responses with a corpus `doc_id` citation. These results predate iteration 4.
- What is incomplete: Real Ollama inference and iteration-4 regression tests on the user’s machine have not yet been reported; real Vertex AI requests, Cloud Run deployment, end-to-end CI/CD, complete readiness checks, observability, idempotency hardening, stronger injection defenses, and private/held-out evaluation remain pending.

## Architecture

- Main components and request flow: FastAPI request validation (`app/main.py`) → agent (`app/agent.py`) → guarded operational routing via MCP (`app/operations.py`, `app/mcp_client.py`) for dynamic flight/booking facts, or paragraph-level policy retrieval (`app/rag.py`) for versioned documents; response preserves external HTTP schema, tool traces, and corpus citations. Iteration 4 adds configured LLM provider selection and optional evidence-bound policy summarization.
- Why this LLM/provider abstraction: Preserve the supplied `LLMProvider` interface and inject interchangeable adapters. Ollama provides offline local inference (`make run-local`), Vertex AI/Gemini is the intended deployment provider (`make run`), and FakeLLM is for controlled tests. The domain/routing logic does not depend on provider-specific SDKs.
- Why this tool orchestration approach: Explicit, constrained operational routing prevents model-generated tool parameters from directly causing state changes. Confirmed holds additionally require affirmative user intent, `confirm_action=true`, and booking/flight checks. This is intentionally narrower than an unrestricted autonomous agent.
- Why this retrieval/index strategy: Local scikit-learn TF-IDF word/character retrieval is cost-effective for the supplied small synthetic corpus, supports deterministic paragraph citations and abstention, and avoids unnecessary managed vector infrastructure. SHA-256 identifies source-corpus index versions; refresh can rebuild upon reviewed corpus changes.

## Evaluation

- Metrics used: Existing pytest tests, public golden-set pass count, retrieval precision@1, hit@3 and negative-query abstention. Request latency is surfaced per response, but production latency/error distributions are not yet measured.
- Baseline and final results on the public golden set: Iteration 1: 2/8 (offline fake); iteration 2: 7/8 on user machine with live MCP; iteration 3: 8/8 on user machine with MCP + extractive RAG. The iteration-4 version has NOT yet been evaluated on the user’s Ollama setup, so 8/8 is the latest *verified* result, not a verified final score.
- One failure you investigated and what changed: `public-02-policy-baggage` failed with no `BAGGAGE-001` citation (iteration 2). Added versioned paragraph retrieval and grounded citations in iteration 3; that case then passed in the user’s public evaluation.

## Reliability, security and cost

- Timeout/retry/fallback policy: Configurable bounded model timeouts and output-token limits were added in iteration 4; verify behavior against live Ollama and Vertex AI. Avoid unbounded retry chains and do not mask provider failures as successful grounded answers. No production-grade retry/backoff guarantee is claimed yet.
- Confirmation and idempotency policy: `create_reaccommodation_hold` requires affirmative action language, `confirm_action=true`, validated booking/eligible flight, and an idempotency key; returned traces redact sensitive identifiers. Robust replay/session binding and concurrent idempotency validation need further verification.
- Prompt-injection/data-exfiltration controls: LLM does not directly control MCP write calls or invent citations; retrieval IDs come from the corpus and operational facts from tools. This is a partial defense only; adversarial policy text, untrusted model output, stronger prompt-injection testing, and outbound-network restrictions are pending.
- Logging and PII policy: No user message, booking code, idempotency secret, raw prompt or provider credential should be included in traces/logs; tool-call results redact sensitive keys. Structured JSON logs, request correlation and low-cardinality operational metrics remain to be implemented/verified.
- Expected cost drivers and limits: Local Ollama incurs local compute; Vertex AI bills model usage; Cloud Run/Artifact Registry add hosting and storage. Bound output tokens, timeouts, instances and concurrency; set cost alerts before deployment. Exact cost has not been measured.

## Cloud delivery

- Platform and region: Planned GCP Cloud Run in `us-central1` per `docs/DEPLOY_GCP.md`; Vertex AI location/model availability to be confirmed. Not yet deployed.
- Authentication from CI/CD: Planned GitHub Actions → Google Cloud Workload Identity Federation, scoped to the private repository and approved branch; not yet configured/verified.
- Runtime identity: Planned dedicated Cloud Run service account with least-privilege Vertex AI permissions, using application default identity (no downloaded long-lived keys); not yet configured/verified.
- Rollback procedure: Planned Cloud Run revision rollback to a previously verified revision; exact service/revision names will be documented and tested during deployment.
- Cleanup command: After review, planned targeted `gcloud run services delete aeroassist --region us-central1 --project "$GOOGLE_CLOUD_PROJECT"` and targeted cleanup of challenge-only Artifact Registry images; do not execute before review or delete shared resources.

## Next three improvements

1. Run iteration-4 `make test`, `make lint`, local Ollama end-to-end probes, and the complete public evaluator; check citations and tool traces remain authoritative.
2. Harden safety and LLMOps: mixed MCP+RAG requests, injection/unsafe arguments, idempotency replays, request-scoped structured logs, metrics, and readiness.
3. Deploy to GCP Cloud Run using reviewed CI/CD and federated identity; verify HTTPS, rollback, and targeted teardown.


## Iteration 1 verification (2026-11-04)

- This is an incremental, **incomplete** baseline rather than a scored submission.
- Verified: local HTTP `/v1/chat` now responds; seven public unit/contract tests pass.
- Public golden: **2/8**, with the six other cases failing because tool calls, citations and action confirmation have not been implemented yet.
- Current backend is an offline deterministic fake for validating the HTTP boundary; it is not a real generative provider and no Core level is claimed.
- Next priorities: integrate the MCP client with strict write confirmation and audited traces; implement an indexed policy retriever with justified citations; add a real configurable provider and production hardening.


## Iteration 2 — MCP operational integration (pending real stdio validation)

- Added `app/mcp_client.py`: uses the provided MCP server through stdio and `ClientSession`; business records were not copied or altered.
- Added `app/operations.py`: constrained routing and validated tool arguments; no LLM-generated tool arguments are trusted. Creating a hold requires explicit textual intent, `confirm_action=true`, valid idempotency key, verified booking and an eligible flight on the same date/route.
- Booking codes and idempotency keys are redacted from returned tool-call traces.
- `app/agent.py` invokes the operational service first, preserving the existing fallback provider for unhandled questions; `app/main.py` maps unsafe requests to HTTP 400.
- Unit and HTTP contract tests use a test-only MCP stand-in. Separate integration tests exercise **real stdio** if the MCP SDK is available.
- This execution environment has no installed `mcp` package and cannot reach the package index, so live MCP stdio integration **has not been verified here**. The real integration tests will run on a machine with `make install`.
- Remaining work: real Vertex AI provider, RAG, broader intent handling, stronger action confirmation/session binding, cloud deployment, hardening and golden-set E2E verification. **No additional level is claimed complete.**

## Iteration 3 — local policy retrieval (RAG groundwork)

- Preserved `app.rag.Retriever`, `RetrievedChunk`, the external HTTP schema and all synthetic corpus files. Added paragraph-level lexical retrieval with scikit-learn TF-IDF (word and character n-grams). We chose this instead of a managed vector database because the corpus is tiny, fixed and inexpensive to index in-process.
- Each citation is derived from a retrieved corpus paragraph and preserves its front-matter `doc_id` and title. `chunk_id` is deterministic (`doc_id#pN`) for a given document version. A SHA-256 digest of document names and bytes identifies the index build. `Retriever.refresh()` rebuilds the index when the versioned corpus is updated; production refresh should be performed via a reviewed release and new instances.
- Initial response generation is deliberately **extractive**: the selected policy paragraph is surfaced verbatim with a citation. This is evidence-based, but it is not yet generative RAG with a real LLM. The `FakeLLM` fallback is unchanged for unsupported requests. A real, configurable Vertex AI provider and grounding verification remain outstanding.
- Retrieval thresholds and small domain vocabulary boost abstention over false citations. These are initial heuristics, not calibrated thresholds. Policy and operational information must remain separate; dynamic flight queries continue to use MCP.
- `python scripts/evaluate_retrieval.py` (with project root on PYTHONPATH) reports P@1, hit@3 and abstention against a small hand-written retrieval set. This evaluation is not a substitute for hidden/held-out cases.
- Local verification: **26 passed** using the available dependencies. The local retrieval suite reported P@1=6/6, hit@3=6/6 and negative abstention=2/2. MCP SDK and Ruff were unavailable in this execution environment, so the real stdio tests were skipped and lint was not verified here. Remote/public end-to-end evaluation must be repeated on the recipient's fully installed environment.
- No Level 3 or production capability is claimed complete: index performance on harder queries, real LLM-based answer composition, prompt-injection defense, policy+operation joint answers and Cloud Run deployment require further work.


## Iteration 4 — interchangeable LLM adapters (local verification pending)

- Preserved the existing `LLMProvider` protocol and `FakeLLM` test adapter. Added `OllamaLLM` for local development using the non-streaming localhost HTTP API and `VertexAILLM` using the existing `google-genai` dependency. The factory chooses the provider via `LLM_BACKEND` and validates token/timeout limits.
- `make run-local` selects Ollama, while the existing `make run` target selects Vertex AI. The HTTP application and MCP/RAG operations are shared; production requires Google Cloud credentials and a configured project. No provider/API keys are committed.
- Operational answers and tool execution remain deterministic and sourced from MCP. For policy answers, the canonical paragraph and its citation are always preserved; an optional bounded model-generated summary can be appended. Unsupported questions abstain without calling a model. This does **not** prove model-generated summaries are fully entailed; additional grounding verification is necessary before claiming full production quality.
- `GET /ready` performs a bounded availability/model check for Ollama. Vertex AI credentials and real generation are not testable here and remain to be verified in the target account; readiness of the whole MCP dependency graph remains a follow-up.
- Dependencies: moved `httpx` to runtime because Ollama requests require it; no new agent framework or vector DB introduced. `docs/AI_USAGE.md` remains the exact untouched original template for user-supplied disclosure.
- Verification in this execution environment: offline HTTP/unit suite passes, including mocked Ollama API requests and grounded policy behavior. **Real Ollama and Vertex AI calls have not been executed here.** Public golden set and lint should be repeated on the recipient's machine. No scored level is claimed solely on these tests.

## Iteration 4 follow-up — multi-document grounding and HTTPX2

- Added `Retriever.search_diverse()` as a post-ranking step that retains at most one scored paragraph per policy. This avoids a single policy consuming the context budget for compound questions; existing `search()` and the underlying index remain unchanged.
- The agent passes the retrieved policy excerpts and their identifiers to the configured LLM; cites only those corpus paragraphs. The excerptive baseline remains visible, and accepted model wording is appended as an explanation. Rejection/fallback is logged without raw user prompts. Numeric claims absent from evidence and URLs are rejected, but **these simple guards cannot prove semantic entailment**; stronger claim-level checks remain pending.
- Updated first-party Ollama adapter/test imports and direct dependency to HTTPX2 (`httpx2>=2.13,<3.0`) following Starlette's recommendation. External dependency compatibility and an actual HTTPX2 + Ollama run must be verified on the user's machine.
- Local test suite: **42 passed, 1 skipped** using an HTTPX 1.x import shim solely because HTTPX2 cannot be downloaded into the isolated environment. This is **not** a validated HTTPX2 installation, live Ollama test or production grounding guarantee.

## Iteration 5 — single response and offline RAG quality checks

- The policy branch now returns one generated answer when it passes conservative
  guards. It no longer concatenates complete retrieved paragraphs with the model
  output. If generation fails or misses a retrieved topic, it returns the
  original extractive fallback and logs the reason without exposing prompts.
- Added `app/grounding.py` to separate response checks from orchestration.
  These are **heuristics**, not semantic entailment or guaranteed injection defense.
  Retrieved evidence and citation identifiers remain application-owned.
- Added `scripts/evaluate_rag.py`, `make evaluate-rag` and
  `docs/RAG_EVALUATION.md`. The metrics are RAGAS-inspired deterministic proxies,
  **not** scores produced by the RAGAS library. An optional live-API mode checks
  answer topic coverage and citations. Public golden and MCP safety cases must
  remain part of the regression suite.
- Kept the original `docs/AI_USAGE.md` template intact for developer disclosure.
- Local environment verification: unit tests pass with a temporary **HTTPX 1.x
  import shim** because HTTPX2 cannot be installed in this isolated environment.
  This does not establish HTTPX2, local Ollama or Vertex AI compatibility;
  run `make install`, `make test`, `make lint`, `make evaluate-rag` and
  `make evaluate-public` in the fully provisioned development environment.

## Iteración 5b — cobertura de necesidades y evaluador individual

- Se conserva el índice lexical TF-IDF original. `search_for_needs` reutiliza el retriever por segmentos de la consulta y fusiona candidatos por `doc_id`, sin vectores ni infraestructura adicional.
- El agente usa hasta cinco documentos y controla un presupuesto conservador de caracteres (`RAG_CONTEXT_MAX_CHARS`), sin truncar el texto de una cita. No garantiza todos los límites del tokenizer de inferencia; es una defensa inicial verificable.
- La evaluación offline muestra cada caso simple, compuesto o sin soporte, documentos faltantes y cobertura literal de temas al consultar la API. Son métricas deterministas; no equivalen a RAGAS ni a una verificación semántica de hechos.
- Resultados de referencia obtenidos localmente con un adaptador temporal de pruebas para `httpx2`, pues este paquete no está disponible en el entorno de revisión. La prueba contra Ollama y HTTPX2 reales debe realizarse en Windows.

## Iteration 6 — initial observability and bounded readiness

- Added `app/observability.py` for low-cardinality Prometheus counters and request latency with no new runtime dependencies. HTTP middleware owns correlation headers, request status, and safe operational events; the existing `/metrics` endpoint now exports histogram data. MCP tool metrics are derived from tool traces returned by successful requests.
- Selected allowlisted structured logging instead of free-form request logging, to avoid exposing prompt, booking or session content. `LOG_FORMAT=json` activates JSON operational events.
- `/ready` now caps its existing provider probe at two seconds and treats provider exceptions as not ready; MCP and RAG dependency probes remain future work. `/health` still avoids dependencies.
- Tests cover correlation, metrics, schema errors, privacy, readiness failures and a basic prompt-injection abstention case. They do not prove comprehensive injection resistance. See `docs/OBSERVABILITY.md` for commands, limitations and pending architecture diagrams.
- Independent user verification is still required for real HTTPX2, Ollama, MCP stdio, Ruff and the black-box evaluation. No completed production level claimed.

## Iteration 6b — code quality and Prometheus exposition

- Addressed first-party Ruff findings with formatting-only changes, removed a duplicate
  stopword and a redundant timeout exception alias, and explicitly used `strict=True`
  when combining equal-length TF-IDF score vectors. The latter asserts an expected
  invariant, rather than silently truncating mismatched vectors.
- Preserved the supplied `mcp_server/` source and excluded that directory from
  first-party Ruff checks. Public evaluation scripts retain their original behavior;
  their URLs are restricted to HTTP(S), and scoped `S310` comments document the
  validated network call sites rather than globally disabling the security rule.
- Corrected Prometheus metadata so each metric family has a matching `HELP` and
  `TYPE` immediately before its samples. Both the aggregate request counter and the
  separately labeled HTTP counter remain available for compatibility. Added a
  regression test for labeled counters and histogram metadata.
- Verification: local unit suite with a temporary HTTPX-to-HTTPX2 testing alias;
  `httpx2`, Ruff and cloud dependencies are unavailable in this isolated environment.
  The user's installed Windows environment must run `make lint`, `make test`, the public
  evaluator, and RAG evaluator before claiming a fully validated CI-quality gate.
- No MCP business records, HTTP API contracts, provider configuration or indexed
  policy content were changed by this patch.


## Iteration 7 — bounded request admission and MCP abuse regression

- Added process-local, nonblocking `/v1/chat` admission (`MAX_CONCURRENT_CHATS`,
  default 8, allowed 1–100). Saturation returns HTTP 429 with a request ID, before
  any MCP or model work. A `finally` block releases capacity after success,
  validation failure, provider failure or timeout. Rate limiting across Cloud Run
  instances **is not** provided by this mechanism and requires ingress controls.
- Retained existing MCP routing, server data, explicit `confirm_action` and
  booking/flight/seat checks. Tests cover refusal before authorization, malicious
  requests with `confirm_action=false`, upstream 502/504 and bounded admission.
- Restricted idempotency-key parsing to ASCII letters, digits, underscore and
  hyphen. This is a narrower input validation policy for a tool argument; no
  response schema or business record is changed.
- No new dependencies or framework. Existing MCP call timeout remains configurable
  with `MCP_TIMEOUT_SECONDS`; LLM timeout and output bounds are preserved.
- Remaining risks: model prompt injection cannot be proven absent; semantic
  grounding remains heuristic, writes are not globally rate limited, readiness
  does not probe every MCP resource, and real cloud security/CD is pending.

## Iteration 8 — OCI container and reviewed CI/CD path

- Retained the provided Python 3.12 slim, port 8080 and non-root `app` runtime. Added a local-only liveness `HEALTHCHECK` and `exec` for clean termination. Image defaults to the Vertex AI backend; CI explicitly overrides the backend with `fake` **only for isolated container smoke testing**.
- CI runs Ruff, pytest and offline RAG checks on pull requests and pushes to `main`; the container job depends on those checks and builds/starts the actual image. This is a smoke test, **not** proof of working Vertex AI or MCP in Cloud Run.
- CD is a `workflow_run` triggered exclusively by a successful `ci` push run on the same repository's `main`. It checks out `head_sha`, uses Workload Identity Federation, pushes the SHA-tagged image to Artifact Registry and deploys its immutable digest to Cloud Run. Configure branch protection and a `production` environment requiring review; neither can be enforced by repository YAML alone.
- Production runtime uses a distinct service account and private Cloud Run (`--no-allow-unauthenticated`) by default. Reviewers must have invocation access and use an identity token. Never commit service account keys.
- Cost guardrails: min instances 0, max 2, concurrency 8, output tokens configured separately. 1 GiB is a conservative starting memory allocation for Python/ML dependencies; validate usage and charges before optimizing.
- **Not verified yet:** Docker execution and CI/CD runs in GitHub, configured Google Cloud credentials/project, Vertex AI, access by reviewers, rollback. Do not count Foundation/CD as complete until these checks pass and evidence links exist.

## Iteration 8b — CI-only handoff before challenge submission

- Retained `.github/workflows/ci.yml` for push and PR validation: Ruff, pytest, offline RAG, OCI build and HTTP smoke test as non-root. This pipeline uses no cloud credentials.
- Changed `.github/workflows/cd.yml` from automatic `workflow_run` to manual `workflow_dispatch`, additionally gated by `GCP_DEPLOY_ENABLED=true` and project configuration. It cannot deploy as a side effect of pushing to main. No GCP changes performed.
- Manual CD must be independently authorized and its commit's CI status checked when cloud access exists; neither CI success on GitHub nor any GCP deployment is claimed by this edit.
- Explicitly separated demonstration of OCI packaging from real LLM operations; `LLM_BACKEND=fake` is only infrastructure smoke test.
