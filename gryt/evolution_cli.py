"""
CLI commands for Evolution management (v0.3.0)
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

import typer

from .evolution import Evolution
from .generation import Generation
from .data import SqliteData
from .policy import PolicySet, PolicyViolation
from .hook import PolicyHook


GRYT_DIRNAME = ".gryt"
DEFAULT_DB_RELATIVE = "gryt.db"

evolution_app = typer.Typer(
    name="evolution",
    help="Manage evolutions (point-in-time proofs of changes)",
    no_args_is_help=True,
)


def _get_db() -> SqliteData:
    """Get database connection from .gryt directory"""
    from .paths import get_repo_db_path, ensure_in_repo

    # Ensure we're in a repo
    ensure_in_repo()

    db_path = get_repo_db_path()
    if not db_path or not db_path.exists():
        typer.echo(
            f"Error: Database not found at {db_path}. Run 'gryt init' first.",
            err=True,
        )
        raise typer.Exit(2)
    return SqliteData(db_path=str(db_path))


def cmd_evolution_start(
    version: str,
    change_id: str,
    no_tag: bool = False,
) -> int:
    """Start a new evolution for a generation change"""
    try:
        # Ensure version starts with 'v'
        version = version if version.startswith("v") else f"v{version}"

        data = _get_db()

        # Find generation and change
        gen_rows = data.query("SELECT generation_id FROM generations WHERE version = ?", (version,))
        if not gen_rows:
            typer.echo(f"Error: Generation {version} not found", err=True)
            data.close()
            return 2

        generation_id = gen_rows[0]["generation_id"]

        # Get change details
        change_rows = data.query(
            "SELECT type FROM generation_changes WHERE generation_id = ? AND change_id = ?",
            (generation_id, change_id),
        )
        if not change_rows:
            typer.echo(f"Error: Change {change_id} not found in generation {version}", err=True)
            data.close()
            return 2

        change_type = change_rows[0]["type"]

        # Load and validate policies (v0.5.0)
        from .paths import get_repo_gryt_dir
        repo_gryt_dir = get_repo_gryt_dir()
        policy_path = repo_gryt_dir / "policies.yaml" if repo_gryt_dir else None

        if policy_path and policy_path.exists():
            try:
                policy_set = PolicySet.from_yaml_file(policy_path)
                policy_hook = PolicyHook(policy_set)

                # Validate policies for this evolution
                # Note: pipeline_steps would be passed from Generation if available
                policy_hook.validate_for_evolution(
                    change_type=change_type,
                    change_id=change_id,
                    generation_id=generation_id,
                    data=data,
                    pipeline_steps=None,  # TODO: Load from generation if available
                )
                typer.echo(f"✓ Policy validation passed")
            except PolicyViolation as e:
                typer.echo(f"✗ Policy violation: {e.message}", err=True)
                if e.details:
                    typer.echo(f"  Details: {e.details}")
                data.close()
                return 2

        # Get current user from config
        from .config import Config
        config = Config.load_with_repo_context()
        current_user = config.username or "local"

        # Start evolution (will auto-generate RC tag and create git tag)
        from .paths import find_repo_root
        repo_root = find_repo_root()

        evolution = Evolution.start_evolution(
            data=data,
            version=version,
            change_id=change_id,
            auto_tag=not no_tag,
            repo_path=repo_root or Path.cwd(),
            created_by=current_user,
        )

        data.close()

        typer.echo(f"✓ Started evolution {evolution.tag}")
        typer.echo(f"  Evolution ID: {evolution.evolution_id}")
        typer.echo(f"  Change: {change_id}")
        typer.echo(f"  Status: {evolution.status}")
        if not no_tag:
            typer.echo(f"  Git tag created: {evolution.tag}")

        typer.echo(f"\nNext steps:")
        typer.echo(f"  1. Run your pipeline to prove this change")
        typer.echo(f"  2. Use 'gryt evolution list {version}' to see progress")
        typer.echo(f"  3. When all changes are proven, promote with 'gryt generation promote {version}'")

        return 0

    except ValueError as e:
        typer.echo(f"Error: {e}", err=True)
        return 2
    except Exception as e:
        typer.echo(f"Error: {e}", err=True)
        return 2


def cmd_evolution_list(version: str) -> int:
    """List all evolutions for a generation"""
    try:
        # Ensure version starts with 'v'
        version = version if version.startswith("v") else f"v{version}"

        data = _get_db()

        # Find generation
        gen_rows = data.query("SELECT generation_id FROM generations WHERE version = ?", (version,))
        if not gen_rows:
            typer.echo(f"Error: Generation {version} not found", err=True)
            data.close()
            return 2

        generation_id = gen_rows[0]["generation_id"]

        # Get evolutions
        evolutions = Evolution.list_for_generation(data, generation_id)

        # Get change details for display
        changes_map = {}
        change_rows = data.query(
            "SELECT change_id, type, title FROM generation_changes WHERE generation_id = ?",
            (generation_id,),
        )
        for row in change_rows:
            changes_map[row["change_id"]] = {
                "type": row["type"],
                "title": row["title"],
            }

        data.close()

        if not evolutions:
            typer.echo(f"No evolutions found for generation {version}")
            typer.echo(f"Start one with: gryt evolution start {version} --change <CHANGE-ID>")
            return 0

        typer.echo(f"\nEvolutions for {version}:\n")
        typer.echo(f"{'Tag':<20} {'Change ID':<20} {'Type':<10} {'Status':<12} {'Started':<20}")
        typer.echo("-" * 100)

        for evo in evolutions:
            change_info = changes_map.get(evo.change_id, {})
            change_type = change_info.get("type", "?")
            started = evo.started_at.strftime("%Y-%m-%d %H:%M") if evo.started_at else "?"
            typer.echo(
                f"{evo.tag:<20} {evo.change_id:<20} {change_type:<10} {evo.status:<12} {started:<20}"
            )

        # Summary
        total = len(evolutions)
        passed = sum(1 for e in evolutions if e.status == "pass")
        failed = sum(1 for e in evolutions if e.status == "fail")
        pending = sum(1 for e in evolutions if e.status in ("pending", "running"))

        typer.echo(f"\nSummary: {total} total | {passed} passed | {failed} failed | {pending} pending")

        return 0

    except Exception as e:
        typer.echo(f"Error: {e}", err=True)
        return 2


def cmd_evolution_prove(evolution_id: str, parallel: bool = False, show: bool = False) -> int:
    """Prove an evolution by running its validation pipeline and recording results"""
    try:
        data = _get_db()

        # Load evolution
        evolution_rows = data.query(
            "SELECT evolution_id, generation_id, change_id, status, tag FROM evolutions WHERE evolution_id = ? OR tag = ?",
            (evolution_id, evolution_id),
        )
        if not evolution_rows:
            typer.echo(f"Error: Evolution '{evolution_id}' not found", err=True)
            data.close()
            return 2

        evolution = evolution_rows[0]
        evo_id = evolution["evolution_id"]
        gen_id = evolution["generation_id"]
        change_id = evolution["change_id"]
        evo_tag = evolution["tag"]

        # Load change to get pipeline filename
        change_rows = data.query(
            "SELECT pipeline, title FROM generation_changes WHERE generation_id = ? AND change_id = ?",
            (gen_id, change_id),
        )
        if not change_rows:
            typer.echo(f"Error: Change {change_id} not found", err=True)
            data.close()
            return 2

        pipeline_filename = change_rows[0]["pipeline"]
        change_title = change_rows[0]["title"]

        if not pipeline_filename:
            typer.echo(f"Error: No validation pipeline defined for change {change_id}", err=True)
            typer.echo(f"Run: gryt generation gen-test <version> --change {change_id}", err=True)
            data.close()
            return 2

        typer.echo(f"Proving evolution: {evo_tag}")
        typer.echo(f"  Change: {change_id} - {change_title}")
        typer.echo(f"  Pipeline: {pipeline_filename}")
        typer.echo()

        # Create pipeline record
        pipeline_id = str(uuid.uuid4())
        start_time = datetime.utcnow()

        data.insert(
            "pipelines",
            {
                "pipeline_id": pipeline_id,
                "name": pipeline_filename,
                "start_timestamp": start_time.isoformat(),
                "config_json": json.dumps({"evolution_id": evo_id, "tag": evo_tag}),
            },
        )

        # Update evolution to mark as running
        data.execute(
            "UPDATE evolutions SET status = ?, started_at = ? WHERE evolution_id = ?",
            ("running", start_time.isoformat(), evo_id),
        )
        data.commit()

        # Execute pipeline (reuse logic from cli.py)
        from .cli import _resolve_pipeline_script, _load_module_from_path, _get_pipeline_from_module
        from .paths import get_repo_gryt_dir

        gryt_dir = get_repo_gryt_dir()
        if not gryt_dir:
            typer.echo("Error: Not in a gryt repository", err=True)
            data.close()
            return 2

        try:
            script_path = _resolve_pipeline_script(pipeline_filename, gryt_dir.parent)
            mod = _load_module_from_path(script_path)
            pipeline = _get_pipeline_from_module(mod)

            if pipeline is None:
                typer.echo("Error: Pipeline not found in script", err=True)
                data.close()
                return 2

            # Inject data into pipeline so steps can write to DB
            if pipeline.data is None:
                pipeline.data = data

            typer.echo("Running validation pipeline...\n")
            results = pipeline.execute(parallel=parallel, show=show)

            # Determine success/failure
            exit_code = 0
            pipeline_status = "success"
            evolution_status = "pass"

            # Check environment validation failures
            if results.get("status") == "invalid_env":
                exit_code = 1
                pipeline_status = "error"
                evolution_status = "fail"
            else:
                # Check runner results for failures
                runners = results.get("runners", results)
                for runner_result in runners.values():
                    steps = runner_result.get("steps", {})
                    for step_result in steps.values():
                        if step_result.get("status") == "error":
                            step_rc = step_result.get("returncode")
                            if step_rc is not None and step_rc != 0:
                                exit_code = step_rc
                            else:
                                exit_code = 1
                            pipeline_status = "error"
                            evolution_status = "fail"
                            break
                    if exit_code != 0:
                        break

            # Update pipeline record with completion
            end_time = datetime.utcnow()
            data.execute(
                "UPDATE pipelines SET end_timestamp = ?, status = ? WHERE pipeline_id = ?",
                (end_time.isoformat(), pipeline_status, pipeline_id),
            )

            # Update evolution record with results
            data.execute(
                "UPDATE evolutions SET pipeline_run_id = ?, status = ?, completed_at = ? WHERE evolution_id = ?",
                (pipeline_id, evolution_status, end_time.isoformat(), evo_id),
            )
            data.commit()

            # Display results
            typer.echo()
            if evolution_status == "pass":
                typer.echo(f"✓ Evolution {evo_tag} PASSED")
            else:
                typer.echo(f"✗ Evolution {evo_tag} FAILED")

            typer.echo(f"  Pipeline run ID: {pipeline_id}")
            typer.echo(f"  Duration: {(end_time - start_time).total_seconds():.2f}s")
            typer.echo()
            typer.echo("Detailed results:")
            typer.echo(json.dumps({"status": "ok" if exit_code == 0 else "error", "results": results}, indent=2))

            data.close()
            return exit_code

        except Exception as e:
            # Update pipeline and evolution as failed
            end_time = datetime.utcnow()
            data.execute(
                "UPDATE pipelines SET end_timestamp = ?, status = ? WHERE pipeline_id = ?",
                (end_time.isoformat(), "error", pipeline_id),
            )
            data.execute(
                "UPDATE evolutions SET pipeline_run_id = ?, status = ?, completed_at = ? WHERE evolution_id = ?",
                (pipeline_id, "fail", end_time.isoformat(), evo_id),
            )
            data.commit()
            data.close()
            raise

    except Exception as e:
        typer.echo(f"Error: {e}", err=True)
        return 2


# Register commands
@evolution_app.command("start", help="Start a new evolution for a generation change")
def start_command(
    version: str = typer.Argument(..., help="Generation version (e.g., v2.2.0 or 2.2.0)"),
    change: str = typer.Option(..., "--change", "-c", help="Change ID to prove (e.g., PAY-001)"),
    no_tag: bool = typer.Option(False, "--no-tag", help="Don't create git tag"),
):
    code = cmd_evolution_start(version, change, no_tag)
    raise typer.Exit(code)


@evolution_app.command("list", help="List all evolutions for a generation")
def list_command(
    version: str = typer.Argument(..., help="Generation version (e.g., v2.2.0)"),
):
    code = cmd_evolution_list(version)
    raise typer.Exit(code)


@evolution_app.command("prove", help="Prove an evolution by running its validation pipeline")
def prove_command(
    evolution_id: str = typer.Argument(..., help="Evolution ID or tag (e.g., v2.2.0-rc.1)"),
    parallel: bool = typer.Option(False, "--parallel", "-p", help="Run pipeline runners in parallel"),
    show: bool = typer.Option(False, "--show", "-s", help="Show pipeline output in real-time"),
):
    code = cmd_evolution_prove(evolution_id, parallel, show)
    raise typer.Exit(code)
