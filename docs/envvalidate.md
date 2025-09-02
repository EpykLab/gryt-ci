# Environment Validation

EnvValidate lets you verify a pipeline’s environment before running any steps. It aggregates all misconfigurations in one report (no fail-fast) so you can fix everything at once, locally or in CI.

Key properties:
- Aggregates issues instead of stopping at the first.
- Optional: you decide which validators to include in your pipeline.
- Re-usable via CLI (gryt env-validate) without running the pipeline.

## Built-in Validators

- EnvVarValidator(required=[...])
  - Ensures required environment variables exist and are non-empty.
  - Example: require GITHUB_TOKEN, NPM_TOKEN, etc.

- ToolValidator(tools=[{ name, min_version?, version_args?, version_regex? }])
  - Ensures required CLI tools are on PATH and optionally meet a minimum version.
  - min_version: compare semantic-like versions (e.g., '8.0.0').
  - version_args: override the version flag (default ['--version']).
  - version_regex: regex to extract version from tool output; falls back to the first x.y(.z) token.

Both validators return a list of issues without raising. Each issue includes: kind, name, message, and optional details.

## Pipeline Integration

Attach validators to your Pipeline. When pipeline.execute() is called, validation runs first. If issues are found, execution is skipped and a report is returned.

Example:
