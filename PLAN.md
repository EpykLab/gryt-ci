Milestone v0.2.0: Generation Contracts (MVP)

gryt.dev Changes

1. DB Schema
- Add tables: generations, generation_changes, sync_metadata
- Columns: sync_status, remote_id, last_synced_at (cloud sync tracking)
- Migration: gryt/migrations/003_generations.sql

2. YAML Schema
- Create .gryt/generations/ directory on init
- Schema: version, description, changes[] (type/id/title),
pipeline_template
- Validation: JSON Schema in gryt/schemas/generation.json

3. CLI Commands
- gryt generation new <version> - Create generation YAML + DB entry
- gryt generation list - Show all generations (status, changes count)
- gryt generation show <version> - Detail view
- gryt config set execution_mode <local|cloud|hybrid> - Set sync mode

4. Core Module
- gryt/generation.py - Generation class (load YAML, validate, save to DB)
- gryt/events.py - EventBus (pub/sub for lifecycle events)
- gryt/sync.py - CloudSyncHandler (listen to events, push to API if cloud
mode)

gryt-cloud Changes

1. API Schema (PostgreSQL)
- Add tables: generations, generation_changes
- Foreign key: generations.user_id → users.id

2. API Endpoints
- POST /api/v1/generations - Create generation
- GET /api/v1/generations - List user's generations
- GET /api/v1/generations/{id} - Get generation detail
- PATCH /api/v1/generations/{id} - Update status

3. Client Integration
- Extend gryt/cloud_client.py with create_generation(), sync_generation()

---
Milestone v0.3.0: Evolution Engine

gryt.dev Changes

1. DB Schema
- Add tables: evolutions, evolution_pipeline_runs
- Link: evolutions.pipeline_run_id → pipelines.pipeline_id

2. CLI Commands
- gryt evolution start <version> --change <id> - Create evolution, auto RC
 tag
- gryt evolution list <version> - Show all evolutions for generation
- Auto-increment: Parse existing RCs, generate vX.Y.Z-rc.N

3. Core Module
- gryt/evolution.py - Evolution class (create RC tag, link to pipeline
run)
- Extend Pipeline.run() to accept evolution_id context
- Hook: on_evolution_complete - emit event for sync

4. Git Integration
- Auto-tag: git tag vX.Y.Z-rc.N after successful evolution
- Tag metadata: Include change_id, evolution_id in tag message

gryt-cloud Changes

1. API Schema
- Add tables: evolutions, evolution_runs
- Link: evolutions.generation_id, evolution_runs.pipeline_id

2. API Endpoints
- POST /api/v1/evolutions - Create evolution
- GET /api/v1/evolutions?generation_id=<id> - List evolutions
- PATCH /api/v1/evolutions/{id} - Update status (running/pass/fail)

---
Milestone v0.4.0: Promotion Gates

gryt.dev Changes

1. Promotion Logic
- gryt generation promote <version> - Validate 100% PASS, create final tag
- Check: All changes in generation have ≥1 PASS evolution
- Fail: If any change unprovens or all evolutions failed

2. Gate System
- Abstract PromotionGate base class in gryt/gates.py
- Built-in gates:
  - AllChangesProvenGate - 100% PASS requirement
  - MinEvolutionsGate - Require N evolutions per change
- Config: .gryt/promotion_policy.yaml (list of gates + params)

3. Git Tagging
- Auto-tag: git tag vX.Y.Z on successful promote
- Tag message: Include generation summary, evolution count

4. DB Update
- Update generations.status = 'promoted', promoted_at timestamp

gryt-cloud Changes

1. API Endpoints
- POST /api/v1/generations/{id}/promote - Validate + mark promoted
- Return: Promotion report (gate results, tag created)

2. Webhook Integration
- Emit webhook on promotion: generation.promoted event
- Payload: version, tag, changes summary

---
Milestone v0.5.0: Policy & Hooks++

gryt.dev Changes

1. Change Type Policies
- Config: .gryt/policies.yaml
- Rules: require_e2e_for_add, require_security_scan_for_fix
- Hook trigger: on_change_type_<add|fix|refine|remove>

2. Extended Hooks
- PolicyHook - Validate policies before evolution start
- ChangeTypeHook - Custom logic per change type
- Integration: Check policies in evolution start command

3. Advanced Destinations
- SlackDestination - Post to Slack on evolution complete
- PrometheusDestination - Push metrics (evolution count, pass rate)
- Alerts: Configurable thresholds (e.g., "alert if pass rate < 80%")

gryt-cloud Changes

1. Policy Storage
- Add table: policies (user_id, policy_type, config_json)
- API: POST /api/v1/policies, GET /api/v1/policies

2. Destination Management
- Add table: destinations (type, credentials_encrypted)
- API: POST /api/v1/destinations, webhooks trigger destinations

---
Milestone v0.6.0: Templates & UX

gryt.dev Changes

1. Template System
- Extend gryt new --template <name> with generation templates
- Templates: go-release, python-lib, hotfix
- Include: Pre-filled generation YAML, pipeline, policies

2. TUI Dashboard
- gryt dashboard - Launch TUI (using textual library)
- Views:
  - Generations list (status, progress %)
  - Evolution timeline
  - Pipeline runs (live updates)
- Actions: Start evolution, promote, view logs

3. CLI UX Improvements
- Colorized output (success/fail/warning)
- Progress bars for long operations
- Interactive prompts for generation new (guided wizard)

gryt-cloud Changes

1. Web UI (Optional)
- React SPA for dashboard
- Views: Generations, evolutions, pipeline runs, webhooks
- Authentication: API key or OAuth

2. Template Sharing
- API: POST /api/v1/templates, GET /api/v1/templates
- Community templates: Shareable generation+pipeline combos

---
Milestone v1.0.0: Secure Evolvability Certified

gryt.dev Changes

1. Audit Trail
- gryt audit export --format <json|csv> - Export full DB history
- Include: All generations, evolutions, pipeline runs, changes
- Timestamps, user, machine, git commit per event

2. Rollback
- gryt rollback <version> - Revert to previous generation
- DB: Mark current generation as rolled_back, restore previous
- Git: Create rollback commit, tag vX.Y.Z-rollback

3. Hot-fix Workflow
- gryt hotfix create --base <version> - Generate patch version
- Auto-create generation: vX.Y.Z+1 with single Fix change
- Fast-track: Allow single evolution promote (skip multi-RC flow)

4. NIST 800-161 Compliance
- Documentation: Compliance guide mapping gryt features to NIST controls
- Report: gryt compliance report - Generate audit report
- Validation: Ensure immutability, traceability, secure evolution

gryt-cloud Changes

1. Audit API
- GET /api/v1/audit/trail?from=<date>&to=<date> - Query audit log
- Retention: Configurable (default 2 years)

2. Compliance Dashboard
- Web UI: NIST control checklist, audit timeline, rollback history

3. Enterprise Features
- RBAC: Roles (developer, approver, admin)
- Approval workflow: Require approver sign-off before promote
- SSO: SAML/OIDC integration

---
Cross-Cutting Concerns

Cloud Sync Strategy (All Milestones)

Behavior by Mode:
- local: No auto-sync, manual gryt cloud sync only
- cloud: Auto-sync on every generation/evolution change
- hybrid: Sync on promote only

Conflict Resolution:
- Detect: Compare last_synced_at + remote_id
- Strategy: Last-write-wins (configurable to fail-on-conflict)
- UI: Show conflict warnings, offer gryt cloud pull/push --force

Implementation:
- EventBus emits → CloudSyncHandler checks mode → API call if needed
- Background sync: Queue failed syncs, retry with exponential backoff
- Status: gryt cloud status shows sync state per generation

Testing Strategy

Per Milestone:
- Unit tests: Core classes (Generation, Evolution, Gates)
- Integration tests: CLI commands → DB state
- E2E tests: Full workflow (new → evolve → promote)

Cloud Integration:
- Mock API for local tests
- Test environment: gryt-cloud staging instance
- Contract tests: Ensure CLI ↔ API compatibility

Migration Path

For Existing Users:
- v0.2.0: Auto-migrate existing pipelines table (add generation_id column)
- Backward compat: Allow pipelines without generations (legacy mode)
- Migration guide: How to convert existing workflows to generations

---
Suggested Work Order

Phase 1 (v0.2.0): 2-3 weeks
1. DB schema + migrations (gryt.dev + gryt-cloud)
2. Generation YAML + CLI (local-only first)
3. EventBus + CloudSyncHandler
4. API endpoints + client integration
5. Manual testing with hybrid sync

Phase 2 (v0.3.0): 2-3 weeks
1. Evolution DB schema
2. Evolution CLI + RC tagging logic
3. Link evolution → pipeline run
4. Cloud API + sync
5. Test full evolution workflow

Phase 3 (v0.4.0): 1-2 weeks
1. PromotionGate base class
2. AllChangesProvenGate implementation
3. Promote CLI command
4. Cloud API + webhook
5. Test promotion flow

Phase 4 (v0.5.0): 2-3 weeks
1. Policy YAML schema
2. PolicyHook + ChangeTypeHook
3. Slack/Prometheus destinations
4. Cloud policy storage
5. Test policy enforcement

Phase 5 (v0.6.0): 3-4 weeks
1. Template system refactor
2. TUI dashboard (textual)
3. CLI UX improvements
4. Web UI (optional, parallel work)
5. Template sharing API

Phase 6 (v1.0.0): 3-4 weeks
1. Audit export CLI
2. Rollback implementation
3. Hot-fix workflow
4. NIST compliance docs
5. Enterprise features (RBAC, approval)

Total Estimated Timeline: 13-19 weeks (3-5 months)

---
Key Decision Points

1. EventBus: Use internal pub/sub vs external (Redis/NATS)? → Internal for
 v0.2.0, revisit for scale
2. Sync Conflicts: Last-write-wins vs fail-fast? → Configurable, default
last-write-wins
3. TUI Library: textual vs rich? → textual (more interactive)
4. Web UI: React vs HTMX? → React (existing skillset)
5. RBAC: Build custom vs use Casbin? → Custom (simpler for v1.0.0)
