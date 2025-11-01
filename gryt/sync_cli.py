"""Sync CLI commands for bidirectional sync with cloud."""
from __future__ import annotations

from typing import Optional
import typer
from rich.console import Console
from rich.table import Table

from .sync import CloudSync
from .config import Config
from .cloud_client import GrytCloudClient


sync_app = typer.Typer(name="sync", help="Bidirectional sync with Gryt Cloud")
console = Console()


def _get_sync_client() -> CloudSync:
    """Get configured CloudSync client."""
    from .paths import get_repo_db_path, ensure_in_repo
    from .data import SqliteData

    # Ensure we're in a repo
    ensure_in_repo()

    # Get database
    db_path = get_repo_db_path()
    if not db_path or not db_path.exists():
        raise RuntimeError(f"Database not found at {db_path}. Run 'gryt init' first.")

    data = SqliteData(db_path=str(db_path))

    # Get cloud client
    config = Config.load_with_repo_context()
    client = GrytCloudClient(
        username=config.username,
        password=config.password,
        gryt_url=config.gryt_url,
        api_key_id=config.api_key_id,
        api_key_secret=config.api_key_secret,
    )

    return CloudSync(data=data, client=client)


@sync_app.command("pull")
def pull_command(
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show detailed output"),
) -> None:
    """Pull cloud changes to local database.

    Fetches all generations and evolutions from cloud and updates local database.
    Safe operation - will not overwrite local-only work.
    """
    import logging
    import os

    # Configure logging if verbose or GRYT_LOG_LEVEL is set
    log_level = os.getenv("GRYT_LOG_LEVEL", "WARNING" if not verbose else "INFO")
    logging.basicConfig(
        level=getattr(logging, log_level.upper(), logging.WARNING),
        format='%(name)s: %(message)s'
    )

    try:
        sync = _get_sync_client()
        result = sync.pull()

        console.print(f"[green]Pull complete[/green]")
        console.print(f"  New generations: {result['new']}")
        console.print(f"  Updated generations: {result['updated']}")

        if result["conflicts"]:
            console.print(f"\n[yellow]Conflicts detected:[/yellow] {len(result['conflicts'])}")
            for conflict in result["conflicts"]:
                console.print(f"  [yellow]•[/yellow] {conflict['version']}: {conflict['reason']}")
                console.print(f"    Resolution: {conflict['resolution']}")

        if verbose and result["details"]:
            console.print("\n[dim]Details:[/dim]")
            for detail in result["details"]:
                console.print(f"  [dim]•[/dim] {detail}")

    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)


@sync_app.command("push")
def push_command(
    version: Optional[str] = typer.Option(None, "--version", "-v", help="Push specific version"),
    evolutions: bool = typer.Option(False, "--evolutions", "-e", help="Push completed evolutions"),
    force: bool = typer.Option(False, "--force", "-f", help="Force push even if already synced"),
    verbose: bool = typer.Option(False, "--verbose", help="Show detailed output"),
) -> None:
    """Push local changes to cloud.

    Pushes pending generations to cloud. Use --evolutions to also push completed evolutions.
    Use --force to push even if sync_status is 'synced'.
    Checks for version conflicts before creating.
    """
    import logging
    import os

    # Configure logging if verbose or GRYT_LOG_LEVEL is set
    log_level = os.getenv("GRYT_LOG_LEVEL", "WARNING" if not verbose else "INFO")
    logging.basicConfig(
        level=getattr(logging, log_level.upper(), logging.WARNING),
        format='%(name)s: %(message)s'
    )

    try:
        sync = _get_sync_client()

        if evolutions:
            result = sync.push_evolutions(version=version)
            console.print(f"[green]Evolution push complete[/green]")
            console.print(f"  Created: {result['created']}")
            console.print(f"  Updated: {result['updated']}")
        else:
            result = sync.push(version=version, force=force)
            console.print(f"[green]Push complete[/green]")
            console.print(f"  Created: {result['created']}")
            console.print(f"  Updated: {result['updated']}")

        if result["errors"]:
            console.print(f"\n[red]Errors:[/red] {len(result['errors'])}")
            for error in result["errors"]:
                console.print(f"  [red]•[/red] {error.get('version', 'unknown')}: {error['error']}")
                if "resolution" in error:
                    console.print(f"    Resolution: {error['resolution']}")

        if verbose and result.get("details"):
            console.print("\n[dim]Details:[/dim]")
            for detail in result["details"]:
                console.print(f"  [dim]•[/dim] {detail}")

    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)


@sync_app.command("status")
def status_command(
    version: Optional[str] = typer.Option(None, "--version", "-v", help="Show status for specific version"),
) -> None:
    """Show sync status for generations.

    Displays current sync state for all or specific generation.
    """
    try:
        sync = _get_sync_client()
        result = sync.status(version=version)

        if version:
            # Single version status
            gen = result["generation"]
            console.print(f"\n[bold]Generation {gen['version']}[/bold]")
            console.print(f"  Sync status: {gen['sync_status']}")
            console.print(f"  Remote ID: {gen['remote_id'] or 'not synced'}")
            console.print(f"  Last synced: {gen['last_synced_at'] or 'never'}")

            if gen["evolutions"]:
                console.print(f"\n  Evolutions: {len(gen['evolutions'])}")
                for evo in gen["evolutions"]:
                    console.print(f"    • {evo['tag']}: {evo['sync_status']}")
        else:
            # Summary status
            summary = result["summary"]
            console.print(f"\n[bold]Sync Status Summary[/bold]")
            console.print(f"  Total generations: {summary['total']}")
            console.print(f"  Synced: {summary['synced']}")
            console.print(f"  Pending: {summary['pending']}")
            console.print(f"  Conflicts: {summary['conflicts']}")

            if result["generations"]:
                table = Table(title="\nGenerations")
                table.add_column("Version", style="cyan")
                table.add_column("Status", style="magenta")
                table.add_column("Remote ID", style="dim")
                table.add_column("Last Synced", style="dim")

                for gen in result["generations"]:
                    table.add_row(
                        gen["version"],
                        gen["sync_status"],
                        gen["remote_id"] or "—",
                        gen["last_synced_at"] or "—",
                    )

                console.print(table)

    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)


@sync_app.command("config")
def config_command(
    mode: Optional[str] = typer.Option(None, "--mode", "-m", help="Set execution mode: local, cloud, hybrid"),
) -> None:
    """Configure sync settings.

    Execution modes:
      local: No auto-sync, manual sync only
      cloud: Auto-sync on every change
      hybrid: Sync on promote only (default)
    """
    try:
        config = Config.load_with_repo_context()

        if mode:
            if mode not in ("local", "cloud", "hybrid"):
                console.print("[red]Invalid mode. Must be: local, cloud, or hybrid[/red]")
                raise typer.Exit(1)

            config.execution_mode = mode
            config.save()
            console.print(f"[green]Execution mode set to:[/green] {mode}")
        else:
            # Show current config
            console.print(f"\n[bold]Sync Configuration[/bold]")
            console.print(f"  Execution mode: {config.execution_mode or 'hybrid (default)'}")
            console.print(f"  Cloud URL: {config.gryt_url or 'https://api.gryt.dev (default)'}")
            console.print(f"  Authenticated: {'yes' if config.username or config.api_key_id else 'no'}")

    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)
