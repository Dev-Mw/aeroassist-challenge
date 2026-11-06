# AI assistance disclosure

Using AI is allowed. This disclosure is not scored by the amount of AI used; it supports a fair discussion of ownership.

## Tools used

| Tool/model | Tasks | Approximate share | How output was verified |
| --- | --- | ---: | --- |
| ChatGPT (asistencia de código) | Diseño de telemetría, pruebas de seguridad, documentación técnica (iteración 6) | Por confirmar por el responsable | Suite local reproducible y verificación manual pendiente en Windows/Ollama/GCP |

## Material changes made after AI output

- Iteration 1: API baseline added; retain as an intermediate scaffold rather than evidence of an operational LLM.
- Iteration 2: constrained MCP routing with explicit hold confirmation and auditable traces; user verified live flight-status invocation and 7/8 public cases.
- Iteration 3: TF-IDF paragraph retriever and citations; user verified 8/8 public cases and retrieval metrics.
- Iteration 4: proposed provider adapters and configuration for local Ollama and production Vertex AI; live inference and regressions remain pending.
- The owner should amend this section with any independent edits, code review, rejected patches, or refactors actually performed before submission. 
- Iteración 6: comprobaciones de instrumentación, prueba de recuperación de política de seguridad y ajuste de expectativa: recuperar una política de seguridad no implica ejecutar una instrucción adversarial.
- Iteración 6b: revisión asistida de hallazgos Ruff, formato de código, metadatos Prometheus y pruebas de regresión. Los cambios requieren ejecución de Ruff y HTTPX2 reales en el entorno del responsable.
- Iteración 7: asistencia para un control acotado de concurrencia, pruebas de error y confirmación de MCP, y documentación de límites. Pendiente de revisión y verificación por el responsable.
- 

## One suggestion rejected and why

- No introducir almacenamiento vectorial/embeddings para observabilidad: no lo exige el desafío y aumentaría la complejidad sin valor demostrado.
- 

## Files or areas written without AI assistance

- Pendiente de declaración por el responsable del proyecto; no se infiere autoría.
- 

## Known uncertainty

- La iteración 6 fue validada por el responsable con 67 tests aprobados y 8/8 casos públicos; la iteración 6b requiere repetir lint y evaluación tras el parche. HTTPX2 y Ruff no están disponibles en el entorno aislado de preparación del parche.
- Los controles de prompt injection y readiness aún son parciales.
- 


### Iteration 8 — deployment pipeline assistance

ChatGPT assisted with minimal updates to the existing Dockerfile and GitHub Actions CI/CD workflows, plus container smoke-test and operational documentation. Decisions requiring verification by the candidate include GitHub branch and environment protections, Workload Identity Federation trust conditions, least-privilege service account permissions, HTTPS access and the first successful Cloud Run deploy. These were not verified in a live GCP environment at the time of authoring.
