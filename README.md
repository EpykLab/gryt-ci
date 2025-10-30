# **gryt-ci** – *Composable, Contract-Driven CI for Secure Evolvability*

> **Move fast — and stay in control.**
> gryt-ci is a **local-first, platform-agnostic CI framework** that turns raw velocity into **governed, auditable, and resilient releases**.
> Built on **atomic contracts** (Generations) and **iterative proof** (Evolutions), gryt-ci ensures **nothing ships until the declared intent is 100% realized** — while preserving maximum execution speed.

---

## Table of Contents
- [Core Primitives](#core-primitives)
- [Release Model: Generation & Evolution](#release-model-generation--evolution)
- [Why Contract-Based Releases?](#why-contract-based-releases)
- [Secure Evolvability (NIST 800-161)](#secure-evolvability-nist-800-161)
- [CLI & Workflow](#cli--workflow)
- [Database & Audit Trail](#database--audit-trail)
- [Catalog System](#catalog-system)
- [Installation](#installation)
- [Quick Start](#quick-start)
- [Examples](#examples)
- [Contributing](#contributing)

---

## Core Primitives

| Primitive | Definition | Role | Composition |
|---------|------------|------|-------------|
| **Step** | Atomic executable action (`go test`, `echo "hello"`). | Smallest **executable** unit. | → **Pipeline** |
| **Pipeline** | Ordered or parallel set of **Steps** + **Runners** + config. | **Unit of execution**. | → **Runtime**, references **Data**, **Hooks**, **Destinations**, **Versioning** |
| **Data** | Immutable artifact/log row in `.gryt/gryt.db` (SQLite). | **Storage & proof**. | Produced by **Steps**, consumed by **Hooks** |
| **Runtime** | Local execution sandbox (Python-based, no containers). | **Host environment**. | Executes **Runners** |
| **Runner** | Scheduler driving **Steps** (sequential/parallel). | **Orchestrator**. | Inside **Pipeline** |
| **Versioning** | SemVer + Git-tag mapping. | **Release tracking**. | Applied to **Generations/Evolutions** |
| **Hooks** | Event callbacks (`pipeline_start`, `step_fail`). | **Observability & policy**. | Attached to **Pipeline** |
| **Destinations** | External sinks (S3, Slack, Prometheus). | **Export**. | Receive **Data** |

---

## Release Model: Generation & Evolution

| Term | Definition | Relationship |
|------|-----------|--------------|
| **Generation** | **Release Contract** – declarative blueprint of *what* `vX.Y.Z` **must** contain (Fix/Refine/Add/Remove). | 1 Generation → N Evolutions |
| **Evolution** | **Point-in-time proof** – a tagged pipeline run (`vX.Y.Z-rc.12`) that realizes one or more declared changes. | 1 Evolution = 1 Pipeline run + 1 Version tag |
| **Change Type** | One of: **Fix**, **Refine**, **Add**, **Remove** | Defined in Generation → proven in Evolutions |

```mermaid
graph TD
    G[Generation v2.2.0<br/>Fix A, Refine B, Add C] --> E1[Evolution v2.2.0-rc.1<br/>Fix A]
    G --> E2[Evolution v2.2.0-rc.2<br/>Refine B]
    G --> E3[Evolution v2.2.0-rc.3<br/>Add C]
    E1 & E2 & E3 --> R[v2.2.0<br/>Deployable]
```

### Generation File (`.gryt/generations/v2.2.0.yaml`)
```yaml
version: v2.2.0
description: "Payment gateway overhaul"
changes:
  - type: fix
    id: PAY-001
    title: "Race condition in refund webhook"
  - type: refine
    id: PAY-002
    title: "Reduce latency of status polling"
  - type: add
    id: PAY-003
    title: "Support Apple Pay"
pipeline_template: release-pipeline
```

---

## Why Contract-Based Releases?

| Goal | Push-Every-Commit | gryt-ci |
|------|-------------------|--------|
| **Velocity** | Immediate deploy | Same speed + **parallel Runners** |
| **Atomicity** | Partial changes leak | **Generation** = complete contract |
| **Secure Evolvability** | Drift, tech debt | **Explicit intent + proof** |
| **Guardrails** | None | **Hooks**, **DB**, **policy checks** |
| **Emergency Fixes** | Bypass CI | **Hot-fix Generation** (`v2.2.1`) |

> **Even a single-line bug fix is a Generation.**
> `v2.2.1` → alpha → beta → RC → prod.
> Speed is preserved. **Control is never sacrificed.**

---

## Secure Evolvability (NIST 800-161)

> **“A system must be able to evolve securely.”**

gryt-ci **enforces** this by:

- **Declarative intent** (Generation)
- **Immutable proof** (Data rows per Evolution)
- **Audit trail** (SQLite DB)
- **Policy gates** (Hooks fail on violation)
- **Promotion gate** (100% PASS required)

**Result:** Velocity **without** long-term degradation.

---

## CLI & Workflow

```bash
# Initialize project
gryt init

# Create a release contract
gryt generation new v2.2.0

# Start an evolution (proves one or more changes)
gryt evolution start v2.2.0 --change PAY-001

# List progress
gryt evolution list v2.2.0

# Promote when complete
gryt generation promote v2.2.0   # → tags v2.2.0, marks deployable
```

---

## Database & Audit Trail

```sql
-- .gryt/gryt.db
TABLE generations (version, status, created_at)
TABLE generation_changes (generation_id, change_id, type, title)
TABLE evolutions (tag, generation_id, change_id, status, pipeline_run)
TABLE pipeline_runs (id, pipeline_name, status, started_at)
TABLE data_rows (evolution_id, step_name, metric, value, artifact_path)
```

Query examples:
```bash
gryt db query "SELECT * FROM evolutions WHERE generation_id = 'v2.2.0'"
gryt db metric pass_rate --gen v2.2.0
```

---

## Catalog System

Reusable components defined in **language-specific catalogs**:

```python
# examples/language_go.py
steps = {
    "test": {"cmd": "go test ./..."},
    "lint": {"cmd": "golint ./..."},
    "build": {"cmd": "go build -o bin/app"}
}

pipelines = {
    "release": {
        "steps": ["lint", "test", "build"],
        "runners": 3
    }
}
```

Use across projects:
```bash
gryt pipeline new myapp --from catalog:go.release
```

---

## Installation

```bash
pip install gryt-ci
```

> Requires Python 3.9+, Git, and SQLite.

---

## Quick Start

```bash
# 1. Initialize
gryt init

# 2. Define release contract
cat > .gryt/generations/v1.0.0.yaml <<EOF
version: v1.0.0
changes:
  - type: add
    id: FEAT-001
    title: "User login"
pipeline_template: go.release
EOF

# 3. Run evolution
gryt evolution start v1.0.0 --change FEAT-001

# 4. Promote when ready
gryt generation promote v1.0.0
```

---

## Examples

- `examples/language_go.py` – Go CI catalog
- `examples/language_python.py` – Python testing
- `examples/release_gen.py` – Full Generation workflow

---

## Contributing

1. Fork & clone
2. `pip install -e .[dev]`
3. Open PR with `CONTRIBUTING.md` standards

---

**gryt-ci** — *Because speed without control is just noise.*

---

---

# **gryt-ci Roadmap** – *From Current State to Full Contract-Driven CI*

> **Current Version (v0.4.0)**: Promotion gates with 100% PASS validation.
> **Target Vision**: Full **Generation/Evolution** contract engine with **secure evolvability**.

---

## Current State (Implemented)

| Feature | Status |
|-------|--------|
| `gryt init`, `gryt run` | ✅ Done |
| Step & Pipeline execution | ✅ Done |
| Local Runtime (no Docker) | ✅ Done |
| Parallel Runners | ✅ Done |
| SQLite DB (`.gryt/gryt.db`) | ✅ Done |
| `gryt db query` | ✅ Done |
| Language catalogs (`examples/language_*.py`) | ✅ Done |
| Hooks (basic) | ✅ Done |
| Version tagging (manual) | ✅ Done |
| **v0.2.0**: Generation contracts | ✅ Done |
| `gryt generation new/list/show` | ✅ Done |
| `.gryt/generations/*.yaml` | ✅ Done |
| DB: `generations`, `generation_changes` | ✅ Done |
| EventBus + CloudSyncHandler | ✅ Done |
| `gryt config execution_mode` | ✅ Done |
| Cloud API: Generation endpoints | ✅ Done |
| **v0.3.0**: Evolution Engine | ✅ Done |
| `gryt evolution start --change ID` | ✅ Done |
| Auto RC tagging (`vX.Y.Z-rc.N`) | ✅ Done |
| DB: `evolutions` table | ✅ Done |
| `gryt evolution list` | ✅ Done |
| Git tag creation (annotated) | ✅ Done |
| Cloud API: Evolution endpoints | ✅ Done |
| **v0.4.0**: Promotion Gates | ✅ Done |
| `gryt generation promote` | ✅ Done |
| PromotionGate system (pluggable) | ✅ Done |
| 100% PASS validation | ✅ Done |
| AllChangesProvenGate | ✅ Done |
| NoFailedEvolutionsGate | ✅ Done |
| Auto Git tag on promote (vX.Y.Z) | ✅ Done |
| Cloud API: Promotion endpoint | ✅ Done |
| **v0.5.0**: Policy & Hooks++ | ✅ Done |
| Change-type hooks (`on_change_type_*`) | ✅ Done |
| Policy YAML schema & validation | ✅ Done |
| PolicyHook & ChangeTypeHook | ✅ Done |
| Policy enforcement in evolution start | ✅ Done |
| SlackDestination for notifications | ✅ Done |
| PrometheusDestination for metrics | ✅ Done |
| Alerts configuration (thresholds in schema) | ✅ Done |
| **v0.6.0**: Templates & UX | ✅ Done |
| Template system & registry | ✅ Done |
| Built-in templates (go, python, node, minimal) | ✅ Done |
| `gryt new` command with template support | ✅ Done |
| `gryt dashboard` TUI with Rich | ✅ Done |
| Real-time monitoring (generations, evolutions, stats) | ✅ Done |
| **v1.0.0**: Secure Evolvability Certified | ✅ Done |
| Audit trail export (JSON, CSV, HTML) | ✅ Done |
| Database snapshot & rollback system | ✅ Done |
| Hot-fix generation workflow | ✅ Done |
| NIST 800-161 compliance report generator | ✅ Done |
| `gryt audit` command suite | ✅ Done |
| `gryt compliance` report generation | ✅ Done |

---

## Roadmap: Complete! 🎉

All planned milestones have been implemented:
- ✅ v0.2.0 – Generation Contracts
- ✅ v0.3.0 – Evolution Engine
- ✅ v0.4.0 – Promotion Gates
- ✅ v0.5.0 – Policy & Hooks++
- ✅ v0.6.0 – Templates & UX
- ✅ v1.0.0 – Secure Evolvability Certified

**gryt-ci v1.0.0 is production-ready!**

---

## Gap Analysis

| Required for Vision | Current | Status |
|---------------------|---------|--------|
| **Generation contract** | ✅ CLI + YAML + DB | Done (v0.2.0) |
| **Evolution tagging** | ✅ Auto-increment RC | Done (v0.3.0) |
| **Change Types** | ✅ YAML + DB | Done (v0.2.0) |
| **Promotion gate** | ✅ Pluggable gates | Done (v0.4.0) |
| **Policy hooks** | ✅ YAML + Hooks + Alerts | Done (v0.5.0) |
| **Hot-fix path** | ✅ Fast-track workflow | Done (v1.0.0) |
| **Audit export** | ✅ JSON/CSV/HTML export | Done (v1.0.0) |

---

## Next Steps (Immediate)

1. ✅ **Generation contracts** – CLI, YAML, DB (v0.2.0)
2. ✅ **Evolution engine** – RC tagging, Git tags (v0.3.0)
3. ✅ **Promotion gates** – 100% PASS validation (v0.4.0)
4. ✅ **Policy system** – Change-type hooks, alerts (v0.5.0)
5. ✅ **TUI dashboard** – Interactive UI, templates (v0.6.0)
6. 📋 **NIST compliance** – Audit export (v1.0.0)

---

**We are building the CI system that AI-era teams need: fast, local, and unbreakable.**

Let’s ship the contract.
