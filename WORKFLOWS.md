# gryt-ci Workflows

Complete workflow examples for common scenarios.

---

## Workflow 1: Standard Feature Release

**Goal:** Release v1.5.0 with two new features and one bug fix.

### Step 1: Create Generation

```bash
gryt generation new v1.5.0
```

Edit `.gryt/generations/v1.5.0.yaml`:

```yaml
version: v1.5.0
description: "User authentication and notifications"
changes:
  - type: add
    id: FEAT-201
    title: "OAuth2 login support"
  - type: add
    id: FEAT-202
    title: "Email notification system"
  - type: fix
    id: BUG-88
    title: "Session timeout edge case"
pipeline_template: full-ci
```

### Step 2: First Evolution (OAuth2)

```bash
# Start evolution
gryt evolution start v1.5.0 --change FEAT-201

# Implement feature
# ... code changes ...

# Commit
git add .
git commit -m "feat: add OAuth2 login [FEAT-201]"

# Run pipeline
gryt run full-ci
```

**Pipeline runs:**
- Linting
- Unit tests
- Integration tests
- Security scan
- Build artifacts

**Result:** Creates `v1.5.0-rc.1` tag if all pass.

### Step 3: Second Evolution (Notifications)

```bash
gryt evolution start v1.5.0 --change FEAT-202

# Implement
# ... code changes ...

git add .
git commit -m "feat: email notification system [FEAT-202]"

gryt run full-ci
```

**Result:** Creates `v1.5.0-rc.2` tag.

### Step 4: Third Evolution (Bug Fix)

```bash
gryt evolution start v1.5.0 --change BUG-88

# Fix bug
# ... code changes ...

git add .
git commit -m "fix: handle session timeout edge case [BUG-88]"

gryt run full-ci
```

**Result:** Creates `v1.5.0-rc.3` tag.

### Step 5: Verify Progress

```bash
gryt evolution list v1.5.0
```

Output:
```
Generation: v1.5.0 (draft)
Description: User authentication and notifications

Evolutions:
  Tag           Change     Status  Timestamp
  v1.5.0-rc.1   FEAT-201   pass    2024-01-20 09:15
  v1.5.0-rc.2   FEAT-202   pass    2024-01-20 11:30
  v1.5.0-rc.3   BUG-88     pass    2024-01-20 14:45

Changes:
  ID        Title                       Status
  FEAT-201  OAuth2 login support        proven
  FEAT-202  Email notification system   proven
  BUG-88    Session timeout edge case   proven

Ready for promotion: YES
```

### Step 6: Promote

```bash
# Create snapshot first
gryt audit snapshot --label "pre-v1.5.0-promotion"

# Promote
gryt generation promote v1.5.0
```

**Output:**
```
Running promotion gates...
  AllChangesProvenGate: PASS
  NoFailedEvolutionsGate: PASS
  MinEvolutionsGate: PASS

Creating final tag v1.5.0...
Updating generation status to promoted...

Generation v1.5.0 promoted successfully!
```

### Step 7: Deploy

```bash
# Tag is now available
git push origin v1.5.0

# Trigger deployment (external CD system)
# Your CD watches for v* tags and deploys
```

**Timeline:**
- Day 1: Create generation, start FEAT-201 evolution
- Day 2: Complete FEAT-201, start FEAT-202
- Day 3: Complete FEAT-202, start BUG-88
- Day 4: Complete BUG-88, promote

---

## Workflow 2: Emergency Hot-fix

**Scenario:** Production issue in v2.3.0 needs immediate fix.

### Step 1: Create Hot-fix

```bash
gryt audit hotfix v2.3.0 \
  --issue CRIT-500 \
  --title "Fix database connection pool leak"
```

**Output:**
```
Creating hot-fix for v2.3.0...
Hot-fix generation created: v2.3.1
  Generation ID: gen-abc123
  Issue: CRIT-500

Next steps:
  1. gryt evolution start v2.3.1 --change CRIT-500
  2. Run your pipeline to test the fix
  3. gryt audit hotfix-promote v2.3.1
```

### Step 2: Implement Fix

```bash
# Start evolution
gryt evolution start v2.3.1 --change CRIT-500

# Fix the leak
# ... code changes ...

git add .
git commit -m "fix: prevent connection pool leak [CRIT-500]"
```

### Step 3: Test

```bash
gryt run full-ci
```

**Pipeline creates:** `v2.3.1-rc.1` tag

### Step 4: Fast-track Promote

```bash
gryt audit hotfix-promote v2.3.1
```

**Output:**
```
Promoting hot-fix: v2.3.1

Running HotfixGate (minimal validation)...
  At least one passing evolution: PASS
  No pending evolutions: PASS

Hot-fix promoted successfully!
Tag created: v2.3.1
```

### Step 5: Deploy Immediately

```bash
git push origin v2.3.1

# Emergency deploy via CD
kubectl set image deployment/app app=myapp:v2.3.1
```

**Timeline:**
- Hour 0: Issue detected
- Hour 1: Hot-fix created and implemented
- Hour 2: Pipeline passes, promoted
- Hour 2.5: Deployed to production

**Key Differences from Standard Release:**
- Automatic version calculation (v2.3.0 -> v2.3.1)
- Minimal gates (only one passing evolution required)
- No waiting for all changes
- Fast-track promotion

---

## Workflow 3: Multi-Team Parallel Development

**Scenario:** Three teams working on v3.0.0 simultaneously.

### Step 1: Create Generation (Release Manager)

```yaml
# .gryt/generations/v3.0.0.yaml
version: v3.0.0
description: "Q1 Major Release"
changes:
  # Team A: Payments
  - type: add
    id: TEAM-A-1
    title: "Subscription billing"
  - type: refine
    id: TEAM-A-2
    title: "Checkout flow UX"

  # Team B: Analytics
  - type: add
    id: TEAM-B-1
    title: "Advanced reporting dashboard"
  - type: add
    id: TEAM-B-2
    title: "Export to CSV/Excel"

  # Team C: Infrastructure
  - type: refine
    id: TEAM-C-1
    title: "Database query optimization"
  - type: fix
    id: TEAM-C-2
    title: "Memory leak in cache layer"

pipeline_template: full-ci
```

### Step 2: Teams Work in Parallel

**Team A (Week 1-2):**
```bash
# Branch for TEAM-A-1
git checkout -b feature/subscription-billing

# Implement subscription billing
# ...

# Start evolution
gryt evolution start v3.0.0 --change TEAM-A-1
gryt run full-ci

# Merge to main
git checkout main
git merge feature/subscription-billing
git push
```

**Team B (Week 1-2):**
```bash
# Independent work on reporting
git checkout -b feature/reporting-dashboard

gryt evolution start v3.0.0 --change TEAM-B-1
gryt run full-ci

git checkout main
git merge feature/reporting-dashboard
git push
```

**Team C (Week 1):**
```bash
# Quick optimization
git checkout -b perf/db-optimization

gryt evolution start v3.0.0 --change TEAM-C-1
gryt run full-ci

git checkout main
git merge perf/db-optimization
git push
```

### Step 3: Check Progress (Release Manager)

```bash
gryt evolution list v3.0.0
```

**Week 2 Status:**
```
Generation: v3.0.0 (draft)

Evolutions:
  v3.0.0-rc.1   TEAM-A-1   pass    Team A
  v3.0.0-rc.2   TEAM-B-1   pass    Team B
  v3.0.0-rc.3   TEAM-C-1   pass    Team C
  v3.0.0-rc.4   TEAM-A-2   pass    Team A
  v3.0.0-rc.5   TEAM-B-2   pass    Team B
  v3.0.0-rc.6   TEAM-C-2   pass    Team C

Changes:
  TEAM-A-1  Subscription billing          proven
  TEAM-A-2  Checkout flow UX              proven
  TEAM-B-1  Advanced reporting dashboard  proven
  TEAM-B-2  Export to CSV/Excel           proven
  TEAM-C-1  Database query optimization   proven
  TEAM-C-2  Memory leak in cache layer    proven

Ready for promotion: YES
```

### Step 4: Promote

```bash
gryt generation promote v3.0.0
```

### Benefits

- Teams work independently without coordination
- Each team proves their changes work
- Release manager sees complete progress
- All changes validated before promotion
- Clear audit trail of who did what when

---

## Workflow 4: Continuous Deployment

**Goal:** Deploy every commit to staging, promote proven changes to production weekly.

### Setup

```yaml
# .gryt/generations/v4.1.0.yaml (this week's release)
version: v4.1.0
description: "Week 6 release"
changes:
  - type: add
    id: FEAT-301
    title: "Dark mode support"
  - type: refine
    id: PERF-45
    title: "Reduce API latency"
pipeline_template: cd-pipeline
```

### Daily Developer Flow

**Monday:**
```bash
# Start feature
git checkout -b feature/dark-mode
gryt evolution start v4.1.0 --change FEAT-301

# Implement
# ... code ...

# Commit and push
git add .
git commit -m "feat: add dark mode toggle [FEAT-301]"
git push origin feature/dark-mode
```

**CI runs automatically:**
```bash
# .github/workflows/ci.yml triggers:
gryt run cd-pipeline
```

**Pipeline:**
1. Test
2. Build
3. Deploy to staging
4. Run E2E tests
5. Create RC tag if pass

**Tuesday:**
```bash
# Staging looks good, merge
git checkout main
git merge feature/dark-mode
git push

# Another feature
git checkout -b perf/api-latency
gryt evolution start v4.1.0 --change PERF-45
# ... implement ...
git push
```

### Friday (Promotion Day)

```bash
# Check week's progress
gryt evolution list v4.1.0
```

**Output:**
```
Evolutions:
  v4.1.0-rc.1   FEAT-301   pass    Mon 10:30
  v4.1.0-rc.2   PERF-45    pass    Tue 14:15

All changes proven. Ready for production.
```

```bash
# Promote to production
gryt generation promote v4.1.0

# CD pipeline deploys v4.1.0 to production
```

### Next Week

```bash
# Create next week's generation
gryt generation new v4.2.0

# Continue daily deployments to staging
# Promote v4.2.0 next Friday
```

**Cadence:**
- Daily: Commits go to staging via evolutions
- Weekly: Promote to production
- Always: Full audit trail

---

## Workflow 5: Policy-Enforced Quality

**Goal:** Enforce testing and security requirements automatically.

### Step 1: Define Policies

```yaml
# .gryt/policy.yaml
policies:
  - name: "e2e-tests-for-features"
    applies_to: [add]
    required_steps:
      - e2e-tests
    description: "All new features need E2E tests"

  - name: "security-scan-always"
    applies_to: [add, fix, refine, remove]
    required_steps:
      - security-scan
      - dependency-audit
    description: "Security scan required for all changes"

  - name: "performance-benchmarks"
    applies_to: [refine]
    required_steps:
      - benchmark
    description: "Performance changes need benchmarks"

  - name: "minimum-evolutions"
    min_evolutions: 2
    description: "At least 2 evolutions before promotion"
```

### Step 2: Create Generation

```yaml
# .gryt/generations/v5.0.0.yaml
version: v5.0.0
changes:
  - type: add
    id: FEAT-400
    title: "Real-time notifications"
  - type: refine
    id: PERF-100
    title: "Optimize database queries"
```

### Step 3: Try to Start Evolution (Without Required Steps)

```bash
gryt evolution start v5.0.0 --change FEAT-400
```

**Output:**
```
ERROR: Policy violation

Policy: e2e-tests-for-features
  Applies to: add
  Violation: Pipeline 'release-pipeline' missing required step: e2e-tests

Policy: security-scan-always
  Applies to: add
  Violation: Pipeline 'release-pipeline' missing required step: security-scan

Evolution not started.
```

### Step 4: Fix Pipeline

Add required steps to `.gryt/pipelines/release-pipeline.yaml`:

```yaml
name: release-pipeline
steps:
  - name: test
    command: "go test ./..."
  - name: e2e-tests
    command: "npm run test:e2e"
  - name: security-scan
    command: "trivy scan ."
  - name: dependency-audit
    command: "npm audit"
  - name: build
    command: "go build"
```

### Step 5: Try Again

```bash
gryt evolution start v5.0.0 --change FEAT-400
```

**Output:**
```
Validating policies...
  e2e-tests-for-features: PASS
  security-scan-always: PASS

Evolution started: v5.0.0-rc.1
Change: FEAT-400
Pipeline: release-pipeline
```

### Step 6: Performance Change Validation

```bash
gryt evolution start v5.0.0 --change PERF-100
```

**Checks:**
- Requires `benchmark` step (policy: performance-benchmarks)
- Requires `security-scan` (policy: security-scan-always)

### Benefits

- Developers cannot bypass quality gates
- Policies enforced before pipeline runs (fail fast)
- Clear error messages guide developers
- Consistent standards across teams
- Audit trail shows policy compliance

---

## Workflow 6: Rollback After Bad Promotion

**Scenario:** v6.0.0 promoted but has critical issue in production.

### Step 1: Detect Issue

```bash
# Production monitoring alerts
# Issue: v6.0.0 has memory leak
```

### Step 2: Check Snapshots

```bash
gryt audit list-snapshots
```

**Output:**
```
Snapshots:

ID                                       Label                Created              Size
snapshot_20240120_143000                 pre-v6.0.0-promotion 2024-01-20 14:30    15.2 MB
snapshot_20240119_120000                 daily-backup         2024-01-19 12:00    14.8 MB
snapshot_20240118_120000                 daily-backup         2024-01-18 12:00    14.5 MB
```

### Step 3: Rollback Database

```bash
gryt audit rollback snapshot_20240120_143000
```

**Output:**
```
Creating backup of current state...
  Backup ID: snapshot_20240120_153000

Rolling back to: snapshot_20240120_143000

This will replace your current database. Continue? [y/N]: y

Rollback complete.
```

**Result:**
- Generation v6.0.0 status reverted from "promoted" to "draft"
- Can fix issue and re-promote

### Step 4: Fix and Re-promote

```bash
# Create hot-fix
gryt audit hotfix v5.9.0 \
  --issue CRIT-600 \
  --title "Fix memory leak"

gryt evolution start v5.9.1 --change CRIT-600

# Fix issue
# ... code changes ...

gryt run full-ci
gryt audit hotfix-promote v5.9.1

# Deploy v5.9.1
git push origin v5.9.1
```

### Step 5: Return to v6.0.0 Later

```bash
# Fix the issue in v6.0.0 scope
gryt evolution start v6.0.0 --change FIX-LEAK
gryt run full-ci

# Re-promote
gryt generation promote v6.0.0
```

---

## Workflow 7: Compliance Audit

**Goal:** Generate quarterly compliance report for audit.

### Step 1: Export Audit Trail

```bash
# Export complete audit trail
gryt audit export \
  --output "audit-q1-2024.json" \
  --format json

# Also create human-readable HTML
gryt audit export \
  --output "audit-q1-2024.html" \
  --format html
```

### Step 2: Generate Compliance Report

```bash
gryt compliance --output "compliance-q1-2024.html"
```

**Report includes:**
- Total generations created
- Promotion success rate
- Failed evolutions analysis
- Audit event count
- Policy enforcement evidence

### Step 3: Query Specific Metrics

```bash
# How many changes in Q1?
gryt db query "
  SELECT COUNT(*) as total_changes
  FROM generation_changes
  WHERE created_at >= '2024-01-01'
    AND created_at < '2024-04-01'
"

# Pass rate
gryt db query "
  SELECT
    COUNT(*) as total,
    SUM(CASE WHEN status = 'pass' THEN 1 ELSE 0 END) as passed,
    ROUND(SUM(CASE WHEN status = 'pass' THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 2) as pass_rate
  FROM evolutions
  WHERE created_at >= '2024-01-01'
"

# Promoted generations
gryt db query "
  SELECT version, promoted_at
  FROM generations
  WHERE status = 'promoted'
    AND promoted_at >= '2024-01-01'
  ORDER BY promoted_at DESC
"
```

### Step 4: Snapshot for Archive

```bash
# Create Q1 archive snapshot
gryt audit snapshot --label "q1-2024-archive"

# Backup database file
cp .gryt/gryt.db backups/gryt-q1-2024.db
```

### Deliverables

1. `audit-q1-2024.json` - Machine-readable audit data
2. `audit-q1-2024.html` - Human-readable audit report
3. `compliance-q1-2024.html` - NIST 800-161 compliance report
4. `gryt-q1-2024.db` - Complete database snapshot
5. SQL query results for specific metrics

---

## Workflow 8: Distributed Team Collaboration with Sync

### Scenario

Team distributed across multiple locations working on same codebase. Need to coordinate releases, share generation contracts, avoid version conflicts.

### Execution Mode

```bash
gryt sync config --mode hybrid
```

Hybrid mode: manual sync during development, auto-sync on promotion.

### Collaboration Model: Shared Generation

**Developer A (San Francisco) - Creates Contract**

```bash
# Create generation contract
gryt generation new v5.0.0

# Edit contract
cat > .gryt/generations/v5.0.0.yaml <<EOF
version: v5.0.0
description: "Major refactor - authentication system"
changes:
  - change_id: AUTH-001
    type: add
    title: OAuth2 integration
  - change_id: AUTH-002
    type: refine
    title: Session management refactor
  - change_id: AUTH-003
    type: remove
    title: Deprecated legacy auth endpoints
EOF

# Push contract to cloud
gryt sync push --version v5.0.0
```

Output:
```
Push complete
  Created: 1
  Updated: 0
```

**Developer B (Tokyo) - Pulls Contract**

```bash
# Check cloud state
gryt sync status

# Pull latest changes
gryt sync pull
```

Output:
```
Pull complete
  New generations: 1
  Updated generations: 0
  Conflicts: 0
```

**Developer A - Works on OAuth2**

```bash
# Start evolution for AUTH-001
gryt evolution start v5.0.0 --change AUTH-001

# Run pipeline
gryt run oauth-integration

# Evolution passes
gryt evolution list v5.0.0
```

Output:
```
v5.0.0-rc.1  AUTH-001  pass
```

**Developer B - Works on Session Management**

```bash
# Start evolution for AUTH-002
gryt evolution start v5.0.0 --change AUTH-002

# Run pipeline
gryt run session-refactor

# Evolution passes
gryt evolution list v5.0.0
```

Output:
```
v5.0.0-rc.1  AUTH-001  pass
v5.0.0-rc.2  AUTH-002  pass
```

**Developer A - Removes Legacy Endpoints**

```bash
# Pull latest evolutions
gryt sync pull

# See B's work
gryt evolution list v5.0.0
# v5.0.0-rc.1  AUTH-001  pass
# v5.0.0-rc.2  AUTH-002  pass

# Start evolution for AUTH-003
gryt evolution start v5.0.0 --change AUTH-003

# Run pipeline
gryt run remove-legacy-auth

# All changes proven
gryt generation show v5.0.0
```

Output:
```
Generation: v5.0.0
Status: draft
Changes:
  ✓ AUTH-001 (proven by v5.0.0-rc.1)
  ✓ AUTH-002 (proven by v5.0.0-rc.2)
  ✓ AUTH-003 (proven by v5.0.0-rc.3)
```

**Developer A - Promotes**

```bash
# Promote to production
gryt generation promote v5.0.0
```

Output:
```
Promotion successful
  Version: v5.0.0
  All changes proven: 3/3
  Synced to cloud: yes
```

Auto-synced to cloud in hybrid mode.

**Developer B - Sees Promotion**

```bash
# Pull latest state
gryt sync pull

# Verify promotion
gryt generation show v5.0.0
```

Output:
```
Generation: v5.0.0
Status: promoted
Promoted at: 2025-10-29T10:15:00Z
```

### Conflict Scenario: Same Version

**Developer A**

```bash
# Creates v6.0.0
gryt generation new v6.0.0
```

**Developer B (doesn't pull first)**

```bash
# Also creates v6.0.0
gryt generation new v6.0.0
```

Both work independently.

**Developer A promotes first**

```bash
gryt generation promote v6.0.0
# Auto-synced to cloud
```

**Developer B tries to push**

```bash
gryt sync push --version v6.0.0
```

Output:
```
Push complete
  Created: 0
  Updated: 0
  Errors: 1
    • v6.0.0: Version v6.0.0 already exists in cloud
      Resolution: Use different version or pull to sync
```

**Developer B resolves conflict**

```bash
# Pull A's version
gryt sync pull

# Check conflict
gryt generation list
# v6.0.0 (promoted, from cloud)
# v6.0.0 (draft, local)

# Rename local version
gryt generation rename v6.0.0 v6.1.0

# Continue work on v6.1.0
gryt evolution start v6.1.0 --change FEAT-100
```

### Best Practices for Distributed Teams

**1. Pull-before-create workflow:**

```bash
# Always check cloud state first
gryt sync pull

# Then create new versions
gryt generation new v7.0.0
```

**2. Use version ranges per team:**

```bash
# Team A: v1.x.x
gryt generation new v1.0.0
gryt generation new v1.1.0

# Team B: v2.x.x
gryt generation new v2.0.0
gryt generation new v2.1.0
```

**3. Sync before promotion:**

```bash
# Check cloud state
gryt sync status --version v8.0.0

# Pull any updates
gryt sync pull

# Then promote
gryt generation promote v8.0.0
```

**4. Regular sync checks:**

```bash
# Daily morning routine
gryt sync pull
gryt sync status

# See what team has been working on
gryt generation list
```

### Sync Status Monitoring

```bash
# Check overall sync health
gryt sync status
```

Output:
```
Sync Status Summary
  Total generations: 15
  Synced: 12
  Pending: 2
  Conflicts: 1

Generations:
Version    Status       Remote ID      Last Synced
v1.0.0     synced       gen-abc123     2025-10-28
v2.0.0     synced       gen-def456     2025-10-29
v3.0.0     pending      —              —
v4.0.0     conflict     —              —
```

### Outcome

Distributed team successfully collaborates on v5.0.0 without conflicts. Clear contract (generation) shared via cloud. Individual developers work on different changes independently. Sync system prevents version conflicts. Full audit trail maintained locally and in cloud.

---

## Summary

**Standard Release:** Generation -> Evolutions -> Promote
- Best for planned releases with multiple changes
- Full gate validation
- Clear audit trail

**Hot-fix:** Fast-track for emergencies
- Automatic version calculation
- Minimal gates
- Quick turnaround

**Parallel Teams:** Independent evolution tracking
- No coordination needed
- Clear progress visibility
- Individual team accountability

**Continuous Deployment:** Daily staging, weekly production
- Rapid iteration
- Proven changes only
- Regular cadence

**Policy-Enforced:** Automated quality gates
- Prevent policy violations
- Consistent standards
- Clear requirements

**Rollback:** Database time travel
- Safe experimentation
- Quick recovery
- Point-in-time restore

**Compliance:** Audit and reporting
- Complete change history
- NIST 800-161 compliance
- Quarterly reporting

**Distributed Collaboration:** Cloud sync for teams
- Bidirectional sync (pull/push)
- Version conflict detection
- Shared generation contracts
- Independent evolution work
- Pull-before-create best practice
