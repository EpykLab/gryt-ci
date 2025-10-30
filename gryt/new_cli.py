"""
CLI commands for creating new projects from templates (v0.6.0)
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer

from .templates import get_template_registry
from .data import SqliteData


new_app = typer.Typer(
    name="new",
    help="Create a new project from a template",
    no_args_is_help=True,
)


def cmd_new_project(
    project_name: str,
    template: str = "minimal",
    output_dir: Optional[str] = None,
) -> int:
    """Create a new project from a template"""
    try:
        registry = get_template_registry()

        # Get template
        tpl = registry.get(template)
        if not tpl:
            typer.echo(f"Error: Template '{template}' not found", err=True)
            typer.echo(f"\nAvailable templates:", err=True)
            for t in registry.list():
                typer.echo(f"  {t.name:<20} - {t.description}", err=True)
            return 2

        # Determine output directory
        if output_dir:
            project_path = Path(output_dir).resolve()
        else:
            project_path = Path.cwd() / project_name

        # Check if directory exists
        if project_path.exists():
            typer.echo(f"Error: Directory {project_path} already exists", err=True)
            return 2

        # Create project from template
        typer.echo(f"Creating new project '{project_name}' from template '{template}'...")

        context = {
            "project_name": project_name,
        }

        tpl.render(project_path, context)

        # Initialize database
        gryt_dir = project_path / ".gryt"
        db_path = gryt_dir / "gryt.db"
        data = SqliteData(db_path=str(db_path))
        data.close()

        typer.echo(f"✓ Project created at {project_path}")
        typer.echo(f"\nNext steps:")
        typer.echo(f"  cd {project_name}")
        typer.echo(f"  gryt generation list  # View example generation")
        typer.echo(f"  gryt run {tpl.gryt_config.get('default_pipeline', 'default')}  # Run pipeline")

        return 0

    except Exception as e:
        typer.echo(f"Error: {e}", err=True)
        return 2


def cmd_list_templates() -> int:
    """List all available templates"""
    try:
        registry = get_template_registry()
        templates = registry.list()

        if not templates:
            typer.echo("No templates available")
            return 0

        typer.echo("\nAvailable Templates:\n")
        typer.echo(f"{'Name':<20} {'Language':<12} {'Description':<50}")
        typer.echo("-" * 85)

        for tpl in templates:
            typer.echo(f"{tpl.name:<20} {tpl.language:<12} {tpl.description:<50}")

        typer.echo(f"\nUsage: gryt new <project-name> --template <template-name>")

        return 0

    except Exception as e:
        typer.echo(f"Error: {e}", err=True)
        return 2


# Register commands
@new_app.command("project", help="Create a new project from a template")
def new_project_command(
    project_name: str = typer.Argument(..., help="Name of the project to create"),
    template: str = typer.Option("minimal", "--template", "-t", help="Template to use"),
    output: Optional[str] = typer.Option(None, "--output", "-o", help="Output directory (default: ./project_name)"),
):
    code = cmd_new_project(project_name, template, output)
    raise typer.Exit(code)


@new_app.command("list", help="List all available templates")
def list_templates_command():
    code = cmd_list_templates()
    raise typer.Exit(code)


# Callback just for help text
@new_app.callback()
def new_callback():
    """Create a new project from a template"""
    pass
