"""
TUI Dashboard for monitoring gryt-ci (v0.6.0)

Provides an interactive terminal interface to view:
- Active generations
- Evolution progress
- Recent pipeline runs
- Policy violations
"""
from __future__ import annotations

import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from rich.console import Console
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich import box

from .data import SqliteData


class Dashboard:
    """TUI Dashboard for gryt-ci monitoring"""

    def __init__(self, db_path: Path, refresh_interval: float = 2.0):
        self.db_path = db_path
        self.refresh_interval = refresh_interval
        self.console = Console()
        self.data: Optional[SqliteData] = None

    def start(self) -> None:
        """Start the dashboard with live updates"""
        self.data = SqliteData(db_path=str(self.db_path))

        try:
            with Live(self._build_layout(), console=self.console, refresh_per_second=1) as live:
                while True:
                    time.sleep(self.refresh_interval)
                    live.update(self._build_layout())
        except KeyboardInterrupt:
            pass
        finally:
            if self.data:
                self.data.close()

    def _build_layout(self) -> Layout:
        """Build the dashboard layout"""
        layout = Layout()

        # Split into header and body
        layout.split_column(
            Layout(name="header", size=3),
            Layout(name="body"),
        )

        # Split body into left and right columns
        layout["body"].split_row(
            Layout(name="left"),
            Layout(name="right"),
        )

        # Split left column into generations and evolutions
        layout["left"].split_column(
            Layout(name="generations"),
            Layout(name="evolutions"),
        )

        # Split right column into pipeline runs and stats
        layout["right"].split_column(
            Layout(name="pipelines"),
            Layout(name="stats"),
        )

        # Populate sections
        layout["header"].update(self._build_header())
        layout["generations"].update(self._build_generations_panel())
        layout["evolutions"].update(self._build_evolutions_panel())
        layout["pipelines"].update(self._build_pipelines_panel())
        layout["stats"].update(self._build_stats_panel())

        return layout

    def _build_header(self) -> Panel:
        """Build dashboard header"""
        title = Text()
        title.append("gryt-ci ", style="bold cyan")
        title.append("Dashboard", style="bold white")
        title.append(f" | {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", style="dim")

        return Panel(
            title,
            border_style="cyan",
            box=box.ROUNDED,
        )

    def _build_generations_panel(self) -> Panel:
        """Build generations overview panel"""
        if not self.data:
            return Panel("No data", title="Generations")

        # Query generations
        rows = self.data.query("""
            SELECT version, status, description, created_at, promoted_at
            FROM generations
            ORDER BY created_at DESC
            LIMIT 5
        """)

        table = Table(show_header=True, header_style="bold magenta", box=box.SIMPLE)
        table.add_column("Version", style="cyan")
        table.add_column("Status", style="yellow")
        table.add_column("Description")

        if not rows:
            table.add_row("No generations", "", "")
        else:
            for row in rows:
                status = row["status"]
                status_style = "green" if status == "promoted" else "yellow"

                table.add_row(
                    row["version"],
                    Text(status, style=status_style),
                    row["description"] or "",
                )

        return Panel(table, title="[bold]Generations[/bold]", border_style="magenta")

    def _build_evolutions_panel(self) -> Panel:
        """Build evolutions progress panel"""
        if not self.data:
            return Panel("No data", title="Evolutions")

        # Query recent evolutions
        rows = self.data.query("""
            SELECT e.tag, e.status, gc.type as change_type, e.started_at
            FROM evolutions e
            JOIN generation_changes gc ON e.change_id = gc.change_id
            ORDER BY e.started_at DESC
            LIMIT 8
        """)

        table = Table(show_header=True, header_style="bold green", box=box.SIMPLE)
        table.add_column("Tag", style="cyan")
        table.add_column("Type", style="blue")
        table.add_column("Status")

        if not rows:
            table.add_row("No evolutions", "", "")
        else:
            for row in rows:
                status = row["status"]

                # Color code by status
                if status == "pass":
                    status_text = Text("✓ PASS", style="bold green")
                elif status == "fail":
                    status_text = Text("✗ FAIL", style="bold red")
                elif status == "running":
                    status_text = Text("⟳ RUN", style="bold yellow")
                else:
                    status_text = Text(status, style="dim")

                table.add_row(
                    row["tag"],
                    row["change_type"] or "?",
                    status_text,
                )

        return Panel(table, title="[bold]Recent Evolutions[/bold]", border_style="green")

    def _build_pipelines_panel(self) -> Panel:
        """Build pipeline runs panel"""
        if not self.data:
            return Panel("No data", title="Pipeline Runs")

        # Query recent pipeline runs
        rows = self.data.query("""
            SELECT pipeline_id, status, start_timestamp, end_timestamp
            FROM pipelines
            ORDER BY start_timestamp DESC
            LIMIT 6
        """)

        table = Table(show_header=True, header_style="bold blue", box=box.SIMPLE)
        table.add_column("Pipeline", style="cyan")
        table.add_column("Status")
        table.add_column("Started")

        if not rows:
            table.add_row("No pipeline runs", "", "")
        else:
            for row in rows:
                status = row["status"]

                # Color code by status
                if status == "completed":
                    status_text = Text("DONE", style="green")
                elif status == "failed":
                    status_text = Text("FAIL", style="red")
                elif status == "running":
                    status_text = Text("RUN", style="yellow")
                else:
                    status_text = Text(status or "?", style="dim")

                started = row["start_timestamp"]
                if started:
                    try:
                        dt = datetime.fromisoformat(started)
                        started_str = dt.strftime("%H:%M:%S")
                    except:
                        started_str = "?"
                else:
                    started_str = "?"

                table.add_row(
                    row["pipeline_id"],
                    status_text,
                    started_str,
                )

        return Panel(table, title="[bold]Pipeline Runs[/bold]", border_style="blue")

    def _build_stats_panel(self) -> Panel:
        """Build statistics panel"""
        if not self.data:
            return Panel("No data", title="Stats")

        # Gather stats
        gen_rows = self.data.query("SELECT COUNT(*) as count FROM generations")
        gen_count = gen_rows[0]["count"] if gen_rows else 0

        evo_rows = self.data.query("SELECT COUNT(*) as count FROM evolutions")
        evo_count = evo_rows[0]["count"] if evo_rows else 0

        pass_rows = self.data.query("SELECT COUNT(*) as count FROM evolutions WHERE status = 'pass'")
        pass_count = pass_rows[0]["count"] if pass_rows else 0

        fail_rows = self.data.query("SELECT COUNT(*) as count FROM evolutions WHERE status = 'fail'")
        fail_count = fail_rows[0]["count"] if fail_rows else 0

        # Calculate pass rate
        if evo_count > 0:
            pass_rate = (pass_count / evo_count) * 100
        else:
            pass_rate = 0.0

        # Build stats display
        stats_text = Text()
        stats_text.append("Generations: ", style="bold")
        stats_text.append(f"{gen_count}\n", style="cyan")

        stats_text.append("Evolutions: ", style="bold")
        stats_text.append(f"{evo_count}\n", style="cyan")

        stats_text.append("Pass Rate: ", style="bold")
        rate_style = "green" if pass_rate >= 80 else "yellow" if pass_rate >= 60 else "red"
        stats_text.append(f"{pass_rate:.1f}%\n", style=rate_style)

        stats_text.append(f"  ✓ Passed: ", style="dim")
        stats_text.append(f"{pass_count}\n", style="green")

        stats_text.append(f"  ✗ Failed: ", style="dim")
        stats_text.append(f"{fail_count}", style="red")

        return Panel(stats_text, title="[bold]Stats[/bold]", border_style="yellow")


def run_dashboard(db_path: Path, refresh_interval: float = 2.0) -> None:
    """Run the dashboard TUI"""
    dashboard = Dashboard(db_path, refresh_interval)
    dashboard.start()
