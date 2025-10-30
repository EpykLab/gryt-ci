# Repo Navigation - Working from Subdirectories

As of this update, **all gryt CLI commands work from any subdirectory within a git repository**.

## How It Works

The gryt CLI now automatically finds the repository root by:
1. Walking up the directory tree from your current location
2. Looking for a `.gryt` folder
3. Verifying a `.git` folder exists at the same level (safety check)
4. Using that location as the repo root for all operations

This matches git's behavior - you can run `gryt` commands anywhere in your repo tree.

## Example Usage

```bash
# Initialize at repo root
cd /home/user/myproject
gryt init

# Work from subdirectories - all commands work!
cd src/services/auth
gryt generation list          # ✓ Works
gryt generation new v1.0.0    # ✓ Works
gryt evolution start v1.0.0 --change FEAT-001  # ✓ Works
gryt run my-pipeline          # ✓ Works
gryt audit export -o audit.json -f json  # ✓ Works
gryt dashboard                # ✓ Works

# Even from deeply nested directories
cd tests/integration/api/v2
gryt generation list          # ✓ Still works!
```

## Commands Updated

All CLI commands now use repo root finding:

### Generation Commands
- `gryt generation new`
- `gryt generation list`
- `gryt generation show`
- `gryt generation promote`
- All find database at repo `.gryt/gryt.db`

### Evolution Commands
- `gryt evolution start`
- `gryt evolution list`
- All find database and policies at repo root

### Audit Commands
- `gryt audit export`
- `gryt audit snapshot`
- `gryt audit rollback`
- `gryt audit hotfix`
- All find database at repo root

### Dashboard
- `gryt dashboard`
- Finds database at repo root

### Sync Commands
- `gryt sync pull/push/status`
- Uses repo-aware config and database

### Pipeline Commands
- `gryt run <pipeline>`
- Searches for pipelines in repo `.gryt/pipelines/`

### Config Commands
- `gryt config set/get`
- Uses config hierarchy (local repo → global)

## Config Hierarchy

Config values are now looked up hierarchically:

1. **Local repo config** (`.gryt/config`) - highest priority
2. **Global config** (`~/.gryt.yaml`) - fallback

Example:
```yaml
# ~/.gryt.yaml (global)
username: my_global_user
api_key: global_key_123
execution_mode: hybrid

# /myproject/.gryt/config (local - overrides)
username: project_specific_user
# api_key inherited from global
# execution_mode inherited from global
```

When you run `gryt config get username` from `/myproject/src/foo/`:
- Finds repo root at `/myproject`
- Loads `/myproject/.gryt/config`
- Falls back to `~/.gryt.yaml` for missing values
- Returns `project_specific_user`

## Safety Features

- **Requires .git folder**: Won't mistake a nested `.gryt` folder for the repo root
- **Clear error messages**: If not in a repo, tells you to run `gryt init` or navigate to a repo
- **Backward compatible**: If you're already at repo root, works exactly as before

## Implementation

See `gryt/paths.py` for the core implementation:
- `find_repo_root()` - Walks up directory tree
- `get_repo_gryt_dir()` - Returns `.gryt` directory
- `get_repo_config_path()` - Returns config path
- `get_repo_db_path()` - Returns database path
- `ensure_in_repo()` - Raises error if not in repo

All CLI command modules now use these functions instead of `Path.cwd()`.
