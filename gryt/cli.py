from __future__ import annotations

import argparse
import importlib.util
import json
import sqlite3
import sys
from pathlib import Path
from types import ModuleType
from typing import Any, Optional
import shutil

from . import Pipeline, Runner, CommandStep, SqliteData, LocalRuntime


GRYT_DIRNAME = ".gryt"
DEFAULT_DB_RELATIVE = "gryt.db"
PIPELINES_SUBDIR = "pipelines"
CONFIG_FILENAME = "config"


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


def _resolve_pipeline_script(arg: str, base: Path) -> Path:
    # If arg is a valid file path, use it
    p = Path(arg)
    if p.exists():
        return p.resolve()
    # Try ./.gryt/pipelines/<arg>.py
    gryt_dir = base / GRYT_DIRNAME / PIPELINES_SUBDIR
    cand = gryt_dir / (arg if arg.endswith(".py") else f"{arg}.py")
    if cand.exists():
        return cand.resolve()
    # As a last attempt, treat arg relative to CWD
    return (base / arg).resolve()


def cmd_run(args: argparse.Namespace) -> int:
    script = _resolve_pipeline_script(args.script, Path.cwd())
    mod = _load_module_from_path(script)
    pipeline = _get_pipeline_from_module(mod)
    if pipeline is None:
        print("Error: Pipeline not found in script. Define PIPELINE or a build() -> Pipeline function.", file=sys.stderr)
        return 2
    results = pipeline.execute(parallel=args.parallel)
    print(json.dumps({"status": "ok", "results": results}, indent=2))
    return 0


def cmd_validate(args: argparse.Namespace) -> int:
    script = _resolve_pipeline_script(args.script, Path.cwd())
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


def _ensure_gryt_structure(root: Path, force: bool = False) -> Path:
    gryt_dir = root / GRYT_DIRNAME
    if gryt_dir.exists() and force:
        shutil.rmtree(gryt_dir)
    # Create directories
    (gryt_dir / PIPELINES_SUBDIR).mkdir(parents=True, exist_ok=True)
    # Create config file if missing
    cfg = gryt_dir / CONFIG_FILENAME
    if not cfg.exists():
        cfg.write_text("")
    # Create sqlite db file if missing
    db_path = gryt_dir / DEFAULT_DB_RELATIVE
    if not db_path.exists():
        # Touch by creating a connection
        conn = sqlite3.connect(str(db_path))
        conn.close()
    return gryt_dir


def cmd_init(args: argparse.Namespace) -> int:
    target = Path(args.path or ".").resolve()
    target.mkdir(parents=True, exist_ok=True)
    gryt_dir = _ensure_gryt_structure(target, force=args.force)

    # Create a starter pipeline under .gryt/pipelines/example.py
    example = gryt_dir / PIPELINES_SUBDIR / "example.py"
    if example.exists() and not args.force:
        # Do not overwrite if exists unless --force
        pass
    else:
        example.write_text(
            """#!/usr/bin/env python3
from gryt import Pipeline, Runner, CommandStep, SqliteData, LocalRuntime

data = SqliteData(db_path='.gryt/gryt.db')
runtime = LocalRuntime()

runner = Runner([
    CommandStep('hello', {'cmd': ['echo', 'hello']}, data=data),
    CommandStep('world', {'cmd': ['echo', 'world']}, data=data),
])

PIPELINE = Pipeline([runner], data=data, runtime=runtime)
""".lstrip()
        )
        try:
            example.chmod(example.stat().st_mode | 0o111)
        except Exception:
            pass

    print(f"Initialized gryt project at {gryt_dir}")
    return 0


def cmd_new(args: argparse.Namespace) -> int:
    name = args.name
    if not name:
        print("Error: --name is required", file=sys.stderr)
        return 2
    root = Path.cwd()
    gryt_dir = _ensure_gryt_structure(root, force=False)
    filename = name if name.endswith('.py') else f"{name}.py"
    path = gryt_dir / PIPELINES_SUBDIR / filename
    if path.exists() and not args.force:
        print(f"Refusing to overwrite existing {path}. Use --force to overwrite.", file=sys.stderr)
        return 3
    path.write_text(
        """#!/usr/bin/env python3
from gryt import Pipeline, Runner, CommandStep, SqliteData, LocalRuntime

# Example workflow created by `gryt new`

data = SqliteData(db_path='.gryt/gryt.db')
runtime = LocalRuntime()

runner = Runner([
    CommandStep('hello', {'cmd': ['echo', 'hello from new pipeline']}, data=data),
])

PIPELINE = Pipeline([runner], data=data, runtime=runtime)
""".lstrip()
    )
    try:
        path.chmod(path.stat().st_mode | 0o111)
    except Exception:
        pass
    print(f"Created new pipeline at {path}")
    return 0


def cmd_db(args: argparse.Namespace) -> int:
    db_path = Path(args.db) if args.db else (Path.cwd() / GRYT_DIRNAME / DEFAULT_DB_RELATIVE)
    if not db_path.exists():
        print(json.dumps({"error": f"Database not found: {db_path}"}, indent=2))
        return 2
    try:
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
        tables = [r[0] for r in cur.fetchall()]
        dump: dict[str, Any] = {"db": str(db_path), "tables": {}}
        for t in tables:
            cur.execute(f"SELECT * FROM {t}")
            rows = cur.fetchall()
            # Convert rows to JSON-serializable dicts; try to parse JSON-ish strings
            table_rows: list[dict[str, Any]] = []
            for row in rows:
                d = dict(row)
                for k, v in list(d.items()):
                    if isinstance(v, str) and v[:1] in "[{":
                        try:
                            d[k] = json.loads(v)
                        except Exception:
                            pass
                table_rows.append(d)
            dump["tables"][t] = table_rows
        print(json.dumps(dump, indent=2))
        conn.close()
        return 0
    except Exception as e:  # noqa: BLE001
        print(json.dumps({"error": str(e)}))
        return 2


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="gryt")
    sub = parser.add_subparsers(dest="command", required=True)

    p_init = sub.add_parser("init", help="Create a .gryt project structure")
    p_init.add_argument("path", nargs="?", help="directory to initialize the .gryt project")
    p_init.add_argument("--force", action="store_true", help="overwrite existing .gryt folder if present")
    p_init.set_defaults(func=cmd_init)

    p_run = sub.add_parser("run", help="Execute a pipeline script (path or name under .gryt/pipelines)")
    p_run.add_argument("script", help="path to pipeline script or name inside .gryt/pipelines")
    p_run.add_argument("--parallel", action="store_true", help="run runners in parallel")
    p_run.set_defaults(func=cmd_run)

    p_val = sub.add_parser("validate", help="Validate a pipeline script")
    p_val.add_argument("script", help="path to pipeline script or name inside .gryt/pipelines")
    p_val.set_defaults(func=cmd_validate)

    p_new = sub.add_parser("new", help="Create a new pipeline file in .gryt/pipelines/")
    p_new.add_argument("--name", required=True, help="name of the pipeline file (without .py or with .py)")
    p_new.add_argument("--force", action="store_true", help="overwrite if exists")
    p_new.set_defaults(func=cmd_new)

    p_db = sub.add_parser("db", help="Dump contents of the gryt SQLite DB as JSON")
    p_db.add_argument("--db", help="path to sqlite db (default ./.gryt/gryt.db)")
    p_db.set_defaults(func=cmd_db)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
