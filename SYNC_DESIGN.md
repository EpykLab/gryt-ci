# Distributed Sync Design

How to handle multi-developer scenarios without conflicts or data loss.

---

## The Problem

Current sync is incomplete and would fail with distributed teams:

**Scenario:**
```
Developer A                    Developer B
├─ gryt generation new v1.0.0  ├─ gryt generation new v1.0.0
├─ add FEAT-001                ├─ add FEAT-002
├─ gryt evolution start        ├─ gryt evolution start
├─ gryt promote v1.0.0         ├─ gryt promote v1.0.0
│  (syncs to cloud)            │  (syncs to cloud)
│                              │
└─ ??? conflict ???            └─ ??? conflict ???
```

**Issues:**
1. Both have same version but different changes
2. No conflict detection
3. No merge strategy
4. Last write wins (data loss)
5. No way for A to see B's changes

---

## Solution: Git-like Sync Model

### Core Principles

**1. Cloud is source of truth for promoted releases**
- Once promoted to cloud, immutable
- Local can't override cloud promoted state
- Promotes require cloud to be up-to-date

**2. Generations are collaborative, Evolutions are local**
- Generations: Shared contract (synced)
- Evolutions: Individual proof (local-only until completed)
- Changes: Defined in generation, proven by evolutions

**3. Pull before push**
- `gryt sync pull` fetches cloud state
- `gryt sync push` fails if behind
- `gryt promote` requires up-to-date state

**4. Use generation version as lock**
- Version v1.0.0 can only be promoted once
- First to promote wins
- Others must create new version (v1.0.1, v1.1.0, etc.)

---

## Recommended Workflow

### Single-Developer Workflow (Local Mode)

```bash
# No sync, everything local
gryt config execution_mode local

gryt generation new v1.0.0
gryt evolution start v1.0.0 --change FEAT-001
gryt run pipeline
gryt promote v1.0.0
```

No conflicts possible. Full autonomy.

### Multi-Developer Workflow (Hybrid Mode)

**Developer A:**
```bash
gryt config execution_mode hybrid

# 1. Pull latest from cloud
gryt sync pull

# 2. Check what versions exist
gryt sync status
# Output: Cloud has: v0.9.0 (promoted), v1.0.0 (draft)

# 3. Create new version (not v1.0.0, already exists)
gryt generation new v1.1.0

# 4. Add changes
vim .gryt/generations/v1.1.0.yaml
# Add FEAT-001

# 5. Prove changes locally
gryt evolution start v1.1.0 --change FEAT-001
gryt run pipeline

# 6. Promote (syncs to cloud)
gryt promote v1.1.0
# Success: v1.1.0 promoted to cloud
```

**Developer B (concurrent):**
```bash
# 1. Pull latest
gryt sync pull

# 2. Check status
gryt sync status
# Output: Cloud has: v0.9.0, v1.0.0, v1.1.0 (just promoted by A)

# 3. Create next version
gryt generation new v1.2.0

# 4. Add different changes
vim .gryt/generations/v1.2.0.yaml
# Add FEAT-002

# 5. Prove and promote
gryt evolution start v1.2.0 --change FEAT-002
gryt run pipeline
gryt promote v1.2.0
```

**Result:** No conflicts. Linear version history.

### Coordinated Release (Multiple Changes, One Version)

When team wants multiple developers contributing to same release:

**Team lead creates generation:**
```bash
# Lead creates generation contract
gryt generation new v2.0.0

vim .gryt/generations/v2.0.0.yaml
```

```yaml
version: v2.0.0
description: "Q1 Major Release"
changes:
  - type: add
    id: FEAT-101
    title: "OAuth2 login"
    assignee: developer-a
  - type: add
    id: FEAT-102
    title: "Email notifications"
    assignee: developer-b
  - type: fix
    id: BUG-50
    title: "Session timeout"
    assignee: developer-c
```

```bash
# Push to cloud as draft
gryt sync push
# Creates v2.0.0 in cloud (status: draft)
```

**Developer A:**
```bash
# Pull the generation contract
gryt sync pull

# Verify you have v2.0.0
cat .gryt/generations/v2.0.0.yaml

# Prove your assigned change
gryt evolution start v2.0.0 --change FEAT-101
gryt run pipeline

# Evolution syncs to cloud automatically (cloud mode)
# Or manually: gryt sync push-evolutions
```

**Developer B (parallel):**
```bash
gryt sync pull

# Prove your change
gryt evolution start v2.0.0 --change FEAT-102
gryt run pipeline
```

**Developer C (parallel):**
```bash
gryt sync pull

gryt evolution start v2.0.0 --change BUG-50
gryt run pipeline
```

**Team lead checks progress:**
```bash
# Query cloud for v2.0.0 status
gryt sync status v2.0.0

# Output:
# Generation: v2.0.0 (draft)
# Changes:
#   FEAT-101  OAuth2 login          proven (dev-a, rc.1)
#   FEAT-102  Email notifications   proven (dev-b, rc.1)
#   BUG-50    Session timeout       proven (dev-c, rc.1)
# Ready for promotion: YES

# Promote
gryt promote v2.0.0
# Syncs promoted status to cloud
# All developers get notified
```

**Other developers pull:**
```bash
gryt sync pull
# Fetches v2.0.0 promoted status
# Local DB updated
```

---

## Conflict Resolution Rules

### Rule 1: Version-based Locking

**Generations are uniquely identified by version.**

```bash
# Developer A
gryt generation new v1.0.0
gryt promote v1.0.0
# Syncs to cloud, v1.0.0 now promoted

# Developer B (tries same version)
gryt generation new v1.0.0
gryt promote v1.0.0
# ERROR: Version v1.0.0 already promoted in cloud
# Please use a different version or pull latest
```

**Resolution:** Developer B must use v1.0.1 or v1.1.0.

### Rule 2: Promoted is Immutable

Once promoted in cloud, cannot be modified.

```bash
# After v1.0.0 promoted
gryt generation new v1.0.0  # Error: version exists

# Must create new version
gryt generation new v1.0.1  # OK
```

### Rule 3: Draft Can Be Modified

Draft generations (not promoted) can receive updates.

```bash
# Lead creates draft
gryt generation new v2.0.0
gryt sync push  # Pushes to cloud as draft

# Developer adds evolution
gryt evolution start v2.0.0 --change FEAT-001
# Evolution syncs to cloud

# Lead can still modify generation
vim .gryt/generations/v2.0.0.yaml
# Add more changes
gryt sync push  # Updates cloud draft

# Developer pulls updates
gryt sync pull  # Gets latest v2.0.0 with new changes
```

### Rule 4: Evolution Ownership

Evolutions are owned by the developer who created them.

```bash
# Developer A
gryt evolution start v2.0.0 --change FEAT-001
# Creates rc.1 (owned by dev-a)

# Developer B
gryt evolution start v2.0.0 --change FEAT-001
# Creates rc.2 (owned by dev-b)

# Both valid, proves same change independently
# Promotion gate requires at least one passing
```

---

## Sync Commands

### gryt sync pull

Fetch cloud state and merge into local DB.

```bash
gryt sync pull
```

**Behavior:**
- Fetches all generations from cloud
- For each cloud generation:
  - If not in local DB: Insert
  - If in local DB with same remote_id: Update local with cloud state
  - If in local DB without remote_id: Leave local alone (not synced yet)
- Fetches evolutions associated with synced generations
- Updates sync_status and timestamps

**Safe:** Never overwrites local-only work.

### gryt sync push

Push local changes to cloud.

```bash
gryt sync push
```

**Behavior:**
- For each local generation with sync_status != synced:
  - If remote_id exists: Update cloud
  - If no remote_id: Create in cloud, save remote_id
- Handles conflicts (see rules above)
- Updates sync_status to 'synced'

**Fails if:** Version conflict detected.

### gryt sync status

Show sync state.

```bash
gryt sync status
```

**Output:**
```
Local generations:
  v1.0.0  promoted  synced     (cloud: promoted)
  v1.1.0  draft     pending    (cloud: none)

Cloud generations not in local:
  v0.9.0  promoted

Sync status: Behind (1 cloud generation not pulled)
```

### gryt sync push-evolutions

Push evolutions for a generation.

```bash
gryt sync push-evolutions v2.0.0
```

**Behavior:**
- Push all evolutions for v2.0.0 to cloud
- Useful in hybrid mode for collaboration
- Automatic in cloud mode

---

## Data Model Changes

### Add Sync Fields to generations Table

```sql
ALTER TABLE generations ADD COLUMN remote_id TEXT;
ALTER TABLE generations ADD COLUMN sync_status TEXT DEFAULT 'not_synced';
  -- Values: not_synced, syncing, synced, conflict, failed
ALTER TABLE generations ADD COLUMN last_synced_at DATETIME;
ALTER TABLE generations ADD COLUMN sync_error TEXT;
```

### Add Sync Fields to evolutions Table

```sql
ALTER TABLE evolutions ADD COLUMN remote_id TEXT;
ALTER TABLE evolutions ADD COLUMN sync_status TEXT DEFAULT 'not_synced';
ALTER TABLE evolutions ADD COLUMN last_synced_at DATETIME;
ALTER TABLE evolutions ADD COLUMN owner TEXT;  -- Developer who created it
```

### Add Sync Metadata Table

```sql
CREATE TABLE sync_metadata (
  key TEXT PRIMARY KEY,
  value TEXT,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Store:
-- - last_pull_timestamp
-- - cloud_url
-- - sync_mode (local/cloud/hybrid)
```

---

## Implementation: CloudSync Service

### sync.py (Enhanced)

```python
class CloudSync:
    """Bidirectional sync with conflict detection"""

    def __init__(self, data: SqliteData, client: GrytCloudClient):
        self.data = data
        self.client = client

    def pull(self) -> dict:
        """Pull cloud state to local"""
        result = {
            "new": 0,
            "updated": 0,
            "conflicts": []
        }

        # Fetch all cloud generations
        cloud_gens = self.client.list_generations()

        for cloud_gen in cloud_gens["generations"]:
            remote_id = cloud_gen["id"]
            version = cloud_gen["version"]

            # Check if exists locally
            local = self.data.query(
                "SELECT * FROM generations WHERE remote_id = ?",
                (remote_id,)
            )

            if not local:
                # Check if same version exists locally without remote_id
                local_by_version = self.data.query(
                    "SELECT * FROM generations WHERE version = ?",
                    (version,)
                )

                if local_by_version:
                    # Conflict: same version, different source
                    result["conflicts"].append({
                        "version": version,
                        "reason": "Local and cloud have same version",
                        "resolution": "Rename local version or delete"
                    })
                else:
                    # New from cloud, insert
                    self._insert_from_cloud(cloud_gen)
                    result["new"] += 1
            else:
                # Update local with cloud state
                self._update_from_cloud(local[0], cloud_gen)
                result["updated"] += 1

        # Update last pull timestamp
        self.data.insert("sync_metadata", {
            "key": "last_pull_timestamp",
            "value": datetime.now().isoformat()
        })

        return result

    def push(self, version: Optional[str] = None) -> dict:
        """Push local changes to cloud"""
        result = {
            "created": 0,
            "updated": 0,
            "errors": []
        }

        # Get generations to sync
        if version:
            gens = [Generation.from_db(self.data, version)]
        else:
            # All not synced or modified
            gens = self._get_pending_generations()

        for gen in gens:
            try:
                if gen.remote_id:
                    # Update existing
                    self.client.update_generation(
                        gen.remote_id,
                        gen.to_dict()
                    )
                    result["updated"] += 1
                else:
                    # Check if version exists in cloud
                    try:
                        cloud_gen = self.client.get_generation_by_version(
                            gen.version
                        )
                        # Conflict: version exists
                        result["errors"].append({
                            "version": gen.version,
                            "error": "Version already exists in cloud",
                            "resolution": "Use different version"
                        })
                        continue
                    except:
                        pass  # Version doesn't exist, proceed

                    # Create new
                    cloud_result = self.client.create_generation(
                        gen.to_dict()
                    )

                    # Save remote_id to local
                    self.data.update(
                        "generations",
                        {
                            "remote_id": cloud_result["id"],
                            "sync_status": "synced",
                            "last_synced_at": datetime.now()
                        },
                        "generation_id = ?",
                        (gen.generation_id,)
                    )
                    result["created"] += 1

            except Exception as e:
                result["errors"].append({
                    "version": gen.version,
                    "error": str(e)
                })

                # Update sync status to failed
                self.data.update(
                    "generations",
                    {
                        "sync_status": "failed",
                        "sync_error": str(e)
                    },
                    "generation_id = ?",
                    (gen.generation_id,)
                )

        return result

    def status(self, version: Optional[str] = None) -> dict:
        """Get sync status"""
        if version:
            return self._status_for_version(version)
        else:
            return self._status_all()

    def _status_all(self) -> dict:
        """Overall sync status"""
        local_gens = Generation.list_all(self.data)
        cloud_gens = self.client.list_generations()

        cloud_versions = {g["version"] for g in cloud_gens["generations"]}
        local_versions = {g.version for g in local_gens}

        return {
            "local_only": local_versions - cloud_versions,
            "cloud_only": cloud_versions - local_versions,
            "synced": local_versions & cloud_versions,
            "pending": [
                g.version for g in local_gens
                if g.sync_status != "synced"
            ],
            "conflicts": self._detect_conflicts()
        }

    def _detect_conflicts(self) -> list:
        """Detect sync conflicts"""
        conflicts = []

        # Check for same version, different content
        local_gens = Generation.list_all(self.data)

        for gen in local_gens:
            if not gen.remote_id and gen.sync_status == "not_synced":
                # Check if version exists in cloud
                try:
                    cloud_gen = self.client.get_generation_by_version(
                        gen.version
                    )
                    conflicts.append({
                        "version": gen.version,
                        "type": "version_exists",
                        "message": f"Version {gen.version} exists in cloud"
                    })
                except:
                    pass

        return conflicts
```

---

## Sync CLI Commands

### sync_cli.py

```python
import typer
from gryt import SqliteData
from gryt.cloud_client import GrytCloudClient
from gryt.sync import CloudSync
from gryt.config import Config

sync_app = typer.Typer(name="sync", help="Sync with Gryt Cloud")

def _get_sync() -> CloudSync:
    config = Config()
    if not config.has_credentials():
        typer.echo("Not logged in. Run 'gryt cloud login'", err=True)
        raise typer.Exit(1)

    client = GrytCloudClient(
        username=config.username,
        password=config.password,
        api_key_id=config.api_key_id,
        api_key_secret=config.api_key_secret
    )

    data = SqliteData(db_path=".gryt/gryt.db")
    return CloudSync(data, client)

@sync_app.command("pull")
def pull():
    """Pull cloud changes to local"""
    sync = _get_sync()
    result = sync.pull()

    typer.echo(f"Pulled from cloud:")
    typer.echo(f"  New generations: {result['new']}")
    typer.echo(f"  Updated: {result['updated']}")

    if result['conflicts']:
        typer.echo("\nConflicts detected:")
        for conflict in result['conflicts']:
            typer.echo(f"  {conflict['version']}: {conflict['reason']}")

@sync_app.command("push")
def push(version: str = typer.Option(None, help="Specific version to push")):
    """Push local changes to cloud"""
    sync = _get_sync()
    result = sync.push(version)

    typer.echo(f"Pushed to cloud:")
    typer.echo(f"  Created: {result['created']}")
    typer.echo(f"  Updated: {result['updated']}")

    if result['errors']:
        typer.echo("\nErrors:")
        for error in result['errors']:
            typer.echo(f"  {error['version']}: {error['error']}")

@sync_app.command("status")
def status(version: str = typer.Option(None)):
    """Show sync status"""
    sync = _get_sync()
    result = sync.status(version)

    if version:
        typer.echo(f"Status for {version}:")
        typer.echo(f"  Local: {result['local_status']}")
        typer.echo(f"  Cloud: {result['cloud_status']}")
        typer.echo(f"  Sync: {result['sync_status']}")
    else:
        typer.echo("Sync Status:")
        typer.echo(f"\nLocal only: {len(result['local_only'])}")
        for v in result['local_only']:
            typer.echo(f"  - {v}")

        typer.echo(f"\nCloud only: {len(result['cloud_only'])}")
        for v in result['cloud_only']:
            typer.echo(f"  - {v}")

        typer.echo(f"\nSynced: {len(result['synced'])}")

        if result['pending']:
            typer.echo(f"\nPending sync: {len(result['pending'])}")
            for v in result['pending']:
                typer.echo(f"  - {v}")

        if result['conflicts']:
            typer.echo(f"\nConflicts: {len(result['conflicts'])}")
            for c in result['conflicts']:
                typer.echo(f"  - {c['version']}: {c['message']}")
```

---

## Updated Workflows

### Hybrid Mode with Pull/Push

```bash
# Morning: Pull latest
gryt sync pull

# Check what's new
gryt sync status

# Work on new version
gryt generation new v1.5.0
gryt evolution start v1.5.0 --change FEAT-100
gryt run pipeline

# Promote (auto-pushes in hybrid mode)
gryt promote v1.5.0

# Or manually push
gryt sync push v1.5.0
```

### Cloud Mode with Continuous Sync

```bash
gryt config execution_mode cloud

# Auto-pull on any command
# Auto-push on any change

gryt generation new v1.0.0
# Immediately synced to cloud

gryt evolution start v1.0.0 --change FEAT-001
# Evolution synced to cloud

# Other developers see it immediately
```

### Handling Conflicts

```bash
# Check for conflicts
gryt sync status

# Output:
# Conflicts:
#   v1.0.0: Version exists in cloud

# Resolve by renaming
gryt generation rename v1.0.0 v1.0.1

# Or delete local and pull
gryt generation delete v1.0.0 --local-only
gryt sync pull
```

---

## Best Practices for Teams

### 1. Establish Version Strategy

**Option A: Developer-assigned ranges**
```
Developer A: v1.0.x, v1.2.x, v1.4.x
Developer B: v1.1.x, v1.3.x, v1.5.x
```

**Option B: Pull before create**
```bash
# Always pull first
gryt sync pull
gryt sync status
# See latest version, increment
```

**Option C: Date-based**
```
v2024.01.15  (Jan 15)
v2024.01.16  (Jan 16)
```

### 2. Use Draft Generations for Collaboration

```bash
# Team lead
gryt generation new v2.0.0
gryt sync push  # Creates draft in cloud

# Team members
gryt sync pull  # Get v2.0.0 draft
gryt evolution start v2.0.0 --change THEIR-CHANGE
# Evolutions auto-sync

# Lead promotes when all changes proven
gryt promote v2.0.0
```

### 3. Pull Regularly

```bash
# Add to daily routine
gryt sync pull

# Or add to pre-commit hook
# .git/hooks/pre-commit
#!/bin/bash
gryt sync pull
```

### 4. Promote from Designated Machine

Only one person/machine promotes to avoid race conditions:

```bash
# CI/CD server or team lead machine
gryt promote v2.0.0
```

---

## Migration from Current Implementation

### Phase 1: Add Sync Fields

```sql
-- Run migration
ALTER TABLE generations ADD COLUMN remote_id TEXT;
ALTER TABLE generations ADD COLUMN sync_status TEXT DEFAULT 'not_synced';
ALTER TABLE generations ADD COLUMN last_synced_at DATETIME;
```

### Phase 2: Backfill Remote IDs

```bash
# For existing synced generations, fetch remote_id from cloud
gryt sync backfill
```

### Phase 3: Enable Bidirectional Sync

```bash
# Users can now pull
gryt sync pull

# System uses new CloudSync class
```

### Phase 4: Update Documentation

Add sync commands to all workflow docs.

---

## Summary

**Problems Solved:**
- ✓ Conflict detection via version locking
- ✓ Bidirectional sync (pull/push)
- ✓ Multi-developer coordination
- ✓ Clear ownership model
- ✓ Conflict resolution rules

**Key Principles:**
- Cloud is source of truth for promoted releases
- Versions are unique and immutable when promoted
- Drafts can be collaborative
- Pull before create
- Evolutions belong to creator

**Commands:**
- `gryt sync pull` - Fetch cloud state
- `gryt sync push` - Push local changes
- `gryt sync status` - Check sync state
- `gryt sync push-evolutions` - Share work in progress

**Execution Modes:**
- Local: No sync (single dev)
- Hybrid: Sync on promote (recommended)
- Cloud: Continuous sync (full collaboration)
