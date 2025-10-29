"""
CLI commands for Evolution management (v0.3.0)
"""
from __future__ import annotations

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
    db_path = Path.cwd() / GRYT_DIRNAME / DEFAULT_DB_RELATIVE
    if not db_path.exists():
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
        policy_path = Path.cwd() / GRYT_DIRNAME / "policies.yaml"
        if policy_path.exists():
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

        # Start evolution (will auto-generate RC tag and create git tag)
        evolution = Evolution.start_evolution(
            data=data,
            version=version,
            change_id=change_id,
            auto_tag=not no_tag,
            repo_path=Path.cwd(),
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
