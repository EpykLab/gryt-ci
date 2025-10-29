from __future__ import annotations

import importlib.util
import json
import sqlite3
import sys
from pathlib import Path
from types import ModuleType
from typing import Any, Optional
import shutil

import typer

from . import Pipeline, Runner, CommandStep, SqliteData, LocalRuntime
from .cloud import cloud_app
from .generation_cli import generation_app
from .config import Config


GRYT_DIRNAME = ".gryt"
DEFAULT_DB_RELATIVE = "gryt.db"
PIPELINES_SUBDIR = "pipelines"
MANIFESTS_SUBDIR = "manifests"
CONFIG_FILENAME = "config"

app = typer.Typer(name="gryt", help="Gryt CLI: run and manage gryt pipelines.", no_args_is_help=True)

# Register subcommands
app.add_typer(cloud_app, name="cloud")
app.add_typer(generation_app, name="generation")


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


def cmd_run(script: str, parallel: bool = False, show: bool = False) -> int:
    try:
        script_path = _resolve_pipeline_script(script, Path.cwd())
        mod = _load_module_from_path(script_path)
        pipeline = _get_pipeline_from_module(mod)
        if pipeline is None:
            typer.echo(
                "Error: Pipeline not found in script. Define PIPELINE or a build() -> Pipeline function.",
                err=True,
            )
            return 2
        results = pipeline.execute(parallel=parallel, show=show)
        
        # Check for failures in results and propagate non-zero exit codes
        exit_code = 0
        
        # Check environment validation failures
        if results.get("status") == "invalid_env":
            exit_code = 1
        else:
            # Check runner results for failures
            runners = results.get("runners", results)  # Handle both formats
            for runner_result in runners.values():
                steps = runner_result.get("steps", {})
                for step_result in steps.values():
                    # Check if step has error status or non-zero returncode
                    if step_result.get("status") == "error":
                        # Prefer the actual returncode if available, otherwise use 1
                        step_rc = step_result.get("returncode")
                        if step_rc is not None and step_rc != 0:
                            exit_code = step_rc
                        else:
                            exit_code = 1
                        break  # Exit early on first failure
                if exit_code != 0:
                    break
        
        typer.echo(json.dumps({"status": "ok" if exit_code == 0 else "error", "results": results}, indent=2))
        return exit_code
    except Exception as e:  # noqa: BLE001
        typer.echo(f"Error: {e}", err=True)
        return 2


def cmd_validate(script: str) -> int:
    script_path = _resolve_pipeline_script(script, Path.cwd())
    try:
        mod = _load_module_from_path(script_path)
        pipeline = _get_pipeline_from_module(mod)
        if pipeline is None:
            typer.echo("Invalid: No PIPELINE or build() returning Pipeline found.")
            return 2
        typer.echo("Valid: Pipeline is loadable.")
        return 0
    except Exception as e:  # noqa: BLE001
        typer.echo(f"Invalid: {e}")
        return 2


def _ensure_gryt_structure(root: Path, force: bool = False) -> Path:
    gryt_dir = root / GRYT_DIRNAME
    if gryt_dir.exists() and force:
        shutil.rmtree(gryt_dir)
    # Create directories
    (gryt_dir / PIPELINES_SUBDIR).mkdir(parents=True, exist_ok=True)
    (gryt_dir / MANIFESTS_SUBDIR).mkdir(parents=True, exist_ok=True)
    # Create config file if missing
    cfg = gryt_dir / CONFIG_FILENAME
    if not cfg.exists():
        cfg.write_text("")
    # Create sqlite db file (and initialize schema)
    db_path = gryt_dir / DEFAULT_DB_RELATIVE
    try:
        # Instantiate SqliteData to initialize predefined tables
        data = SqliteData(db_path=str(db_path))
        data.close()
    except Exception:
        # Fallback: touch file to ensure it exists
        conn = sqlite3.connect(str(db_path))
        conn.close()
    return gryt_dir


def cmd_init(path: Optional[Path], force: bool) -> int:
    target = Path(path or ".").resolve()
    target.mkdir(parents=True, exist_ok=True)
    gryt_dir = _ensure_gryt_structure(target, force=force)

    # Create a starter pipeline under .gryt/pipelines/example.py
    example = gryt_dir / PIPELINES_SUBDIR / "example.py"
    if example.exists() and not force:
        # Do not overwrite if exists unless --force
        pass
    else:
        example.write_text(
            """#!/usr/bin/env python3
from gryt import Pipeline, Runner, CommandStep, SqliteData, LocalRuntime

version = SimpleVersioning().get_last_commit_hash()
data = SqliteData(db_path='.gryt/gryt.db')
runtime = LocalRuntime()

runner = Runner([
    CommandStep('hello', {'cmd': ['echo', 'hello']}, data=data),
    CommandStep('world', {'cmd': ['echo', 'world']}, data=data),
], data=data)

PIPELINE = Pipeline([runner], data=data, runtime=runtime)
""".lstrip()
        )
        try:
            example.chmod(example.stat().st_mode | 0o111)
        except Exception:
            pass

    typer.echo(f"Initialized gryt project at {gryt_dir}")
    return 0


def _render_steps_template(step_tokens: list[str]) -> tuple[list[str], list[str]]:
    """
    Return (imports, step_instances) where:
    - imports: list of importable class names from `gryt` that must be added in the import line
    - step_instances: list of python code lines to instantiate steps inside Runner([...])
    """
    # Normalize tokens
    tokens = [t.strip().lower() for t in step_tokens if t and t.strip()]
    imports: set[str] = set()
    steps: list[str] = []

    def add(step_class: str, instance_line: str) -> None:
        imports.add(step_class)
        steps.append(instance_line)

    for t in tokens:
        if t in ("go", "golang"):
            add("GoModDownloadStep", "    GoModDownloadStep('go_mod_download', {'cwd': '.'}, data=data),")
            add("GoBuildStep", "    GoBuildStep('go_build', {'cwd': '.', 'packages': ['./...']}, data=data),")
            add("GoTestStep", "    GoTestStep('go_test', {'cwd': '.', 'packages': ['./...'], 'json': False}, data=data),")
        elif t in ("python", "py"):
            add("PipInstallStep", "    # PipInstallStep('pip_install', {'packages': ['pytest'], 'user': True}, data=data),")
            add("PytestStep", "    PytestStep('pytest', {'args': ['-q'], 'paths': []}, data=data),")
        elif t in ("js", "node", "javascript", "nodejs"):
            add("NpmInstallStep", "    NpmInstallStep('npm_install', {'cwd': '.', 'use_ci': True}, data=data),")
            # We don't assume Svelte; users can add specific build steps later.
        elif t in ("rust",):
            add("CargoBuildStep", "    CargoBuildStep('cargo_build', {'cwd': '.', 'release': False}, data=data),")
            add("CargoTestStep", "    CargoTestStep('cargo_test', {'cwd': '.', 'workspace': False}, data=data),")
        elif t in ("docker", "container"):  # container image build
            add(
                "ContainerBuildStep",
                "    ContainerBuildStep('build_image', {'context_path': '.', 'dockerfile': 'Dockerfile', 'tags': [], 'pull': False, 'push': False}, data=data),",
            )
        else:
            # Unknown token: create a placeholder CommandStep so user can fill in
            imports.add("CommandStep")
            steps.append(f"    CommandStep('{t}', {{'cmd': ['echo', 'TODO: implement {t} step']}}, data=data),")

    return sorted(imports), steps

def _render_destination_template(dest_token: Optional[str]) -> tuple[list[str], list[str]]:
    """
    Return (imports, step_instances) for a destination preset to build and publish artifacts.
    Supported destinations: npm, pypi, gh
    """
    if not dest_token:
        return [], []
    t = dest_token.strip().lower()
    imports: set[str] = set()
    steps: list[str] = []

    def add(step_class: str, instance_line: str) -> None:
        imports.add(step_class)
        steps.append(instance_line)

    if t in ("npm",):
        # NPM: install deps, build, then publish via NpmRegistryDestination
        add("NpmInstallStep", "    NpmInstallStep('npm_ci', {'cwd': '.', 'use_ci': True}, data=data),")
        add("CommandStep", "    CommandStep('npm_build', {'cmd': ['npm', 'run', 'build'], 'cwd': '.'}, data=data),")
        add("PublishDestinationStep", "    PublishDestinationStep('publish_npm', NpmRegistryDestination('npm_publish', {'package_dir': '.'}), ['.'], data=data),")
        imports.update(["NpmRegistryDestination"])
    elif t in ("pypi", "py", "python"):
        # PyPI: build wheel/sdist, then publish via PyPIDestination
        add("CommandStep", "    CommandStep('py_build', {'cmd': ['python', '-m', 'build']}, data=data),")
        add("PublishDestinationStep", "    PublishDestinationStep('publish_pypi', PyPIDestination('pypi', {'dist_glob': 'dist/*'}), ['dist/*'], data=data),")
        imports.update(["PyPIDestination"])
    elif t in ("gh", "github"):
        # GitHub Release: assume artifacts in ./dist and publish via GitHubReleaseDestination (fill in owner/repo/tag)
        add("CommandStep", "    CommandStep('build_artifacts', {'cmd': ['bash', '-lc', 'echo \"TODO: build artifacts into ./dist\"']}, data=data),")
        add("PublishDestinationStep", "    PublishDestinationStep('publish_gh', GitHubReleaseDestination('gh_release', {'owner': 'YOUR_ORG', 'repo': 'YOUR_REPO', 'tag': 'v0.1.0'}), ['dist/*'], data=data),")
        imports.update(["GitHubReleaseDestination"])
    else:
        # Unknown destination: placeholder echo
        add("CommandStep", "    CommandStep('publish_" + t + "', {'cmd': ['echo', 'TODO: publish to " + t + "'], 'cwd': '.'}, data=data),")

    return sorted(imports), steps



def _render_validators_template(dest_tokens: list[str]) -> tuple[list[str], list[str]]:
    """
    Return (imports, validator_instances) to include in a 'validators = [...]' list.
    We infer basic requirements from destinations.
    """
    imports: set[str] = set()
    validators: list[str] = []
    tokens = [t.strip().lower() for t in dest_tokens if t and t.strip()]

    def add(validator_class: str, instance_line: str) -> None:
        imports.add(validator_class)
        validators.append(instance_line)

    for t in tokens:
        if t in ("gh", "github"):
            add("EnvVarValidator", "    EnvVarValidator(required=['GITHUB_TOKEN']),")
        if t in ("npm",):
            add("ToolValidator", "    ToolValidator(tools=[{'name': 'npm'}]),")
            add("EnvVarValidator", "    EnvVarValidator(required=['NPM_TOKEN']),")
        if t in ("pypi", "py", "python"):
            add("ToolValidator", "    ToolValidator(tools=[{'name': 'python'}, {'name': 'twine'}]),")
    return sorted(imports), validators


def cmd_new(name: str, force: bool, steps: Optional[str] = None, destination: Optional[str] = None) -> int:
    if not name:
        typer.echo("Error: --name is required", err=True)
        return 2
    root = Path.cwd()
    gryt_dir = _ensure_gryt_structure(root, force=False)
    filename = name if name.endswith(".py") else f"{name}.py"
    path = gryt_dir / PIPELINES_SUBDIR / filename
    if path.exists() and not force:
        typer.echo(f"Refusing to overwrite existing {path}. Use --force to overwrite.", err=True)
        return 3

    # Build template
    imports = ["Pipeline", "Runner", "SqliteData", "LocalRuntime"]
    step_lines: list[str]
    if steps:
        tokens = [tok for part in steps.split(",") for tok in [part]]
        extra_imports, step_lines = _render_steps_template(tokens)
        imports.extend(extra_imports)
    else:
        # Basic default
        imports.append("CommandStep")
        step_lines = [
            "    CommandStep('hello', {'cmd': ['echo', 'hello from new pipeline']}, data=data),",
        ]

    # Destination presets (accept comma-separated list and aggregate)
    dest_imports_total: set[str] = set()
    dest_steps_total: list[str] = []
    validator_imports_total: set[str] = set()
    validator_lines_total: list[str] = []
    dest_tokens: list[str] = []
    if destination:
        dest_tokens = [t.strip() for t in destination.split(",") if t and t.strip()]
        for t in dest_tokens:
            di, ds = _render_destination_template(t)
            dest_imports_total.update(di)
            dest_steps_total.extend(ds)
        vi, vs = _render_validators_template(dest_tokens)
        validator_imports_total.update(vi)
        validator_lines_total.extend(vs)

    imports.extend(sorted(dest_imports_total))
    imports.extend(sorted(validator_imports_total))
    if dest_steps_total:
        # Ensure CommandStep import if any destination steps use it
        if "CommandStep" not in imports and any("CommandStep(" in s for s in dest_steps_total):
            imports.append("CommandStep")
        step_lines.extend(dest_steps_total)

    import_str = ", ".join(sorted(set(imports)))
    steps_str = "\n".join(step_lines)

    if validator_lines_total:
        validators_block = "validators = [\n" + "\n".join(validator_lines_total) + "\n]\n\n"
        validators_arg = ", validators=validators"
    else:
        validators_block = ""
        validators_arg = ""

    content = f"""#!/usr/bin/env python3
from gryt import {import_str}

# Workflow created by `gryt new`

# Use project-local database by default
# Tip: if you prefer ephemeral runs during experimentation, use SqliteData(in_memory=True)

version = SimpleVersioning().get_last_commit_hash()
data = SqliteData(db_path='.gryt/gryt.db')
runtime = LocalRuntime()
{validators_block}runner = Runner([
{steps_str}
], data=data)

PIPELINE = Pipeline([runner], data=data, runtime=runtime{validators_arg})
""".lstrip()

    path.write_text(content)
    try:
        path.chmod(path.stat().st_mode | 0o111)
    except Exception:
        pass
    typer.echo(f"Created new pipeline at {path}")
    return 0


def cmd_db(db: Optional[Path]) -> int:
    db_path = Path(db) if db else (Path.cwd() / GRYT_DIRNAME / DEFAULT_DB_RELATIVE)
    if not db_path.exists():
        typer.echo(json.dumps({"error": f"Database not found: {db_path}"}, indent=2))
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
        typer.echo(json.dumps(dump, indent=2))
        conn.close()
        return 0
    except Exception as e:  # noqa: BLE001
        typer.echo(json.dumps({"error": str(e)}))
        return 2


# Typer command bindings


@app.command("init", help="Create a .gryt project structure")
def init_command(
    path: Optional[Path] = typer.Argument(
        None, help="Directory to initialize the .gryt project"
    ),
    force: bool = typer.Option(
        False, "--force", help="Overwrite existing .gryt folder if present"
    ),
):
    code = cmd_init(path=path, force=force)
    raise typer.Exit(code)


@app.command("run", help="Execute a pipeline script (path or name under .gryt/pipelines)")
def run_command(
    script: str = typer.Argument(..., help="Path to pipeline script or name inside .gryt/pipelines"),
    parallel: bool = typer.Option(False, "--parallel", help="Run runners in parallel"),
    show: bool = typer.Option(False, "--show", help="Dump command output to stdout while running"),
):
    code = cmd_run(script=script, parallel=parallel, show=show)
    raise typer.Exit(code)


@app.command("validate", help="Validate a pipeline script")
def validate_command(
    script: str = typer.Argument(..., help="Path to pipeline script or name inside .gryt/pipelines"),
):
    code = cmd_validate(script=script)
    raise typer.Exit(code)


@app.command("new", help="Create a new pipeline file in .gryt/pipelines/")
def new_command(
    name: str = typer.Option(..., "--name", help="Name of the pipeline file (without .py or with .py)"),
    force: bool = typer.Option(False, "--force", help="Overwrite if exists"),
    steps: Optional[str] = typer.Option(None, "--steps", help="Comma-separated list of step presets: go,python,js,docker,rust, ..."),
    destination: Optional[str] = typer.Option(None, "--destination", help="Comma-separated publish destination presets: npm, pypi, gh"),
):
    code = cmd_new(name=name, force=force, steps=steps, destination=destination)
    raise typer.Exit(code)


def cmd_env_validate(script: str) -> int:
    try:
        script_path = _resolve_pipeline_script(script, Path.cwd())
        mod = _load_module_from_path(script_path)
        pipeline = _get_pipeline_from_module(mod)
        if pipeline is None:
            typer.echo(
                "Error: Pipeline not found in script. Define PIPELINE or a build() -> Pipeline function.",
                err=True,
            )
            return 2
        report = pipeline.validate_environment() if hasattr(pipeline, "validate_environment") else {"status": "ok", "issues": []}
        typer.echo(json.dumps({"status": "ok", "report": report}, indent=2))
        return 0
    except Exception as e:  # noqa: BLE001
        typer.echo(f"Error: {e}", err=True)
        return 2


@app.command("env-validate", help="Validate the environment for a pipeline without running it")
def env_validate_command(
    script: str = typer.Argument(..., help="Path to pipeline script or name inside .gryt/pipelines"),
):
    code = cmd_env_validate(script=script)
    raise typer.Exit(code)


@app.command("db", help="Dump contents of the gryt SQLite DB as JSON")
def db_command(
    db: Optional[Path] = typer.Option(None, "--db", help="Path to sqlite db (default ./.gryt/gryt.db)"),
):
    code = cmd_db(db=db)
    raise typer.Exit(code)


def cmd_migrate(db: Optional[Path]) -> int:
    """
    Run in-place schema migrations on the gryt SQLite database.
    """
    db_path = Path(db) if db else (Path.cwd() / GRYT_DIRNAME / DEFAULT_DB_RELATIVE)
    if not db_path.exists():
        typer.echo(json.dumps({"error": f"Database not found: {db_path}"}))
        return 2
    try:
        data = SqliteData(db_path=str(db_path))
        # Explicitly run migrations and gather report
        report = getattr(data, "migrate", None)
        if callable(report):
            res = data.migrate()
            migrations = res.get("migrations", [])
        else:
            # Fallback: initialization already ensured schema
            migrations = []
        data.close()
        typer.echo(json.dumps({"status": "ok", "db": str(db_path), "migrations": migrations}, indent=2))
        return 0
    except Exception as e:  # noqa: BLE001
        typer.echo(json.dumps({"error": str(e)}))
        return 2


@app.command("migrate", help="Run database schema migrations for the gryt SQLite DB")
def migrate_command(
    db: Optional[Path] = typer.Option(None, "--db", help="Path to sqlite db (default ./.gryt/gryt.db)"),
):
    code = cmd_migrate(db=db)
    raise typer.Exit(code)


def cmd_config_set(key: str, value: str) -> int:
    """Set a configuration value"""
    try:
        config = Config()

        # Validate execution_mode
        if key == "execution_mode":
            if value not in ("local", "cloud", "hybrid"):
                typer.echo(f"Error: Invalid execution_mode '{value}'. Must be: local, cloud, or hybrid", err=True)
                return 2

        config.set(key, value)
        config.save()
        typer.echo(f"✓ Set {key} = {value}")
        return 0
    except Exception as e:
        typer.echo(f"Error: {e}", err=True)
        return 2


def cmd_config_get(key: Optional[str]) -> int:
    """Get configuration value(s)"""
    try:
        config = Config()
        if key:
            value = config.get(key)
            if value is None:
                typer.echo(f"{key} = (not set)")
            else:
                typer.echo(f"{key} = {value}")
        else:
            # Show all config
            typer.echo("Configuration:")
            typer.echo(f"  execution_mode: {config.execution_mode}")
            if config.username:
                typer.echo(f"  username: {config.username}")
            if config.api_key_id:
                typer.echo(f"  api_key_id: {config.api_key_id}")
            if config.gryt_url:
                typer.echo(f"  gryt_url: {config.gryt_url}")
        return 0
    except Exception as e:
        typer.echo(f"Error: {e}", err=True)
        return 2


@app.command("config", help="Get or set configuration values")
def config_command(
    key: Optional[str] = typer.Argument(None, help="Configuration key"),
    value: Optional[str] = typer.Argument(None, help="Value to set (omit to get current value)"),
):
    if value:
        code = cmd_config_set(key, value)
    else:
        code = cmd_config_get(key)
    raise typer.Exit(code)


def main(argv: list[str] | None = None) -> int:
    # Preserve a programmatic entry point that returns an int code.
    try:
        # Note: Typer/Click call signature: app(args=None, prog_name=None, ...)
        app(args=argv, prog_name="gryt", standalone_mode=False)
        return 0
    except typer.Exit as e:
        # typer.Exit inherits from click.exceptions.Exit and carries a code
        return int(e.exit_code or 0)
    except SystemExit as e:
        return int(e.code or 0)
    except Exception as e:  # Fallback safety
        if str(e):  # Only print if there's an actual error message
            typer.echo(f"Unexpected error: {e}", err=True)
        return 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
