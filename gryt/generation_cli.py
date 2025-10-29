"""
CLI commands for Generation contract management (v0.2.0)
"""
from __future__ import annotations

import json
import sys
import uuid
from pathlib import Path
from typing import Optional

import typer
import yaml

from .generation import Generation, GenerationChange
from .data import SqliteData


GRYT_DIRNAME = ".gryt"
GENERATIONS_SUBDIR = "generations"
DEFAULT_DB_RELATIVE = "gryt.db"

generation_app = typer.Typer(
    name="generation",
    help="Manage generation contracts (release definitions)",
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


def _get_generations_dir() -> Path:
    """Get or create .gryt/generations directory"""
    gen_dir = Path.cwd() / GRYT_DIRNAME / GENERATIONS_SUBDIR
    gen_dir.mkdir(parents=True, exist_ok=True)
    return gen_dir


def cmd_generation_new(
    version: str,
    description: Optional[str] = None,
    pipeline_template: Optional[str] = None,
) -> int:
    """Create a new generation contract"""
    try:
        # Ensure version starts with 'v'
        version = version if version.startswith("v") else f"v{version}"

        # Get database
        data = _get_db()

        # Check if version already exists
        existing = data.query("SELECT version FROM generations WHERE version = ?", (version,))
        if existing:
            typer.echo(f"Error: Generation {version} already exists", err=True)
            data.close()
            return 2

        # Create generation with placeholder change
        changes = [
            GenerationChange(
                change_id=f"CHANGE-{str(uuid.uuid4())[:8].upper()}",
                change_type="add",
                title="Placeholder change - edit YAML to customize",
            )
        ]

        generation = Generation(
            version=version,
            description=description or f"Release {version}",
            changes=changes,
            pipeline_template=pipeline_template,
        )

        # Save to database
        generation.save_to_db(data)

        # Save to YAML file
        gen_dir = _get_generations_dir()
        yaml_path = generation.save_to_yaml(gen_dir)

        data.close()

        typer.echo(f"✓ Created generation {version}")
        typer.echo(f"  Database: .gryt/gryt.db")
        typer.echo(f"  YAML: {yaml_path.relative_to(Path.cwd())}")
        typer.echo(f"\nEdit {yaml_path.relative_to(Path.cwd())} to define changes.")
        return 0

    except Exception as e:
        typer.echo(f"Error: {e}", err=True)
        return 2


def cmd_generation_list() -> int:
    """List all generations"""
    try:
        data = _get_db()
        generations = Generation.list_all(data)
        data.close()

        if not generations:
            typer.echo("No generations found. Create one with 'gryt generation new <version>'")
            return 0

        typer.echo("Generations:\n")
        typer.echo(f"{'Version':<15} {'Status':<12} {'Changes':<10} {'Sync':<15} {'Description':<40}")
        typer.echo("-" * 100)

        for gen in generations:
            changes_count = len(gen.changes)
            desc = (gen.description or "")[:37] + "..." if gen.description and len(gen.description) > 40 else (gen.description or "")
            typer.echo(
                f"{gen.version:<15} {gen.status:<12} {changes_count:<10} {gen.sync_status:<15} {desc:<40}"
            )

        return 0

    except Exception as e:
        typer.echo(f"Error: {e}", err=True)
        return 2


def cmd_generation_show(version: str) -> int:
    """Show detailed information about a generation"""
    try:
        # Ensure version starts with 'v'
        version = version if version.startswith("v") else f"v{version}"

        data = _get_db()

        # Find generation by version
        rows = data.query("SELECT generation_id FROM generations WHERE version = ?", (version,))
        if not rows:
            typer.echo(f"Error: Generation {version} not found", err=True)
            data.close()
            return 2

        generation = Generation.from_db(data, rows[0]["generation_id"])
        data.close()

        if not generation:
            typer.echo(f"Error: Generation {version} not found", err=True)
            return 2

        # Display generation details
        typer.echo(f"\nGeneration: {generation.version}")
        typer.echo(f"Status: {generation.status}")
        typer.echo(f"Description: {generation.description or '(none)'}")
        typer.echo(f"Pipeline Template: {generation.pipeline_template or '(none)'}")
        typer.echo(f"Sync Status: {generation.sync_status}")
        if generation.remote_id:
            typer.echo(f"Remote ID: {generation.remote_id}")
        typer.echo(f"Created: {generation.created_at}")
        if generation.promoted_at:
            typer.echo(f"Promoted: {generation.promoted_at}")

        typer.echo(f"\nChanges ({len(generation.changes)}):")
        typer.echo(f"{'ID':<20} {'Type':<10} {'Status':<12} {'Title':<50}")
        typer.echo("-" * 100)

        for change in generation.changes:
            title = change.title[:47] + "..." if len(change.title) > 50 else change.title
            typer.echo(f"{change.change_id:<20} {change.type:<10} {change.status:<12} {title:<50}")

        return 0

    except Exception as e:
        typer.echo(f"Error: {e}", err=True)
        return 2


def cmd_generation_promote(version: str, no_tag: bool = False) -> int:
    """Promote a generation to production"""
    try:
        # Ensure version starts with 'v'
        version = version if version.startswith("v") else f"v{version}"

        data = _get_db()

        # Find generation by version
        rows = data.query("SELECT generation_id FROM generations WHERE version = ?", (version,))
        if not rows:
            typer.echo(f"Error: Generation {version} not found", err=True)
            data.close()
            return 2

        generation = Generation.from_db(data, rows[0]["generation_id"])
        if not generation:
            typer.echo(f"Error: Generation {version} not found", err=True)
            data.close()
            return 2

        # Check if already promoted
        if generation.status == "promoted":
            typer.echo(f"Error: Generation {version} is already promoted", err=True)
            data.close()
            return 2

        typer.echo(f"Promoting generation {version}...")
        typer.echo(f"Running promotion gates...\n")

        # Run promotion
        result = generation.promote(data, auto_tag=not no_tag, repo_path=Path.cwd())

        data.close()

        # Display gate results
        for gate_result in result["gate_results"]:
            status_symbol = "✓" if gate_result["passed"] else "✗"
            typer.echo(f"{status_symbol} {gate_result['gate']}: {gate_result['message']}")

        typer.echo()

        if not result["success"]:
            typer.echo(f"✗ Promotion failed: {result['message']}", err=True)
            typer.echo("\nTo promote, ensure all changes have at least one PASS evolution.")
            typer.echo(f"Use 'gryt evolution list {version}' to see evolution status.")
            return 2

        typer.echo(f"✓ {result['message']}")
        if result.get("tag_created"):
            typer.echo(f"✓ Git tag created: {result['tag']}")
        elif not no_tag:
            typer.echo(f"⚠ Git tag creation failed (you may need to create it manually)")

        typer.echo(f"\nGeneration {version} is now deployable!")

        return 0

    except Exception as e:
        typer.echo(f"Error: {e}", err=True)
        return 2


# Register commands
@generation_app.command("new", help="Create a new generation contract")
def new_command(
    version: str = typer.Argument(..., help="Version (e.g., v2.2.0 or 2.2.0)"),
    description: Optional[str] = typer.Option(None, "--description", "-d", help="Description of the generation"),
    pipeline_template: Optional[str] = typer.Option(None, "--pipeline", "-p", help="Pipeline template to use"),
):
    code = cmd_generation_new(version, description, pipeline_template)
    raise typer.Exit(code)


@generation_app.command("list", help="List all generations")
def list_command():
    code = cmd_generation_list()
    raise typer.Exit(code)


@generation_app.command("show", help="Show detailed information about a generation")
def show_command(
    version: str = typer.Argument(..., help="Version to show (e.g., v2.2.0)"),
):
    code = cmd_generation_show(version)
    raise typer.Exit(code)


@generation_app.command("promote", help="Promote a generation to production")
def promote_command(
    version: str = typer.Argument(..., help="Version to promote (e.g., v2.2.0)"),
    no_tag: bool = typer.Option(False, "--no-tag", help="Don't create git tag"),
):
    code = cmd_generation_promote(version, no_tag)
    raise typer.Exit(code)
