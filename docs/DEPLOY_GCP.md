# GCP deployment bootstrap

Cloud Run is the required deployment target; these exact commands are only a bootstrap reference. You may use any IaC and CI/CD platform, and you remain responsible for least privilege, reproducibility and cleanup.

## Cost-conscious target

- Cloud Run, request-based billing
- `us-central1`
- 1 vCPU, 512 MiB
- min instances 0, max instances 2
- concurrency 20
- request timeout 60s
- Artifact Registry image under 0.5 GB where practical

New eligible accounts currently receive a Google Cloud trial; verify current terms before use. If your account is billable, create a budget alert.

## Runtime identity

Create a dedicated service account. If you use Vertex AI, grant it only the role needed to invoke the model (`roles/aiplatform.user`) and logging permissions. Do not download a JSON key for the service.

```bash
gcloud services enable run.googleapis.com artifactregistry.googleapis.com aiplatform.googleapis.com

gcloud iam service-accounts create aeroassist-runtime \
  --display-name="AeroAssist runtime"

gcloud projects add-iam-policy-binding "$GOOGLE_CLOUD_PROJECT" \
  --member="serviceAccount:aeroassist-runtime@${GOOGLE_CLOUD_PROJECT}.iam.gserviceaccount.com" \
  --role="roles/aiplatform.user"
```

## First manual smoke deployment

You may deploy from source for the first smoke test. Your final submission still needs an automated CD path.

```bash
gcloud run deploy aeroassist \
  --source . \
  --region us-central1 \
  --allow-unauthenticated \
  --service-account "aeroassist-runtime@${GOOGLE_CLOUD_PROJECT}.iam.gserviceaccount.com" \
  --cpu 1 \
  --memory 512Mi \
  --min 0 \
  --max 2 \
  --concurrency 20 \
  --timeout 60 \
  --set-env-vars "APP_ENV=prod,LLM_BACKEND=vertex,TOOL_BACKEND=mcp,GOOGLE_CLOUD_PROJECT=${GOOGLE_CLOUD_PROJECT},GOOGLE_CLOUD_LOCATION=global,GENAI_MODEL=${GENAI_MODEL}"
```

Cloud Run prints the HTTPS URL. Run public evaluation against it and record the exact deployed revision.

## CI/CD authentication

For GitHub Actions, prefer Workload Identity Federation over a long-lived service-account JSON key. Restrict the identity provider to your repository and main branch/environment. Store non-sensitive project/region values as repository variables.

## Cleanup

Document exact targeted commands. At minimum remove the Cloud Run service and unneeded images after review:

```bash
gcloud run services delete aeroassist --region us-central1
```

Never use a broad deletion command or delete a shared project.

## Iteration 8 deployment workflow

The original commands above remain a bootstrap example, not the current release process. The reviewed CI/CD implementation and its required repository/GCP configuration are documented in [`CONTAINER_CICD.md`](../../docs/CONTAINER_CICD.md). The automated workflow defaults to **private Cloud Run** and 1 GiB RAM; it deploys the digest built from the exact CI-verified commit. Do not treat this path as verified until a GitHub Actions deployment actually succeeds and an authorized caller can exercise the HTTPS API.
