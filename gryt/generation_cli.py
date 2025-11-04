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
from .pipeline_templates import generate_pipeline_template, sanitize_change_id


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


def _get_generations_dir() -> Path:
    """Get or create .gryt/generations directory"""
    from .paths import get_repo_gryt_dir, ensure_in_repo

    # Ensure we're in a repo
    ensure_in_repo()

    repo_gryt_dir = get_repo_gryt_dir()
    if not repo_gryt_dir:
        typer.echo(
            f"Error: Not in a gryt repository. Run 'gryt init' first.",
            err=True,
        )
        raise typer.Exit(2)

    gen_dir = repo_gryt_dir / GENERATIONS_SUBDIR
    gen_dir.mkdir(parents=True, exist_ok=True)
    return gen_dir


def cmd_generation_new(
    version: str,
    description: Optional[str] = None,
    pipeline_template: Optional[str] = None,
    team: Optional[str] = None,
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

        # Get current user from config
        from .config import Config
        config = Config.load_with_repo_context()
        current_user = config.username or "local"

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
            created_by=current_user,
            team_id=team,
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
        typer.echo(f"Then run 'gryt generation update {version}' to sync changes to database.")
        return 0

    except Exception as e:
        typer.echo(f"Error: {e}", err=True)
        return 2


def cmd_generation_update(version: str) -> int:
    """Update generation in database from YAML file"""
    try:
        # Ensure version starts with 'v'
        version = version if version.startswith("v") else f"v{version}"

        # Get database
        data = _get_db()

        # Check if version exists
        existing = data.query("SELECT generation_id FROM generations WHERE version = ?", (version,))
        if not existing:
            typer.echo(f"Error: Generation {version} not found in database", err=True)
            typer.echo(f"Create it first with 'gryt generation new {version}'")
            data.close()
            return 2

        generation_id = existing[0]["generation_id"]

        # Find YAML file
        gen_dir = _get_generations_dir()
        yaml_path = gen_dir / f"{version}.yaml"

        if not yaml_path.exists():
            typer.echo(f"Error: YAML file not found at {yaml_path}", err=True)
            data.close()
            return 2

        # Load generation from YAML
        typer.echo(f"Reading changes from {yaml_path.relative_to(Path.cwd())}...")
        updated_gen = Generation.from_yaml_file(yaml_path)

        # Preserve the original generation_id
        updated_gen.generation_id = generation_id

        # Update database
        # First, delete existing changes for this generation
        data.conn.execute(
            "DELETE FROM generation_changes WHERE generation_id = ?",
            (generation_id,)
        )
        data.conn.commit()

        # Update generation record and mark as modified (needs sync)
        data.update(
            "generations",
            {
                "description": updated_gen.description,
                "pipeline_template": updated_gen.pipeline_template,
                "sync_status": "not_synced",  # Mark as needing sync
            },
            "generation_id = ?",
            (generation_id,)
        )

        # Insert updated changes
        for change in updated_gen.changes:
            data.insert(
                "generation_changes",
                {
                    "generation_id": generation_id,
                    "change_id": change.change_id,
                    "type": change.type,
                    "title": change.title,
                    "description": change.description,
                    "status": change.status,
                    "pipeline": change.pipeline,
                }
            )

        data.close()

        typer.echo(f"✓ Updated generation {version} from YAML")
        typer.echo(f"  Changes: {len(updated_gen.changes)}")
        for change in updated_gen.changes:
            typer.echo(f"    • [{change.type}] {change.change_id}: {change.title}")

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
        typer.echo(f"{'Version':<15} {'Status':<12} {'Changes':<10} {'Sync':<15} {'Team':<20} {'Description':<30}")
        typer.echo("-" * 110)

        for gen in generations:
            changes_count = len(gen.changes)
            desc = (gen.description or "")[:27] + "..." if gen.description and len(gen.description) > 30 else (gen.description or "")
            team_display = (gen.team_id[:17] + "...") if gen.team_id and len(gen.team_id) > 20 else (gen.team_id or "-")
            typer.echo(
                f"{gen.version:<15} {gen.status:<12} {changes_count:<10} {gen.sync_status:<15} {team_display:<20} {desc:<30}"
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


def cmd_generation_gen_test(
    version: str,
    change_id: Optional[str] = None,
    all_changes: bool = False,
    force: bool = False,
) -> int:
    """Generate test pipeline files for changes in a generation"""
    try:
        # Ensure version starts with 'v'
        version = version if version.startswith("v") else f"v{version}"

        # Validate arguments
        if not change_id and not all_changes:
            typer.echo("Error: Must specify either --change or --all", err=True)
            return 2

        if change_id and all_changes:
            typer.echo("Error: Cannot specify both --change and --all", err=True)
            return 2

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

        # Get pipelines directory
        from .paths import get_repo_gryt_dir, ensure_in_repo
        ensure_in_repo()
        gryt_dir = get_repo_gryt_dir()
        if not gryt_dir:
            typer.echo("Error: Not in a gryt repository", err=True)
            data.close()
            return 2

        pipelines_dir = gryt_dir / "pipelines"
        pipelines_dir.mkdir(parents=True, exist_ok=True)

        # Determine which changes to process
        changes_to_process = []
        if all_changes:
            changes_to_process = generation.changes
        else:
            # Find specific change
            matching_changes = [c for c in generation.changes if c.change_id == change_id]
            if not matching_changes:
                typer.echo(f"Error: Change {change_id} not found in generation {version}", err=True)
                data.close()
                return 2
            changes_to_process = matching_changes

        # Generate pipeline files
        generated_files = []
        sanitized_version = version.replace(".", "_").replace("-", "_")  # v2.2.0 -> v2_2_0

        for change in changes_to_process:
            # Check if pipeline already exists
            is_regenerating = bool(change.pipeline)
            if change.pipeline and not force:
                typer.echo(f"⚠ Change {change.change_id} already has pipeline: {change.pipeline}")
                continue

            # Generate pipeline filename with version prefix
            sanitized_id = sanitize_change_id(change.change_id)
            pipeline_filename = f"{sanitized_version}_{sanitized_id}_VALIDATION_PIPELINE.py"
            pipeline_path = pipelines_dir / pipeline_filename

            # Generate pipeline content
            pipeline_content = generate_pipeline_template(
                change.change_id,
                change.type,
                change.title,
                change.description,
            )

            # Write pipeline file
            with open(pipeline_path, "w") as f:
                f.write(pipeline_content)

            # Update change in database with pipeline link
            data.update(
                "generation_changes",
                {"pipeline": pipeline_filename},
                "change_id = ?",
                (change.change_id,),
            )

            # Link pipeline in change_pipelines table (v1.0.10)
            from .config import Config
            from datetime import datetime
            config = Config.load_with_repo_context()
            current_user = config.username or "local"

            # Check if this pipeline is already linked
            existing_link = data.query(
                "SELECT id FROM change_pipelines WHERE change_id = ? AND generation_id = ? AND pipeline_name = ?",
                (change.change_id, generation.generation_id, pipeline_filename),
            )
            if not existing_link:
                data.insert(
                    "change_pipelines",
                    {
                        "change_id": change.change_id,
                        "generation_id": generation.generation_id,
                        "pipeline_name": pipeline_filename,
                        "is_primary": 1,  # Generated pipelines are primary
                        "created_at": datetime.utcnow().isoformat(),
                        "created_by": current_user,
                    },
                )

            # Update in-memory change object
            change.pipeline = pipeline_filename

            generated_files.append((change.change_id, pipeline_filename))
            action = "Regenerated" if is_regenerating else "Generated"
            typer.echo(f"✓ {action} {pipeline_filename} for {change.change_id}")

        data.close()

        if not generated_files:
            typer.echo("No new pipeline files generated")
            return 0

        typer.echo(f"\n✓ Generated {len(generated_files)} validation pipeline(s)")
        typer.echo(f"  Location: {pipelines_dir.relative_to(Path.cwd())}/")
        typer.echo("\nNext steps:")
        typer.echo("1. Review and customize the generated pipeline files")
        typer.echo("2. Implement the test cases")
        typer.echo(f"3. Run 'gryt evolution start {version} --change <id>' to validate changes")

        return 0

    except Exception as e:
        typer.echo(f"Error: {e}", err=True)
        import traceback
        traceback.print_exc()
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
    team: Optional[str] = typer.Option(None, "--team", "-t", help="Team ID (for team-based generations)"),
):
    code = cmd_generation_new(version, description, pipeline_template, team)
    raise typer.Exit(code)


@generation_app.command("update", help="Update generation in database from edited YAML file")
def update_command(
    version: str = typer.Argument(..., help="Version to update (e.g., v2.2.0)"),
):
    code = cmd_generation_update(version)
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


@generation_app.command("gen-test", help="Generate validation pipeline files for changes")
def gen_test_command(
    version: str = typer.Argument(..., help="Version (e.g., v2.2.0)"),
    change: Optional[str] = typer.Option(None, "--change", "-c", help="Generate for specific change ID"),
    all_changes: bool = typer.Option(False, "--all", "-a", help="Generate for all changes"),
    force: bool = typer.Option(False, "--force", "-f", help="Regenerate pipeline files even if they already exist"),
):
    code = cmd_generation_gen_test(version, change, all_changes, force)
    raise typer.Exit(code)
