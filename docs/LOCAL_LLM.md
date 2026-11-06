# Iteration 4 — Local and cloud LLM providers

This document supplements the unchanged challenge contract. The same FastAPI,
MCP and RAG code runs in both modes. `FakeLLM` remains for tests only.

## Local with Ollama (Windows Git Bash)

1. Confirm Ollama is running: `ollama list` and `curl http://127.0.0.1:11434/api/tags`.
2. Choose a model actually shown by `ollama list`. For example, install one with
   `ollama pull llama3.2` if it is absent.
3. From the repository root, run `make install` once (existing dependencies).
4. Run `make run-local PYTHON=py OLLAMA_MODEL=llama3.2` **only if your Makefile
   passes variables via the environment**. Since the recipe uses shell variables,
   the portable Git Bash invocation is instead:

   ```bash
   OLLAMA_MODEL=llama3.2 make run-local PYTHON=py
   ```

5. In another terminal, verify `curl -i http://127.0.0.1:8080/ready` and
   `make evaluate-public PYTHON=py`.
6. Test a policy question (for example baggage) and check the `model` field,
   `citations`, and the optional generated `Resumen`. Flight and booking facts
   are still fetched via MCP and should preserve traces.

If you have a different installed model, set `OLLAMA_MODEL` accordingly. The
`/ready` check returns HTTP 503 if the local daemon or configured model is
unavailable. The app itself does not launch Ollama or download a model.

## Vertex AI / production configuration

`make run` sets `LLM_BACKEND=vertex_ai` and requires Google Cloud Application
Default Credentials, `GOOGLE_CLOUD_PROJECT`, a supported model and region.
An example for **local** Git Bash after setting up Google Cloud CLI:

```bash
GOOGLE_CLOUD_PROJECT=your-project \
GOOGLE_CLOUD_LOCATION=global \
GENAI_MODEL=gemini-2.5-flash-lite \
make run PYTHON=py
```

In Cloud Run, provide these values as service environment variables and use a
runtime service account with minimum required Vertex AI permissions. Never
commit API keys, ADC files or `.env` credentials.

The cloud deployment and a real Vertex AI inference request are **not**
verified by this iteration. `make run` starting locally does not constitute
Cloud Run deployment or production readiness.

## Design and verification boundaries

- A single `LLMProvider.generate` boundary is used for text generation.
- The LLM never constructs MCP write arguments, authorizes holds or assigns
  citation IDs. Canonical policy evidence always precedes generated summaries.
- A prompt-injected user question cannot directly invoke MCP tools; however,
  policy summarization still needs more rigorous entailment verification.
- Timeouts and token limits are configurable. Provider errors are returned via
  existing bounded HTTP errors without exposing raw exception messages.
- `make test PYTHON=py` and `make lint PYTHON=py` should be run before commit.
- Run `make evaluate-public PYTHON=py` against a running configured backend.
