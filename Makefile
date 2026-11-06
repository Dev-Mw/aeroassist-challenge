.PHONY: help install test lint run run-local evaluate-public evaluate-rag docker-build

PYTHON ?= py
BASE_URL ?= http://127.0.0.1:8080

help:
	@awk 'BEGIN {FS = ":.*##"}; /^[a-zA-Z_-]+:.*##/ {printf "%-20s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

install: ## Install runtime and development dependencies
	$(PYTHON) -m pip install -e ".[dev]"

test: ## Run public tests
	$(PYTHON) -m pytest

lint: ## Run static checks
	$(PYTHON) -m ruff check .

run: ## Start the API using Vertex AI (requires GCP configuration)
	LLM_BACKEND=vertex_ai $(PYTHON) -m uvicorn app.main:app --host 0.0.0.0 --port 8080

run-local: ## Start the same API using a local Ollama model
	LLM_BACKEND=ollama $(PYTHON) -m uvicorn app.main:app --host 0.0.0.0 --port 8080

evaluate-public: ## Run the public black-box cases against BASE_URL
	$(PYTHON) scripts/evaluate_public.py --base-url $(BASE_URL)

docker-build: ## Build the local OCI image
	docker build -t aeroassist:local .


evaluate-rag: ## Evaluate local RAG retrieval; BASE_URL for optional live HTTP evaluation
	$(PYTHON) -m scripts.evaluate_rag
