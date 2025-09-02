#!/usr/bin/env python3
"""
Example: Environment Validation Pipeline

This example shows how to attach environment validators to a Pipeline so that
misconfigurations are detected before any steps run. Validation aggregates all
issues (no fail-fast) and returns a structured report.

Usage:
  - Validate only (no steps executed):
      gryt env-validate examples/env_validate_pipeline.py
  - Run the pipeline (validation happens first and short-circuits on issues):
      gryt run examples/env_validate_pipeline.py
"""

from gryt import (
    Pipeline,
    Runner,
    CommandStep,
    SqliteData,
    LocalRuntime,
    EnvVarValidator,
    ToolValidator,
)

# Configure validator list (edit to match your project)
# - Require GITHUB_TOKEN to exist (e.g., for GitHub releases)
# - Ensure common tools exist, and optionally enforce minimum versions
validators = [
    EnvVarValidator(required=["GITHUB_TOKEN"]),
    ToolValidator(
        tools=[
            {"name": "npm", "min_version": "8.0.0"},
            {"name": "python"},
            {"name": "cargo"},
            {"name": "go"},
        ]
    ),
]

# Typical pipeline boilerplate
data = SqliteData(db_path=".gryt/gryt.db")
runtime = LocalRuntime()

runner = Runner(
    [
        CommandStep("build", {"cmd": ["echo", "building..."]}, data=data),
        CommandStep("test", {"cmd": ["echo", "testing..."]}, data=data),
    ],
    data=data,
)

# Attach validators to the pipeline. If validation fails, execute() returns:
#   {"status": "invalid_env", "issues": [...]}
PIPELINE = Pipeline([runner], data=data, runtime=runtime, validators=validators)
