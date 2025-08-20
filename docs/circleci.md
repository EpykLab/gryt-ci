# CircleCI: Run a gryt Pipeline

This page provides a starter CircleCI configuration to validate and run a gryt pipeline.

The config installs your project (which exposes the `gryt` CLI) and then runs a specified pipeline script.

## Quick Start

1. Ensure your repository contains a runnable pipeline script. We recommend starting with the included example:
   - `examples/basic_pipeline.py` (uses an in-memory DB; safe for CI).

2. Create `.circleci/config.yml` with the following content:

```yaml
version: 2.1

parameters:
  pipeline_path:
    type: string
    default: "examples/basic_pipeline.py"

executors:
  python:
    docker:
      - image: cimg/python:3.11

jobs:
  run-gryt:
    executor: python
    environment:
      PIPELINE_PATH: << pipeline.parameters.pipeline_path >>
    steps:
      - checkout
      - run:
          name: Upgrade pip
          command: python -m pip install --upgrade pip
      - run:
          name: Install gryt (from repo)
          command: pip install .
      - run:
          name: Validate pipeline
          command: gryt validate "$PIPELINE_PATH"
      - run:
          name: Run pipeline
          command: gryt run "$PIPELINE_PATH"

workflows:
  gryt_pipeline:
    jobs:
      - run-gryt:
          name: run-gryt
          pipeline_path: "examples/basic_pipeline.py"
```

## Notes

- Override the `pipeline_path` parameter (in the workflow/job) to point to your script (e.g., `pipeline.py`).
- If you need language-specific toolchains (Go/Node/Rust, etc.), add setup steps (e.g., `cimg/node`, `setup-go`, or additional apt installs) before running the steps.
- The examples/basic_pipeline.py uses an in-memory DB to avoid collisions and is safe as a CI sanity check.
