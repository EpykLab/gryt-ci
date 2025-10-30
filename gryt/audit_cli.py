"""
CLI commands for Audit Trail (v1.0.0)
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer

from .audit import export_audit_trail
from .rollback import RollbackManager
from .hotfix import HotfixWorkflow, create_hotfix
from .data import SqliteData


GRYT_DIRNAME = ".gryt"
DEFAULT_DB_RELATIVE = "gryt.db"

audit_app = typer.Typer(
    name="audit",
    help="Audit trail and compliance tools (v1.0.0)",
    no_args_is_help=True,
)


def _get_db_path() -> Path:
    """Get database path"""
    db_path = Path.cwd() / GRYT_DIRNAME / DEFAULT_DB_RELATIVE
    if not db_path.exists():
        typer.echo(
            f"Error: Database not found at {db_path}. Run 'gryt init' first.",
            err=True,
        )
        raise typer.Exit(2)
    return db_path


def cmd_export(output: str, format: str) -> int:
    """Export complete audit trail"""
    try:
        db_path = _get_db_path()
        output_path = Path(output)

        typer.echo(f"Exporting audit trail to {output_path}...")

        export_audit_trail(db_path, output_path, format)

        typer.echo(f"✓ Audit trail exported successfully")
        typer.echo(f"  Format: {format}")
        typer.echo(f"  Output: {output_path}")

        return 0

    except Exception as e:
        typer.echo(f"Error: {e}", err=True)
        return 2


def cmd_snapshot(label: Optional[str]) -> int:
    """Create database snapshot"""
    try:
        db_path = _get_db_path()
        manager = RollbackManager(db_path)

        typer.echo("Creating snapshot...")
        snapshot_id = manager.create_snapshot(label)

        typer.echo(f"✓ Snapshot created: {snapshot_id}")

        return 0

    except Exception as e:
        typer.echo(f"Error: {e}", err=True)
        return 2


def cmd_list_snapshots() -> int:
    """List all snapshots"""
    try:
        db_path = _get_db_path()
        manager = RollbackManager(db_path)

        snapshots = manager.list_snapshots()

        if not snapshots:
            typer.echo("No snapshots found")
            return 0

        typer.echo(f"\nSnapshots:\n")
        typer.echo(f"{'ID':<40} {'Label':<20} {'Created':<20} {'Size':<15}")
        typer.echo("-" * 100)

        for snapshot in snapshots:
            size_mb = snapshot.get("db_size_bytes", 0) / (1024 * 1024)
            typer.echo(
                f"{snapshot['snapshot_id']:<40} "
                f"{snapshot.get('label') or '—':<20} "
                f"{snapshot.get('created_at', ''):<20} "
                f"{size_mb:.2f} MB"
            )

        return 0

    except Exception as e:
        typer.echo(f"Error: {e}", err=True)
        return 2


def cmd_rollback(snapshot_id: str, no_backup: bool) -> int:
    """Rollback to a snapshot"""
    try:
        db_path = _get_db_path()
        manager = RollbackManager(db_path)

        if not no_backup:
            typer.echo("Creating backup of current state...")

        typer.echo(f"Rolling back to: {snapshot_id}")

        if not typer.confirm("This will replace your current database. Continue?"):
            typer.echo("Rollback cancelled")
            return 1

        manager.rollback_to_snapshot(snapshot_id, backup_current=not no_backup)

        typer.echo(f"✓ Rollback complete")

        return 0

    except Exception as e:
        typer.echo(f"Error: {e}", err=True)
        return 2


def cmd_hotfix(base_version: str, issue_id: str, title: str) -> int:
    """Create a hot-fix generation"""
    try:
        db_path = _get_db_path()

        typer.echo(f"Creating hot-fix for {base_version}...")

        generation = create_hotfix(db_path, base_version, issue_id, title)

        typer.echo(f"✓ Hot-fix generation created: {generation.version}")
        typer.echo(f"  Generation ID: {generation.generation_id}")
        typer.echo(f"  Issue: {issue_id}")

        typer.echo(f"\nNext steps:")
        typer.echo(f"  1. gryt evolution start {generation.version} --change {issue_id}")
        typer.echo(f"  2. Run your pipeline to test the fix")
        typer.echo(f"  3. gryt audit hotfix-promote {generation.version}")

        return 0

    except Exception as e:
        typer.echo(f"Error: {e}", err=True)
        return 2


def cmd_hotfix_promote(version: str) -> int:
    """Promote a hot-fix generation"""
    try:
        db_path = _get_db_path()
        data = SqliteData(db_path=str(db_path))

        try:
            from .generation import Generation

            # Find generation
            rows = data.query("SELECT generation_id FROM generations WHERE version = ?", (version,))
            if not rows:
                typer.echo(f"Error: Generation {version} not found", err=True)
                return 2

            generation = Generation.from_db(data, rows[0]["generation_id"])
            if not generation:
                typer.echo(f"Error: Could not load generation {version}", err=True)
                return 2

            workflow = HotfixWorkflow(data)

            typer.echo(f"Promoting hot-fix: {version}")
            result = workflow.promote_hotfix(generation, auto_tag=True, repo_path=Path.cwd())

            if result["success"]:
                typer.echo(f"✓ Hot-fix promoted successfully")
                return 0
            else:
                typer.echo(f"✗ Promotion failed: {result['message']}", err=True)
                return 2

        finally:
            data.close()

    except Exception as e:
        typer.echo(f"Error: {e}", err=True)
        return 2


# Register commands
@audit_app.command("export", help="Export complete audit trail")
def export_command(
    output: str = typer.Option(..., "--output", "-o", help="Output file path"),
    format: str = typer.Option("json", "--format", "-f", help="Output format (json, csv, html)"),
):
    code = cmd_export(output, format)
    raise typer.Exit(code)


@audit_app.command("snapshot", help="Create database snapshot")
def snapshot_command(
    label: Optional[str] = typer.Option(None, "--label", "-l", help="Optional snapshot label"),
):
    code = cmd_snapshot(label)
    raise typer.Exit(code)


@audit_app.command("list-snapshots", help="List all snapshots")
def list_snapshots_command():
    code = cmd_list_snapshots()
    raise typer.Exit(code)


@audit_app.command("rollback", help="Rollback to a snapshot")
def rollback_command(
    snapshot_id: str = typer.Argument(..., help="Snapshot ID to rollback to"),
    no_backup: bool = typer.Option(False, "--no-backup", help="Don't backup current state"),
):
    code = cmd_rollback(snapshot_id, no_backup)
    raise typer.Exit(code)


@audit_app.command("hotfix", help="Create a hot-fix generation")
def hotfix_command(
    base_version: str = typer.Argument(..., help="Base version to fix (e.g., v1.2.0)"),
    issue_id: str = typer.Option(..., "--issue", "-i", help="Issue/bug ID"),
    title: str = typer.Option(..., "--title", "-t", help="Fix title"),
):
    code = cmd_hotfix(base_version, issue_id, title)
    raise typer.Exit(code)


@audit_app.command("hotfix-promote", help="Promote a hot-fix generation")
def hotfix_promote_command(
    version: str = typer.Argument(..., help="Hot-fix version to promote"),
):
    code = cmd_hotfix_promote(version)
    raise typer.Exit(code)
