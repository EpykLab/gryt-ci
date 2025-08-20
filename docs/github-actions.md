# GitHub Actions: Run a gryt Pipeline

This guide provides a starter GitHub Actions workflow to validate and run a gryt pipeline.

The workflow installs your project (which provides the `gryt` CLI) and then runs a specified pipeline script.

## Quick Start

1. Ensure your repository contains a runnable pipeline script. We recommend starting with the included example:
   - `examples/basic_pipeline.py` (uses an in-memory DB; safe for CI)

2. Add the following workflow file at `.github/workflows/gryt.yml`:

```yaml
name: gryt pipeline

on:
  push:
  pull_request:
  workflow_dispatch:
    inputs:
      pipeline_path:
        description: 'Path to the Python script that defines the gryt Pipeline (default: examples/basic_pipeline.py)'
        required: false
        default: 'examples/basic_pipeline.py'

jobs:
  run-gryt:
    runs-on: ubuntu-latest
    env:
      PIPELINE_PATH: ${{ github.event.inputs.pipeline_path || 'examples/basic_pipeline.py' }}
    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.x'

      - name: Install gryt (from repo)
        run: |
          python -m pip install --upgrade pip
          pip install .

      - name: Validate pipeline
        run: gryt validate "$PIPELINE_PATH"

      - name: Run pipeline
        run: gryt run "$PIPELINE_PATH"
```

## Reusable workflow (for other repos)

If another repository wants to reuse this repo's workflow, you can reference the reusable workflow:

1. Ensure this repository is accessible to the consumer repo.
2. In the consumer repo, create a workflow like:

```yaml
name: Use gryt reusable workflow

on:
  workflow_dispatch:
    inputs:
      pipeline_path:
        description: 'Path to pipeline script in this repository'
        required: false
        default: 'examples/basic_pipeline.py'

jobs:
  call-gryt:
    uses: <owner>/<repo>/github/workflows/gryt-reusable.yml@<ref>
    with:
      pipeline_path: ${{ inputs.pipeline_path }}
```

Replace <owner>/<repo> with this repository and <ref> with a branch or tag.

## Notes

- Default pipeline script is `examples/basic_pipeline.py`. Override when manually dispatching by setting the `pipeline_path` input.
- If you maintain your pipeline at a different path (e.g., `pipeline.py` at repo root), either:
  - Change the default in the workflow, or
  - Trigger the workflow manually and set `pipeline_path` accordingly.
- The example uses `pip install .` to install the project and expose the `gryt` CLI.
- For language-specific steps (Go, Node, Rust, etc.), ensure the required toolchains are present in the job image (or add setup steps accordingly).
- If your pipeline writes to a persistent DB (e.g., `.gryt.db`), consider rotating/removing the file between runs or use unique step ids to avoid primary key collisions. The example pipeline avoids this by using an in-memory DB.
