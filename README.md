# gryt Documentation

Welcome to the gryt docs. gryt is a minimal, Python-first CI framework that prioritizes:
- Local, platform-agnostic execution
- Clear, composable primitives
- Structured data outputs (SQLite-backed)

This documentation helps you get started quickly and understand the core concepts.

## Installation

We recommend using pipx to install the pure-Python CLI:

- pipx install gryt  # when published to PyPI
- pipx install .     # from a local checkout

For development in this repository:
- Ensure Python 3.8+ is installed.
- Optionally install editable: `python -m pip install -e .`

## Quickstart

Initialize a gryt project in the current directory and run a sample pipeline:

Using the installed command:
```
gryt init --force
# create a new pipeline in .gryt/pipelines
gryt new --name example
gryt validate example
gryt run example
```

Alternatively, module mode also works:
```
python -m gryt.cli run .gryt/pipelines/example.py
```

The sample pipeline runs simple echo steps and writes to `./.gryt/gryt.db`.

## What’s Inside

- CLI: `gryt init|new|validate|run|db` for creating, executing, and inspecting pipelines/databases.
- Primitives: Step, Runner, Pipeline, Data (SQLite), Runtime (Local), Versioning (simple semver with git tags).
- Hooks: Observe lifecycle events; send logs/metrics to remote services.
- Language Steps: Ready-made steps for Go, Python, Node/Svelte, and Rust.

See the following docs to dive deeper:
- CLI usage: docs/cli.md
- Concepts: docs/concepts.md
- Hooks: docs/hooks.md
- Destinations: docs/destinations.md
- Steps catalog: docs/steps.md
- Data store details: docs/data.md
- GitHub Actions starter: docs/github-actions.md
- CircleCI starter: docs/circleci.md
- GitLab CI starter: docs/gitlab-ci.md

## Examples

Browse examples in the ./examples directory:
- basic_pipeline.py: Minimal, runs anywhere.
- parallel_pipeline.py: Demonstrates multiple runners and parallel execution.
- language_*.py: Show how to use language-specific steps (require corresponding toolchains).

Run an example:
```
gryt run examples/basic_pipeline.py
```

## Roadmap (MVP)
- Solidify step outputs and error handling.
- Expand docs and ready-to-use templates for more ecosystems.
- Add richer versioning and runtime integrations.
