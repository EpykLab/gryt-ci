from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType
from typing import Any, Optional

from . import Pipeline, Runner, CommandStep, SqliteData, LocalRuntime


def _load_module_from_path(path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(path.stem, str(path))
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot import module from {path}")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[path.stem] = mod
    spec.loader.exec_module(mod)
    return mod


def _get_pipeline_from_module(mod: ModuleType) -> Optional[Pipeline]:
    # Convention 1: module.PIPELINE is a Pipeline
    obj = getattr(mod, "PIPELINE", None)
    if isinstance(obj, Pipeline):
        return obj
    # Convention 2: module.build() returns a Pipeline
    build = getattr(mod, "build", None)
    if callable(build):
        p = build()
        if isinstance(p, Pipeline):
            return p
    return None


def cmd_run(args: argparse.Namespace) -> int:
    script = Path(args.script).resolve()
    mod = _load_module_from_path(script)
    pipeline = _get_pipeline_from_module(mod)
    if pipeline is None:
        print("Error: Pipeline not found in script. Define PIPELINE or a build() -> Pipeline function.", file=sys.stderr)
        return 2
    results = pipeline.execute(parallel=args.parallel)
    print(json.dumps({"status": "ok", "results": results}, indent=2))
    return 0


def cmd_validate(args: argparse.Namespace) -> int:
    script = Path(args.script).resolve()
    try:
        mod = _load_module_from_path(script)
        pipeline = _get_pipeline_from_module(mod)
        if pipeline is None:
            print("Invalid: No PIPELINE or build() returning Pipeline found.")
            return 2
        print("Valid: Pipeline is loadable.")
        return 0
    except Exception as e:  # noqa: BLE001
        print(f"Invalid: {e}")
        return 2


def cmd_init(args: argparse.Namespace) -> int:
    target = Path(args.path or ".").resolve()
    target.mkdir(parents=True, exist_ok=True)
    sample = target / "pipeline.py"
    if sample.exists() and not args.force:
        print(f"Refusing to overwrite existing {sample}. Use --force to overwrite.", file=sys.stderr)
        return 3
    sample.write_text(
        """
from gryt import Pipeline, Runner, CommandStep, SqliteData, LocalRuntime

data = SqliteData(db_path='.gryt.db')
runtime = LocalRuntime()

runner = Runner([
    CommandStep('hello', {'cmd': ['echo', 'hello']}),
    CommandStep('world', {'cmd': ['echo', 'world']}),
], data=data)

PIPELINE = Pipeline([runner], data=data, runtime=runtime)
""".lstrip()
    )
    print(f"Initialized sample pipeline at {sample}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="gryt")
    sub = parser.add_subparsers(dest="command", required=True)

    p_init = sub.add_parser("init", help="Create a sample pipeline.py")
    p_init.add_argument("path", nargs="?", help="directory to place sample pipeline.py")
    p_init.add_argument("--force", action="store_true", help="overwrite if exists")
    p_init.set_defaults(func=cmd_init)

    p_run = sub.add_parser("run", help="Execute a pipeline script")
    p_run.add_argument("script", help="path to pipeline script")
    p_run.add_argument("--parallel", action="store_true", help="run runners in parallel")
    p_run.set_defaults(func=cmd_run)

    p_val = sub.add_parser("validate", help="Validate a pipeline script")
    p_val.add_argument("script", help="path to pipeline script")
    p_val.set_defaults(func=cmd_validate)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
