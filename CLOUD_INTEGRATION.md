# Cloud Integration Guide

How gryt-ci integrates with Gryt Cloud infrastructure for distributed execution and centralized visibility.

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                      Local Developer                         │
│  ┌────────────────────────────────────────────────────┐     │
│  │ gryt-ci CLI                                        │     │
│  │ - Generations/Evolutions                           │     │
│  │ - Local .gryt/gryt.db                             │     │
│  │ - Pipeline execution                               │     │
│  └────────────────┬───────────────────────────────────┘     │
│                   │                                          │
│                   │ Sync (EventBus)                         │
└───────────────────┼──────────────────────────────────────────┘
                    │
                    │ HTTPS / mTLS
                    │
┌───────────────────▼──────────────────────────────────────────┐
│               Gryt Cloud API (api.gryt.dev)                  │
│  ┌────────────────────────────────────────────────────┐     │
│  │ FastAPI + PostgreSQL                               │     │
│  │ - Generation/Evolution storage                      │     │
│  │ - Pipeline definitions                              │     │
│  │ - Jobs, Webhooks, Repos                            │     │
│  │ - User accounts, API keys                          │     │
│  └────────────────┬───────────────────────────────────┘     │
│                   │                                          │
│                   │ mTLS (private network)                  │
└───────────────────┼──────────────────────────────────────────┘
                    │
                    │
┌───────────────────▼──────────────────────────────────────────┐
│              Gryt Cloud Agents (VPC)                         │
│  ┌────────────────────────────────────────────────────┐     │
│  │ Agent 1..N                                         │     │
│  │ - Docker-based execution                           │     │
│  │ - Resource isolation                               │     │
│  │ - Parallel job execution                           │     │
│  └────────────────────────────────────────────────────┘     │
└──────────────────────────────────────────────────────────────┘
```

---

## Execution Modes

gryt-ci supports three execution modes, configured via `gryt config execution_mode`:

### Local Mode (Default)

**Behavior:**
- All pipelines execute locally
- No automatic cloud sync
- Generations/Evolutions stored in `.gryt/gryt.db`
- Full audit trail maintained locally

**Best for:**
- Development and testing
- Airgapped environments
- Simple single-developer workflows
- Maximum privacy

**Command:**
```bash
gryt config execution_mode local
```

### Cloud Mode

**Behavior:**
- Pipelines execute on Gryt Cloud agents
- Automatic sync on every generation/evolution change
- Local `.gryt/gryt.db` remains source of truth
- Cloud has complete replica for visibility

**Best for:**
- Heavy workloads requiring more resources
- Distributed teams needing shared visibility
- CI/CD integration via webhooks

**Command:**
```bash
gryt config execution_mode cloud
```

### Hybrid Mode (Recommended)

**Behavior:**
- Pipelines execute locally during development
- Sync to cloud only on promotion
- Cloud has record of all promoted releases
- Balance of privacy and collaboration

**Best for:**
- Most production workflows
- Teams needing release visibility
- Compliance and audit requirements
- Gradual cloud adoption

**Command:**
```bash
gryt config execution_mode hybrid
```

---

## Cloud Authentication

### Method 1: Username/Password

```bash
# Create account
gryt cloud signup

# Login
gryt cloud login
```

Interactive prompts for credentials, stored in `~/.gryt/config.json`.

### Method 2: API Keys (Recommended for CI/CD)

```bash
# Login with username/password first
gryt cloud login

# Create API key
gryt cloud api-keys create --name "ci-server" --expires-in-days 90

# Login with API key
gryt cloud login --method api-key
# Enter API key ID and secret
```

API keys provide:
- No password exposure in CI/CD
- Revocable access
- Expiration dates
- Per-service isolation

### Check Authentication

```bash
gryt cloud whoami
```

Output:
```
Logged in as: username
# or
Logged in with API key: key_abc123
```

---

## Cloud Resources

### Pipelines

Cloud-stored pipeline definitions accessible across projects.

**Create:**
```bash
gryt cloud pipelines create \
  --name "go-ci" \
  --description "Go testing and build" \
  --config "$(cat pipeline.yaml | base64)"
```

**List:**
```bash
gryt cloud pipelines list
```

**Use in local project:**
```python
# pipeline.py
from gryt import Pipeline
from gryt.cloud_client import GrytCloudClient

client = GrytCloudClient(username="...", password="...")
cloud_pipeline = client.get_pipeline("pipeline-id-here")

# Use cloud config
pipeline = Pipeline.from_dict(cloud_pipeline)
```

### GitHub Repositories

Connect GitHub repos to trigger cloud pipelines.

**Add repo:**
```bash
gryt cloud repos create \
  --name "my-app" \
  --url "https://github.com/owner/repo" \
  --branch "main" \
  --token "${GITHUB_TOKEN}"
```

**List repos:**
```bash
gryt cloud repos list
```

### Jobs

Link pipelines to repositories for automated execution.

**Create job:**
```bash
gryt cloud jobs create \
  --name "my-app-ci" \
  --description "CI for my-app on every push" \
  --pipeline-id "pipe-123" \
  --repo-id "repo-456" \
  --branch "main"
```

Jobs execute when:
- Webhook is triggered
- Manual execution via API
- Scheduled (future feature)

### Webhooks

Trigger jobs from external events.

**Create webhook:**
```bash
gryt cloud webhooks create \
  --name "github-push" \
  --description "Trigger on GitHub push" \
  --job-id "job-789"
```

**Output:**
```json
{
  "webhook_id": "webhook-abc",
  "webhook_key": "wh_1a2b3c4d...",
  "url": "https://api.gryt.dev/api/v1/webhooks/run/wh_1a2b3c4d..."
}
```

**Configure in GitHub:**
1. Go to repo Settings > Webhooks
2. Add webhook
3. Payload URL: (from output above)
4. Content type: application/json
5. Events: Push, Pull request

**Trigger manually:**
```bash
gryt cloud webhooks trigger wh_1a2b3c4d...
```

---

## Declarative Configuration

Apply multiple resources at once using YAML (kubectl-style).

### Example Configuration

```yaml
# infra.yaml
---
apiVersion: gryt.io/v1
kind: Pipeline
metadata:
  name: test-and-build
spec:
  description: "Test and build application"
  steps:
    - name: test
      command: "go test ./..."
    - name: build
      command: "go build -o bin/app"

---
apiVersion: gryt.io/v1
kind: GitHubRepo
metadata:
  name: my-app-repo
spec:
  git_url: "https://github.com/myorg/myapp"
  branch: "main"
  is_private: true

---
apiVersion: gryt.io/v1
kind: Job
metadata:
  name: my-app-ci
spec:
  description: "CI pipeline for my-app"
  pipeline_name: test-and-build
  github_repo_name: my-app-repo
  branch_override: "develop"

---
apiVersion: gryt.io/v1
kind: Webhook
metadata:
  name: github-webhook
spec:
  description: "Trigger CI on push"
  job_name: my-app-ci
```

### Apply

```bash
gryt cloud apply infra.yaml
```

Output shows created resources and their IDs.

### Benefits

- Version control infrastructure as code
- Atomic multi-resource updates
- Reproducible environments
- Easy replication across projects

---

## Generation/Evolution Sync

### Local-first Architecture

All operations start local:

```bash
# Create generation (local)
gryt generation new v1.0.0

# Edit generation file
vim .gryt/generations/v1.0.0.yaml

# Start evolution (local)
gryt evolution start v1.0.0 --change FEAT-001

# Run pipeline (local or cloud, based on execution_mode)
gryt run my-pipeline
```

### Automatic Sync

**Local mode:**
- No sync

**Cloud mode:**
- `generation.created` → Sync to cloud immediately
- `generation.updated` → Sync update
- `generation.promoted` → Sync promotion
- `evolution.created` → Sync immediately
- `evolution.completed` → Sync result

**Hybrid mode:**
- Only `generation.promoted` → Sync
- Only `evolution.completed` → Sync (if pass)

### Sync Mechanism

Uses EventBus and CloudSyncHandler:

```python
# Automatically attached on gryt init if credentials exist
from gryt.sync import CloudSyncHandler
from gryt.cloud_client import GrytCloudClient

client = GrytCloudClient(username="...", password="...")
handler = CloudSyncHandler(client, execution_mode="hybrid")
handler.attach()  # Listen to events
```

When event fires:
1. Local DB updated first (source of truth)
2. Event emitted
3. CloudSyncHandler receives event
4. Checks execution_mode
5. If should sync: API call to cloud
6. Cloud stores in PostgreSQL
7. `remote_id` saved to local DB for future updates

### Conflict Resolution

Local always wins. Cloud is replica.

If sync fails:
- `sync_status` set to `failed` in local DB
- Manual retry: `gryt cloud sync --force`
- Check sync status: `gryt generation show <version>`

---

## Complete Cloud Workflow

### Setup

```bash
# 1. Create cloud account
gryt cloud signup

# 2. Configure execution mode
gryt config execution_mode hybrid

# 3. Create API key for CI
gryt cloud api-keys create --name "github-actions"
```

### Define Infrastructure

```bash
# 4. Create pipeline
cat > pipeline.yaml <<EOF
apiVersion: gryt.io/v1
kind: Pipeline
metadata:
  name: production-ci
spec:
  description: "Full CI pipeline"
  steps:
    - name: test
      command: "go test ./..."
    - name: build
      command: "go build"
    - name: security
      command: "gosec ./..."
EOF

gryt cloud apply pipeline.yaml
```

### Connect Repository

```bash
# 5. Add GitHub repo
gryt cloud repos create \
  --name "production-app" \
  --url "https://github.com/myorg/app" \
  --token "${GITHUB_TOKEN}"

# 6. Create job
gryt cloud jobs create \
  --name "app-ci" \
  --pipeline-id "pipe-123" \
  --repo-id "repo-456"

# 7. Create webhook
gryt cloud webhooks create \
  --name "github-push" \
  --job-id "job-789"

# 8. Configure GitHub webhook with returned URL
```

### Local Development

```bash
# 9. Clone repo and init gryt
git clone https://github.com/myorg/app
cd app
gryt init

# 10. Create generation for next release
gryt generation new v2.0.0

# Edit .gryt/generations/v2.0.0.yaml

# 11. Develop feature
git checkout -b feature/new-feature
gryt evolution start v2.0.0 --change FEAT-100

# 12. Run pipeline locally during dev
gryt run production-ci

# Generation/Evolution NOT synced yet (hybrid mode)
```

### Promote and Sync

```bash
# 13. Merge to main
git checkout main
git merge feature/new-feature

# 14. All changes proven, promote
gryt generation promote v2.0.0

# NOW synced to cloud (hybrid mode)
# Cloud has record of v2.0.0 promotion
```

### Cloud-triggered CI

```bash
# 15. Push tag triggers webhook
git tag v2.0.0
git push origin v2.0.0

# Webhook triggers cloud job
# Agent executes pipeline
# Results visible in cloud
```

### View Results

```bash
# 16. Check cloud for execution history
gryt cloud jobs list

# Get specific execution
gryt cloud jobs get job-789

# View generations synced
gryt cloud api /api/v1/generations
```

---

## Cloud Agent Architecture

### How Agents Work

**Agent pool:**
- Multiple agent servers in VPC
- Each runs FastAPI service on port 8080
- mTLS authentication required
- Load-balanced by API server

**When job executes:**
1. Webhook triggers job
2. API server selects healthy agent
3. mTLS connection established
4. Job request sent with:
   - Pipeline definition
   - Git repo URL
   - Branch
   - Environment variables
5. Agent creates Docker container
6. Container clones repo
7. Container runs `gryt run <pipeline>`
8. Results sent back to API
9. API stores results in PostgreSQL

**Agent capabilities:**
- Resource limits (CPU, memory)
- Parallel job execution
- Docker layer caching
- Isolated workspaces
- Automatic cleanup

### Security

**Network:**
- Agents only accessible via VPC private network
- No public internet exposure
- mTLS prevents unauthorized connections
- Firewall rules block all except API server

**Authentication:**
- CA certificate validates both parties
- API client certificate
- Agent server certificate
- HMAC signature on API keys
- Per-request validation

**Isolation:**
- Each job runs in separate Docker container
- No shared state between jobs
- Containers destroyed after execution
- Workspace cleanup automatic

---

## Infrastructure Deployment

Gryt Cloud infrastructure is defined in `gryt-cloud` repository.

### Components

**Terraform:**
- DigitalOcean droplets (API, Agents)
- VPC networking
- Firewall rules
- DNS configuration

**Ansible:**
- API server deployment
- Agent server deployment
- Certificate distribution
- Application updates

**GitHub Actions:**
- API releases (tag: `api-v*`)
- Agent releases (tag: `agent-v*`)
- Fly.io deployment (push to main)

### Deployment Commands

```bash
# From gryt-cloud repository

# Deploy infrastructure
cd terraform
terraform apply

# Generate mTLS certificates
./scripts/generate_certs_from_terraform.sh

# Deploy agents
cd gryt-ci-agent/ansible
make deploy

# Deploy API
cd ../../gryt-ci-api/ansible
make deploy

# Verify connectivity
ssh root@api-server
cd /opt/gryt-ci-api
source .env
.venv/bin/python3 diagnose_agent.py
```

### Architecture

```
┌─────────────────────────────────────────────┐
│         Internet                             │
└────────────────┬────────────────────────────┘
                 │
                 │ HTTPS (443)
                 │
┌────────────────▼────────────────────────────┐
│   API Server (api.gryt.dev)                 │
│   - FastAPI + PostgreSQL                     │
│   - Public HTTPS endpoint                    │
│   - User authentication                      │
│   - Webhook receiver                         │
└────────────────┬────────────────────────────┘
                 │
                 │ mTLS (8080) over VPC
                 │
┌────────────────▼────────────────────────────┐
│   Agent Pool (VPC only)                     │
│   ┌──────────────┐  ┌──────────────┐       │
│   │  Agent 1     │  │  Agent 2     │       │
│   │  - FastAPI   │  │  - FastAPI   │       │
│   │  - Docker    │  │  - Docker    │       │
│   └──────────────┘  └──────────────┘       │
└─────────────────────────────────────────────┘
```

---

## API Reference

### Base URL

```
https://api.gryt.dev/api/v1
```

### Authentication

**HTTP Basic Auth:**
```bash
curl -u username:password https://api.gryt.dev/api/v1/pipelines
```

**HMAC API Key:**
```bash
# Automatic when using GrytCloudClient
client = GrytCloudClient(
    api_key_id="key_123",
    api_key_secret="secret_456"
)
```

### Endpoints

**Generations:**
- `POST /generations` - Create generation
- `GET /generations` - List all
- `GET /generations/{id}` - Get specific
- `PATCH /generations/{id}` - Update
- `DELETE /generations/{id}` - Delete
- `POST /generations/{id}/promote` - Promote

**Evolutions:**
- `POST /evolutions` - Create evolution
- `GET /evolutions?generation_id={id}` - List
- `GET /evolutions/{id}` - Get specific
- `PATCH /evolutions/{id}` - Update
- `DELETE /evolutions/{id}` - Delete

**Pipelines:**
- `POST /pipelines` - Create
- `GET /pipelines` - List
- `GET /pipelines/{id}` - Get
- `DELETE /pipelines/{id}` - Delete

**Jobs:**
- `POST /jobs` - Create
- `GET /jobs` - List
- `GET /jobs/{id}` - Get
- `DELETE /jobs/{id}` - Delete

**Webhooks:**
- `POST /webhooks` - Create
- `GET /webhooks` - List
- `GET /webhooks/{id}` - Get
- `DELETE /webhooks/{id}` - Delete
- `POST /webhooks/run/{key}` - Trigger (public)

**Apply:**
- `POST /apply` - Apply YAML configuration

---

## Troubleshooting

### Sync Not Working

**Check credentials:**
```bash
gryt cloud whoami
```

**Check execution mode:**
```bash
gryt config get execution_mode
```

**Check sync status:**
```bash
gryt generation show v1.0.0 | grep sync_status
```

**Force sync:**
```bash
gryt cloud sync --force
```

### Webhook Not Triggering

**Check webhook exists:**
```bash
gryt cloud webhooks list
```

**Test manually:**
```bash
gryt cloud webhooks trigger wh_key_here
```

**Check API logs:**
```bash
# On API server
journalctl -u gryt-api -f | grep webhook
```

### Agent Execution Failing

**Check agent health:**
```bash
# On API server
curl https://agent1.gryt.dev:8080/health \
  --cert /etc/gryt/certs/api-client.crt \
  --key /etc/gryt/certs/api-client.key \
  --cacert /etc/gryt/certs/ca.crt
```

**Check agent logs:**
```bash
# On agent server
journalctl -u gryt-agent -f
```

**Verify mTLS:**
```bash
# On API server
openssl s_client \
  -connect agent1.gryt.dev:8080 \
  -cert /etc/gryt/certs/api-client.crt \
  -key /etc/gryt/certs/api-client.key \
  -CAfile /etc/gryt/certs/ca.crt
```

---

## Migration Paths

### From Local-only to Cloud

```bash
# 1. Continue using local for development
gryt config execution_mode local

# 2. Set up cloud account
gryt cloud signup

# 3. Switch to hybrid for promoted releases
gryt config execution_mode hybrid

# 4. Existing generations not synced
# Only new promotions sync

# 5. Optional: Backfill historical data
gryt cloud sync --all --force
```

### From Cloud back to Local

```bash
# 1. Switch mode
gryt config execution_mode local

# 2. Local .gryt/gryt.db unchanged
# Still has all history

# 3. Cloud data remains
# Can switch back anytime
```

### Full Cloud Adoption

```bash
# 1. Set cloud mode
gryt config execution_mode cloud

# 2. Configure webhooks for all repos
# Every push triggers cloud execution

# 3. Local CLI still works
# But execution happens on agents

# 4. View results locally or via cloud API
gryt evolution list v1.0.0
# or
gryt cloud api /api/v1/evolutions
```

---

## Best Practices

### Use Hybrid Mode

Develop locally, sync promotions to cloud.

**Benefits:**
- Privacy during development
- Shared visibility of releases
- Audit trail in cloud
- Reduced API calls

### Separate API Keys per Environment

```bash
# Development
gryt cloud api-keys create --name "dev-laptop"

# CI/CD
gryt cloud api-keys create --name "github-actions"

# Production deploys
gryt cloud api-keys create --name "prod-deploy-bot"
```

Revoke compromised keys without affecting others.

### Use Declarative Config

Store infrastructure as YAML in git.

**Benefits:**
- Version controlled
- Code review
- Reproducible
- Documentation

```bash
git add cloud-config.yaml
git commit -m "Add CI pipeline configuration"
git push
```

### Monitor Sync Status

Check generations have synced:

```bash
gryt generation list | grep sync_status
```

Alert if sync failing:

```bash
# In monitoring script
if gryt generation show v1.0.0 | grep "sync_status: failed"; then
  alert "Generation sync failed!"
fi
```

### Leverage Webhooks

Automate everything:

```bash
# On push to main: Run full CI
# On push to develop: Run tests only
# On tag: Deploy to staging
# On release: Deploy to production
```

Each scenario is a separate webhook + job.

---

## Summary

**Local-first:**
- All operations start local
- `.gryt/gryt.db` is source of truth
- Cloud is optional enhancement

**Three modes:**
- Local: No sync, full privacy
- Cloud: Full sync, cloud execution
- Hybrid: Sync on promote only

**Cloud provides:**
- Distributed execution via agents
- Centralized visibility
- Webhook automation
- Team collaboration
- Audit trail replication

**Infrastructure:**
- API server (PostgreSQL)
- Agent pool (Docker execution)
- mTLS security
- VPC isolation

**Integration:**
- EventBus syncs generations/evolutions
- Declarative YAML configuration
- GitHub webhook triggers
- API key authentication

**Workflow:**
- Develop locally with full gryt-ci features
- Promote when ready
- Cloud receives promotion (hybrid mode)
- Webhooks trigger cloud execution
- Results visible via API or CLI
- Complete audit trail maintained
