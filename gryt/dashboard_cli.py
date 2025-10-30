"""
CLI command for TUI dashboard (v0.6.0)
"""
from __future__ import annotations

from pathlib import Path

import typer

from .dashboard import run_dashboard


GRYT_DIRNAME = ".gryt"
DEFAULT_DB_RELATIVE = "gryt.db"


def cmd_dashboard(refresh: float = 2.0) -> int:
    """Launch the TUI dashboard"""
    try:
        # Find database
        from .paths import get_repo_db_path, ensure_in_repo

        # Ensure we're in a repo
        ensure_in_repo()

        db_path = get_repo_db_path()
        if not db_path or not db_path.exists():
            typer.echo(
                f"Error: Database not found at {db_path}. Run 'gryt init' first.",
                err=True,
            )
            return 2

        # Run dashboard
        typer.echo("Starting dashboard... (Press Ctrl+C to exit)")
        run_dashboard(db_path, refresh_interval=refresh)

        return 0

    except KeyboardInterrupt:
        typer.echo("\nDashboard stopped")
        return 0
    except Exception as e:
        typer.echo(f"Error: {e}", err=True)
        return 2


def dashboard_command(
    refresh: float = typer.Option(2.0, "--refresh", "-r", help="Refresh interval in seconds"),
):
    """Launch the interactive TUI dashboard"""
    code = cmd_dashboard(refresh)
    raise typer.Exit(code)
