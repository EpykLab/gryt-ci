# Generation Workflow Example

This document shows the complete workflow for creating, editing, and working with generations.

## The Problem This Solves

Previously, you could create a generation with `gryt generation new`, which creates a YAML file and DB entry. You could edit the YAML file, but there was **no way to sync those changes back to the database**. This is now fixed with the `gryt generation update` command.

## Complete Workflow

### Step 1: Create Generation

```bash
gryt generation new v1.5.0
```

Output:
```
✓ Created generation v1.5.0
  Database: .gryt/gryt.db
  YAML: .gryt/generations/v1.5.0.yaml

Edit .gryt/generations/v1.5.0.yaml to define changes.
Then run 'gryt generation update v1.5.0' to sync changes to database.
```

This creates:
- Database record in `.gryt/gryt.db`
- YAML file at `.gryt/generations/v1.5.0.yaml` with a placeholder change

### Step 2: Edit YAML File

Edit `.gryt/generations/v1.5.0.yaml`:

```yaml
version: v1.5.0
description: "Q1 Feature Release - Authentication & Analytics"
changes:
  - type: add
    id: FEAT-201
    title: "OAuth2 social login (Google, GitHub)"
    description: "Allow users to sign in with OAuth providers"

  - type: add
    id: FEAT-202
    title: "Real-time analytics dashboard"
    description: "Display user activity metrics in real-time"

  - type: fix
    id: BUG-88
    title: "Session timeout not working correctly"
    description: "Fix session expiration logic"

  - type: refine
    id: PERF-15
    title: "Optimize database queries for user list"
    description: "Add indexes and query optimization"

pipeline_template: full-ci-pipeline
```

### Step 3: Update Database from YAML

```bash
gryt generation update v1.5.0
```

Output:
```
Reading changes from .gryt/generations/v1.5.0.yaml...
✓ Updated generation v1.5.0 from YAML
  Changes: 4
    • [add] FEAT-201: OAuth2 social login (Google, GitHub)
    • [add] FEAT-202: Real-time analytics dashboard
    • [fix] BUG-88: Session timeout not working correctly
    • [refine] PERF-15: Optimize database queries for user list
```

### Step 4: Generate Validation Pipelines (Optional)

```bash
gryt generation gen-test v1.5.0 --all
```

Output:
```
✓ Generated v1_5_0_FEAT_201_VALIDATION_PIPELINE.py for FEAT-201
✓ Generated v1_5_0_FEAT_202_VALIDATION_PIPELINE.py for FEAT-202
✓ Generated v1_5_0_BUG_88_VALIDATION_PIPELINE.py for BUG-88
✓ Generated v1_5_0_PERF_15_VALIDATION_PIPELINE.py for PERF-15

✓ Generated 4 validation pipeline(s)
  Location: .gryt/pipelines/

Next steps:
1. Review and customize the generated pipeline files
2. Implement the test cases
3. Run 'gryt evolution start v1.5.0 --change <id>' to validate changes
```

This creates dedicated validation pipeline files for each change. You can now edit these files to implement the actual tests.

### Step 5: Verify Changes

```bash
gryt generation show v1.5.0
```

Output:
```
Generation: v1.5.0
Status: draft
Description: Q1 Feature Release - Authentication & Analytics

Changes (4):
  FEAT-201  add     OAuth2 social login (Google, GitHub)              unproven
  FEAT-202  add     Real-time analytics dashboard                     unproven
  BUG-88    fix     Session timeout not working correctly            unproven
  PERF-15   refine  Optimize database queries for user list          unproven

No evolutions yet.
```

### Step 6: Start Working on Changes

```bash
# Work on first feature
gryt evolution start v1.5.0 --change FEAT-201

# Implement the feature
# ... code changes ...
git add .
git commit -m "feat: add OAuth2 social login [FEAT-201]"

# Run pipeline to prove the change
gryt run full-ci-pipeline
# Creates v1.5.0-rc.1 tag on success

# Work on second feature
gryt evolution start v1.5.0 --change FEAT-202
# ... implement ...
gryt run full-ci-pipeline
# Creates v1.5.0-rc.2 tag

# Work on bug fix
gryt evolution start v1.5.0 --change BUG-88
# ... fix bug ...
gryt run full-ci-pipeline
# Creates v1.5.0-rc.3 tag

# Work on optimization
gryt evolution start v1.5.0 --change PERF-15
# ... optimize ...
gryt run full-ci-pipeline
# Creates v1.5.0-rc.4 tag
```

### Step 7: Check Progress

```bash
gryt evolution list v1.5.0
```

Output:
```
Evolutions for v1.5.0:

Tag             Change     Status  Created
v1.5.0-rc.1    FEAT-201   pass    2025-10-30 12:00
v1.5.0-rc.2    FEAT-202   pass    2025-10-30 14:30
v1.5.0-rc.3    BUG-88     pass    2025-10-30 16:15
v1.5.0-rc.4    PERF-15    pass    2025-10-30 17:45
```

### Step 8: Promote to Production

```bash
gryt generation promote v1.5.0
```

Output:
```
Checking promotion gates...
✓ All changes proven (4/4)
✓ No failed evolutions
✓ Minimum evolutions met

Promoting v1.5.0 to production...
✓ Generation promoted
✓ Git tag created: v1.5.0

Generation v1.5.0 is now deployable!
```

## Key Points

1. **Create** - `gryt generation new` creates both DB and YAML
2. **Edit** - Edit the YAML file with your real changes
3. **Update** - `gryt generation update` syncs YAML → DB
4. **Generate Tests** - `gryt generation gen-test` creates validation pipeline scaffolds
5. **Verify** - `gryt generation show` confirms changes are in DB
6. **Prove** - Create evolutions for each change
7. **Promote** - Promote when all changes are proven

## Making Changes After Creation

If you need to add/modify changes after initial creation:

```bash
# Edit the YAML file
vim .gryt/generations/v1.5.0.yaml

# Add a new change to the changes list
# - type: add
#   id: FEAT-203
#   title: "New feature discovered during dev"

# Update database
gryt generation update v1.5.0

# Generate validation pipeline for the new change
gryt generation gen-test v1.5.0 --change FEAT-203

# Verify the new change is there
gryt generation show v1.5.0

# Implement tests in the generated pipeline, then start evolution
gryt evolution start v1.5.0 --change FEAT-203
```

## Benefits

- **YAML as source of truth** - Easy to edit, version control friendly
- **Database for operations** - Fast queries, evolutions link to changes
- **Bidirectional sync** - Changes flow: YAML → DB
- **Validation** - YAML schema validation on update
- **Flexibility** - Edit YAML anytime, update DB when ready
