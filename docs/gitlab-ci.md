# GitLab CI: Run a gryt Pipeline

This page provides a starter GitLab CI configuration to validate and run a gryt pipeline.

The pipeline installs your project (which exposes the `gryt` CLI) and then runs a specified pipeline script.

## Quick Start

1. Ensure your repository contains a runnable pipeline script. We recommend starting with the included example:
   - `examples/basic_pipeline.py` (uses an in-memory DB; safe for CI).

2. Create `.gitlab-ci.yml` with the following content:

```yaml
stages:
  - validate
  - run

variables:
  PIPELINE_PATH: "examples/basic_pipeline.py"

image: python:3.11-slim

before_script:
  - python -m pip install --upgrade pip
  - pip install .

validate:
  stage: validate
  script:
    - gryt validate "$PIPELINE_PATH"

run:
  stage: run
  script:
    - gryt run "$PIPELINE_PATH"
```

## Notes

- Override `PIPELINE_PATH` to point to your script (e.g., `pipeline.py`).
- If you need language-specific toolchains (Go/Node/Rust, etc.), extend the image or add setup steps (apt-get install, curl installers, etc.) before running.
- The example pipeline uses an in-memory DB to avoid collisions.
