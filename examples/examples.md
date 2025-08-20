# Examples

This folder contains runnable examples for gryt. Use the installed CLI to run them:

```
gryt run examples/basic_pipeline.py
gryt run examples/parallel_pipeline.py --parallel
```

Hooks examples:
- hook_http_pipeline.py – demonstrates HttpHook posting to a remote endpoint (optional).

Destinations examples:
- publish_github_release.py – uploads files as GitHub Release assets (requires GITHUB_TOKEN).
- publish_pypi.py – uploads Python dists via twine (requires twine and credentials).
- publish_npm.py – runs npm publish (requires npm auth).

Language-focused examples demonstrate usage of language-specific steps. They require the corresponding toolchains installed and available on PATH (e.g., `go`, `npm`, `cargo`, `pytest`). If those tools are not installed, those examples will fail – use them as reference templates.

- language_python.py – PipInstallStep / PytestStep
- language_node.py – NpmInstallStep / SvelteBuildStep
- language_go.py – GoModDownloadStep / GoBuildStep / GoTestStep
- language_rust.py – CargoBuildStep / CargoTestStep
