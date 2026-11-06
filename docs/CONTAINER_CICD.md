# Container and CI/CD — iteration 8

The deployment target required by the challenge is **Cloud Run**, with a container listening on port 8080 as a non-root user. `docs/API_CONTRACT.md` is unchanged.

## Local build and smoke test

Prerequisite: Docker Engine or Docker Desktop is running. In Git Bash, from the repository root:

```bash
make docker-build
docker run -d --name aeroassist-smoke -e LLM_BACKEND=fake -p 127.0.0.1:18080:8080 aeroassist:local
curl -i http://127.0.0.1:18080/health
curl -i http://127.0.0.1:18080/ready
curl -i http://127.0.0.1:18080/v1/capabilities
docker inspect --format='{{.Config.User}}' aeroassist-smoke
docker logs aeroassist-smoke
docker rm -f aeroassist-smoke
```

Expected: 200 health/readiness in **CI smoke mode only**, user `app`, and normal API startup. `LLM_BACKEND=fake` is never intended for deployment. Do not claim a full LLM/MCP integration from this smoke test. For an operational test, use the configured real provider and `make evaluate-public` against that service.

## CI

`.github/workflows/ci.yml` runs on PRs and pushes to `main`:

1. Python 3.12, `make lint test`, `make evaluate-rag` (offline).
2. Build OCI image; execute HTTP smoke in container as `app` on port 8080.

Use required status checks and PR review protection for `main`. The workflow does not require GCP credentials.

## CD — intentionally disconnected and disabled

`.github/workflows/cd.yml` is **manual only** (`workflow_dispatch`) and has a job-level guard requiring `GCP_DEPLOY_ENABLED=true`, `main`, and all necessary GCP configuration variables. It **never** runs after CI automatically. With no GCP account, do not set `GCP_DEPLOY_ENABLED`. CI works without any GCP secrets or billing account.

When GCP becomes available, separately verify the commit's successful CI run before manually starting CD; workflow_dispatch by itself does **not** establish CI provenance. The existing deployment logic is unverified and remains future work.

Set the following GitHub Actions **repository variables**, not credentials:

| Variable | Description |
| --- | --- |
| `GCP_PROJECT_ID` | Cloud project ID |
| `GCP_REGION` | Cloud Run + Artifact Registry region, e.g. `us-central1` |
| `GCP_ARTIFACT_REPOSITORY` | Existing Docker repository name |
| `GCP_WIF_PROVIDER` | Full Workload Identity Provider resource name |
| `GCP_DEPLOY_SA` | Email of deployer service account |
| `GCP_RUNTIME_SA` | Email of runtime service account |
| `GENAI_MODEL` | Vertex AI model available to the project |

Before running CD, create the Artifact Registry repository; enable Cloud Run, Artifact Registry, Vertex AI, IAM Credentials, and Security Token Service as needed. Configure a Workload Identity Federation provider restricted to **this repo and main-branch trusted events**, and grant the deployer least-privilege Artifact Registry writer, Cloud Run deployer and runtime-service-account impersonation permissions. Runtime identity needs Vertex AI invocation and only relevant operational permissions. **Do not create downloadable JSON keys**. Test each IAM binding; exact permissions depend on project policies.

Cloud Run is deployed **private** (`--no-allow-unauthenticated`) to avoid exposing a state-changing tool to anonymous callers. The reviewer needs Cloud Run Invoker permission. For an authenticated check, an authorized principal can send a Google-signed identity token to the Cloud Run service URL. Evaluation scripts currently do not implement that authentication; either run them in an authenticated test harness or add an opt-in bearer header after reviewing the contract (do not expose tokens in logs).

## Evidence and failure modes

Capture successful CI run URL; when GCP is later enabled, capture the approved CD run URL, source commit SHA, immutable image digest, Cloud Run revision, authorized HTTPS test results, and `make evaluate-public` output. A prepared CD workflow is not a deployed CD path until an actual authorized run finishes successfully.

Known limitations: no Docker daemon in the assistant's build environment, no cloud account attached, and Cloud Run/MCP/Vertex AI not verified end-to-end yet. Local CI smoke uses `fake` only for infrastructure isolation.

## Rollback and cleanup

To roll back, first inspect revisions and choose a **known good** revision:

```bash
gcloud run revisions list --service aeroassist --region "$GCP_REGION" --project "$GCP_PROJECT_ID"
gcloud run services update-traffic aeroassist --to-revisions "GOOD_REVISION=100" --region "$GCP_REGION" --project "$GCP_PROJECT_ID"
```

To clean up **only this challenge service**, after the reviewer finishes:

```bash
gcloud run services delete aeroassist --region "$GCP_REGION" --project "$GCP_PROJECT_ID"
```

Remove challenge-specific Artifact Registry images and unused identities only after checking their ownership; do not delete a shared project or repository indiscriminately.

Until the `GCP_DEPLOY_ENABLED` variable is explicitly set to `true` AND the required GCP variables are configured, the CD deployment job is **skipped**, not treated as a successful cloud deployment. The workflow itself is manual and never triggered by CI.
