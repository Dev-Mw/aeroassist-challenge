# AI assistance disclosure

## Tools used

| Tool/model | Tasks | Approximate share | How output was verified |
| --- | --- | --- | --- |
| ChatGPT | Help with implementation, tests, debugging, CI workflows and documentation across the challenge | **Candidate to confirm** | Local pytest/Ruff, public golden set, RAG checks, manual Ollama queries, Docker smoke test and green GitHub CI |

## Material changes made after AI output

- Iterated on test failures and a real model error that confused flight refunds with baggage refunds; added regression checks and extractive fallback.
- Corrected Ruff findings, line endings and the GitHub container startup retry after observing CI failures.
- Kept GCP deployment inactive because cloud access and billing verification were not completed.

## One suggestion rejected and why

- Did not introduce embeddings, a vector database or an agent framework: for this small synthetic corpus and fixed tools, they would increase complexity without demonstrated benefit.

## Files or areas written without AI assistance

- **Candidate to complete accurately.** The challenge-provided MCP data, policy corpus, notebook and contract are supplied material; they should not be presented as original handwritten work.

## Known uncertainty

- Vertex AI, Cloud Run HTTPS and CD have not been tested on GCP. The grounding guards are heuristic, not a guarantee of semantic correctness or injection resistance. The CI container smoke uses `LLM_BACKEND=fake`; real Ollama behavior was tested separately on the developer's machine.
