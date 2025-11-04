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


def cmd_evolution_prove(evolution_id: str, pipeline_filter: Optional[str] = None, parallel: bool = False, show: bool = False) -> int:
    """Prove an evolution by running its validation pipeline(s) and recording results"""
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

        # Load change details
        change_rows = data.query(
            "SELECT pipeline, title FROM generation_changes WHERE generation_id = ? AND change_id = ?",
            (gen_id, change_id),
        )
        if not change_rows:
            typer.echo(f"Error: Change {change_id} not found", err=True)
            data.close()
            return 2

        change_title = change_rows[0]["title"]

        # Get all linked pipelines for this change
        pipeline_links = data.query(
            "SELECT pipeline_name, is_primary FROM change_pipelines WHERE change_id = ? AND generation_id = ? ORDER BY is_primary DESC, pipeline_name",
            (change_id, gen_id),
        )

        if not pipeline_links:
            typer.echo(f"Error: No validation pipelines linked to change {change_id}", err=True)
            typer.echo(f"Run: gryt generation gen-test <version> --change {change_id}", err=True)
            data.close()
            return 2

        # Filter pipelines if requested
        if pipeline_filter:
            pipeline_links = [p for p in pipeline_links if p["pipeline_name"] == pipeline_filter]
            if not pipeline_links:
                typer.echo(f"Error: Pipeline '{pipeline_filter}' is not linked to change {change_id}", err=True)
                data.close()
                return 2

        typer.echo(f"Proving evolution: {evo_tag}")
        typer.echo(f"  Change: {change_id} - {change_title}")
        typer.echo(f"  Pipelines to run: {len(pipeline_links)}")
        for link in pipeline_links:
            primary_marker = " (primary)" if link["is_primary"] else ""
            typer.echo(f"    - {link['pipeline_name']}{primary_marker}")
        typer.echo()

        # Update evolution to mark as running
        start_time = datetime.utcnow()
        data.execute(
            "UPDATE evolutions SET status = ?, started_at = ? WHERE evolution_id = ?",
            ("running", start_time.isoformat(), evo_id),
        )
        data.commit()

        # Execute all pipelines
        from .cli import _resolve_pipeline_script, _load_module_from_path, _get_pipeline_from_module
        from .paths import get_repo_gryt_dir

        gryt_dir = get_repo_gryt_dir()
        if not gryt_dir:
            typer.echo("Error: Not in a gryt repository", err=True)
            data.close()
            return 2

        all_pipeline_runs = []
        overall_exit_code = 0
        overall_status = "pass"

        try:
            for idx, link in enumerate(pipeline_links, 1):
                pipeline_filename = link["pipeline_name"]
                typer.echo(f"[{idx}/{len(pipeline_links)}] Running {pipeline_filename}...")

                # Create pipeline record
                pipeline_id = str(uuid.uuid4())
                pipeline_start = datetime.utcnow()

                data.insert(
                    "pipelines",
                    {
                        "pipeline_id": pipeline_id,
                        "name": pipeline_filename,
                        "start_timestamp": pipeline_start.isoformat(),
                        "config_json": json.dumps({"evolution_id": evo_id, "tag": evo_tag, "sequence": idx}),
                    },
                )
                data.commit()

                # Load and execute pipeline
                script_path = _resolve_pipeline_script(pipeline_filename, gryt_dir.parent)
                mod = _load_module_from_path(script_path)
                pipeline = _get_pipeline_from_module(mod)

                if pipeline is None:
                    typer.echo(f"Error: Pipeline not found in {pipeline_filename}", err=True)
                    data.execute(
                        "UPDATE pipelines SET end_timestamp = ?, status = ? WHERE pipeline_id = ?",
                        (datetime.utcnow().isoformat(), "error", pipeline_id),
                    )
                    data.commit()
                    overall_exit_code = 2
                    overall_status = "fail"
                    continue

                # Inject data into pipeline so steps can write to DB
                if pipeline.data is None:
                    pipeline.data = data

                results = pipeline.execute(parallel=parallel, show=show)

                # Determine success/failure for this pipeline
                pipeline_exit_code = 0
                pipeline_status = "success"

                # Check environment validation failures
                if results.get("status") == "invalid_env":
                    pipeline_exit_code = 1
                    pipeline_status = "error"
                else:
                    # Check runner results for failures
                    runners = results.get("runners", results)
                    for runner_result in runners.values():
                        steps = runner_result.get("steps", {})
                        for step_result in steps.values():
                            if step_result.get("status") == "error":
                                step_rc = step_result.get("returncode")
                                if step_rc is not None and step_rc != 0:
                                    pipeline_exit_code = step_rc
                                else:
                                    pipeline_exit_code = 1
                                pipeline_status = "error"
                                break
                        if pipeline_exit_code != 0:
                            break

                # Update pipeline record with completion
                pipeline_end = datetime.utcnow()
                data.execute(
                    "UPDATE pipelines SET end_timestamp = ?, status = ? WHERE pipeline_id = ?",
                    (pipeline_end.isoformat(), pipeline_status, pipeline_id),
                )
                data.commit()

                # Track results
                all_pipeline_runs.append({
                    "pipeline_id": pipeline_id,
                    "name": pipeline_filename,
                    "status": pipeline_status,
                    "exit_code": pipeline_exit_code,
                    "duration": (pipeline_end - pipeline_start).total_seconds(),
                    "results": results,
                })

                # Update overall status
                if pipeline_exit_code != 0:
                    overall_exit_code = pipeline_exit_code
                    overall_status = "fail"

                # Display individual result
                if pipeline_status == "success":
                    typer.echo(f"  ✓ {pipeline_filename} PASSED ({(pipeline_end - pipeline_start).total_seconds():.2f}s)")
                else:
                    typer.echo(f"  ✗ {pipeline_filename} FAILED ({(pipeline_end - pipeline_start).total_seconds():.2f}s)")

                typer.echo()

            # Update evolution record with results
            # Note: pipeline_run_id will store the last (or primary) pipeline run ID
            primary_pipeline_id = all_pipeline_runs[0]["pipeline_id"] if all_pipeline_runs else None
            end_time = datetime.utcnow()
            data.execute(
                "UPDATE evolutions SET pipeline_run_id = ?, status = ?, completed_at = ? WHERE evolution_id = ?",
                (primary_pipeline_id, overall_status, end_time.isoformat(), evo_id),
            )
            data.commit()

            # Display overall results
            typer.echo("=" * 60)
            if overall_status == "pass":
                typer.echo(f"✓ Evolution {evo_tag} PASSED")
            else:
                typer.echo(f"✗ Evolution {evo_tag} FAILED")

            typer.echo(f"  Total duration: {(end_time - start_time).total_seconds():.2f}s")
            typer.echo(f"  Pipelines run: {len(all_pipeline_runs)}")
            passed = sum(1 for r in all_pipeline_runs if r["status"] == "success")
            failed = len(all_pipeline_runs) - passed
            typer.echo(f"  Results: {passed} passed, {failed} failed")
            typer.echo()
            typer.echo("Detailed results:")
            typer.echo(json.dumps({
                "status": "ok" if overall_exit_code == 0 else "error",
                "overall_exit_code": overall_exit_code,
                "pipelines": all_pipeline_runs,
            }, indent=2))

            data.close()
            return overall_exit_code

        except Exception as e:
            # Update evolution as failed
            end_time = datetime.utcnow()
            data.execute(
                "UPDATE evolutions SET status = ?, completed_at = ? WHERE evolution_id = ?",
                ("fail", end_time.isoformat(), evo_id),
            )
            data.commit()
            data.close()
            raise

    except Exception as e:
        typer.echo(f"Error: {e}", err=True)
        return 2


def cmd_evolution_link_pipeline(
    change_id: str,
    generation: str,
    pipeline: str,
    primary: bool = False,
) -> int:
    """Link a pipeline to a change for validation"""
    try:
        # Ensure version starts with 'v'
        version = generation if generation.startswith("v") else f"v{generation}"

        data = _get_db()

        # Find generation
        gen_rows = data.query("SELECT generation_id FROM generations WHERE version = ?", (version,))
        if not gen_rows:
            typer.echo(f"Error: Generation {version} not found", err=True)
            data.close()
            return 2

        generation_id = gen_rows[0]["generation_id"]

        # Verify change exists
        change_rows = data.query(
            "SELECT change_id, title FROM generation_changes WHERE generation_id = ? AND change_id = ?",
            (generation_id, change_id),
        )
        if not change_rows:
            typer.echo(f"Error: Change {change_id} not found in generation {version}", err=True)
            data.close()
            return 2

        change_title = change_rows[0]["title"]

        # Verify pipeline file exists
        from .paths import get_repo_gryt_dir
        gryt_dir = get_repo_gryt_dir()
        if not gryt_dir:
            typer.echo("Error: Not in a gryt repository", err=True)
            data.close()
            return 2

        pipeline_path = gryt_dir / "pipelines" / pipeline
        if not pipeline_path.exists():
            typer.echo(f"Error: Pipeline file not found: {pipeline}", err=True)
            typer.echo(f"  Expected location: {pipeline_path}", err=True)
            data.close()
            return 2

        # Get current user
        from .config import Config
        config = Config.load_with_repo_context()
        current_user = config.username or "local"

        # Check if already linked
        existing_link = data.query(
            "SELECT id FROM change_pipelines WHERE change_id = ? AND generation_id = ? AND pipeline_name = ?",
            (change_id, generation_id, pipeline),
        )
        if existing_link:
            typer.echo(f"✓ Pipeline '{pipeline}' is already linked to {change_id}", err=True)
            data.close()
            return 0

        # If marking as primary, unmark other pipelines
        if primary:
            data.execute(
                "UPDATE change_pipelines SET is_primary = 0 WHERE change_id = ? AND generation_id = ?",
                (change_id, generation_id),
            )
            data.commit()

        # Link the pipeline
        data.insert(
            "change_pipelines",
            {
                "change_id": change_id,
                "generation_id": generation_id,
                "pipeline_name": pipeline,
                "is_primary": 1 if primary else 0,
                "created_at": datetime.utcnow().isoformat(),
                "created_by": current_user,
            },
        )

        data.close()

        typer.echo(f"✓ Linked pipeline '{pipeline}' to change {change_id}")
        typer.echo(f"  Change: {change_title}")
        typer.echo(f"  Generation: {version}")
        if primary:
            typer.echo(f"  Marked as primary validation pipeline")

        return 0

    except Exception as e:
        typer.echo(f"Error: {e}", err=True)
        return 2


def cmd_evolution_unlink_pipeline(
    change_id: str,
    generation: str,
    pipeline: str,
) -> int:
    """Unlink a pipeline from a change"""
    try:
        # Ensure version starts with 'v'
        version = generation if generation.startswith("v") else f"v{generation}"

        data = _get_db()

        # Find generation
        gen_rows = data.query("SELECT generation_id FROM generations WHERE version = ?", (version,))
        if not gen_rows:
            typer.echo(f"Error: Generation {version} not found", err=True)
            data.close()
            return 2

        generation_id = gen_rows[0]["generation_id"]

        # Check if link exists
        existing_link = data.query(
            "SELECT id, is_primary FROM change_pipelines WHERE change_id = ? AND generation_id = ? AND pipeline_name = ?",
            (change_id, generation_id, pipeline),
        )
        if not existing_link:
            typer.echo(f"Error: Pipeline '{pipeline}' is not linked to change {change_id}", err=True)
            data.close()
            return 2

        was_primary = existing_link[0]["is_primary"]

        # Delete the link
        data.execute(
            "DELETE FROM change_pipelines WHERE change_id = ? AND generation_id = ? AND pipeline_name = ?",
            (change_id, generation_id, pipeline),
        )
        data.commit()
        data.close()

        typer.echo(f"✓ Unlinked pipeline '{pipeline}' from change {change_id}")
        if was_primary:
            typer.echo(f"  Warning: This was the primary validation pipeline")

        return 0

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


@evolution_app.command("prove", help="Prove an evolution by running its validation pipeline(s)")
def prove_command(
    evolution_id: str = typer.Argument(..., help="Evolution ID or tag (e.g., v2.2.0-rc.1)"),
    pipeline: Optional[str] = typer.Option(None, "--pipeline", help="Run only this specific pipeline (default: run all linked pipelines)"),
    parallel: bool = typer.Option(False, "--parallel", help="Run pipeline runners in parallel"),
    show: bool = typer.Option(False, "--show", "-s", help="Show pipeline output in real-time"),
):
    code = cmd_evolution_prove(evolution_id, pipeline, parallel, show)
    raise typer.Exit(code)


@evolution_app.command("link-pipeline", help="Link an additional pipeline to a change for validation")
def link_pipeline_command(
    change: str = typer.Option(..., "--change", "-c", help="Change ID (e.g., PAY-001)"),
    generation: str = typer.Option(..., "--generation", "-g", help="Generation version (e.g., v2.2.0)"),
    pipeline: str = typer.Option(..., "--pipeline", "-p", help="Pipeline filename (e.g., integration_tests.py)"),
    primary: bool = typer.Option(False, "--primary", help="Mark this as the primary validation pipeline"),
):
    code = cmd_evolution_link_pipeline(change, generation, pipeline, primary)
    raise typer.Exit(code)


@evolution_app.command("unlink-pipeline", help="Unlink a pipeline from a change")
def unlink_pipeline_command(
    change: str = typer.Option(..., "--change", "-c", help="Change ID (e.g., PAY-001)"),
    generation: str = typer.Option(..., "--generation", "-g", help="Generation version (e.g., v2.2.0)"),
    pipeline: str = typer.Option(..., "--pipeline", "-p", help="Pipeline filename to unlink"),
):
    code = cmd_evolution_unlink_pipeline(change, generation, pipeline)
    raise typer.Exit(code)
