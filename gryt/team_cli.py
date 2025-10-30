"""
CLI commands for Team management (v1.0.0)
"""
from __future__ import annotations

from typing import Optional

import typer

from .cloud_client import GrytCloudClient
from .config import Config


team_app = typer.Typer(
    name="team",
    help="Manage teams (cloud-only feature)",
    no_args_is_help=True,
)


def _get_cloud_client() -> GrytCloudClient:
    """Get configured cloud client."""
    config = Config.load_with_repo_context()

    if not config.username or not config.gryt_url:
        typer.echo(
            "Error: Cloud credentials not configured. Run 'gryt cloud login' first.",
            err=True,
        )
        raise typer.Exit(2)

    return GrytCloudClient(
        username=config.username,
        password=config.password,
        gryt_url=config.gryt_url,
        api_key_id=config.api_key_id,
        api_key_secret=config.api_key_secret,
    )


def cmd_team_create(name: str, description: Optional[str] = None) -> int:
    """Create a new team"""
    try:
        client = _get_cloud_client()
        result = client.create_team(name, description)

        team_id = result.get("team_id")
        typer.echo(f"✓ Created team '{name}'")
        typer.echo(f"  Team ID: {team_id}")
        if description:
            typer.echo(f"  Description: {description}")

        return 0

    except Exception as e:
        typer.echo(f"Error: {e}", err=True)
        return 2


def cmd_team_list() -> int:
    """List all teams"""
    try:
        client = _get_cloud_client()
        result = client.list_teams()

        teams = result.get("data", [])
        if not teams:
            typer.echo("No teams found. Create one with 'gryt team create <name>'")
            return 0

        typer.echo("\nTeams:\n")
        typer.echo(f"{'Name':<30} {'Team ID':<40} {'Members':<10}")
        typer.echo("-" * 85)

        for team in teams["teams"]:
            name = team.get("name", "?")
            team_id = team.get("team_id", "?")
            member_count = team.get("member_count", 0)
            typer.echo(f"{name:<30} {team_id:<40} {member_count:<10}")

        return 0

    except Exception as e:
        typer.echo(f"Error: {e}", err=True)
        return 2


def cmd_team_members(team_id: str) -> int:
    """List members of a team"""
    try:
        client = _get_cloud_client()
        result = client.list_team_members(team_id)

        members = result.get("data", [])
        if not members:
            typer.echo(f"No members in team {team_id}")
            typer.echo(f"Add members with: gryt team add-member {team_id} <username>")
            return 0

        typer.echo(f"\nMembers of team {team_id}:\n")
        typer.echo(f"{'Username':<30} {'Role':<15} {'Added':<20}")
        typer.echo("-" * 70)

        for member in members["members"]:
            username = member.get("username", "?")
            role = member.get("role", "member")
            added_at = member.get("added_at", "?")
            typer.echo(f"{username:<30} {role:<15} {added_at:<20}")

        return 0

    except Exception as e:
        typer.echo(f"Error: {e}", err=True)
        return 2


def cmd_team_add_member(team_id: str, username: str) -> int:
    """Add a member to a team"""
    try:
        client = _get_cloud_client()
        client.add_team_member(team_id, username)

        typer.echo(f"✓ Added {username} to team {team_id}")

        return 0

    except Exception as e:
        typer.echo(f"Error: {e}", err=True)
        return 2


def cmd_team_remove_member(team_id: str, username: str) -> int:
    """Remove a member from a team"""
    try:
        client = _get_cloud_client()
        client.remove_team_member(team_id, username)

        typer.echo(f"✓ Removed {username} from team {team_id}")

        return 0

    except Exception as e:
        typer.echo(f"Error: {e}", err=True)
        return 2


def cmd_team_delete(team_id: str) -> int:
    """Delete a team"""
    try:
        # Confirm deletion
        confirm = typer.confirm(f"Are you sure you want to delete team {team_id}?")
        if not confirm:
            typer.echo("Cancelled.")
            return 0

        client = _get_cloud_client()
        client.delete_team(team_id)

        typer.echo(f"✓ Deleted team {team_id}")

        return 0

    except Exception as e:
        typer.echo(f"Error: {e}", err=True)
        return 2


# Register commands
@team_app.command("create", help="Create a new team")
def create_command(
    name: str = typer.Argument(..., help="Team name"),
    description: Optional[str] = typer.Option(None, "--description", "-d", help="Team description"),
):
    code = cmd_team_create(name, description)
    raise typer.Exit(code)


@team_app.command("list", help="List all teams")
def list_command():
    code = cmd_team_list()
    raise typer.Exit(code)


@team_app.command("members", help="List members of a team")
def members_command(
    team_id: str = typer.Argument(..., help="Team ID"),
):
    code = cmd_team_members(team_id)
    raise typer.Exit(code)


@team_app.command("add-member", help="Add a member to a team")
def add_member_command(
    team_id: str = typer.Argument(..., help="Team ID"),
    username: str = typer.Argument(..., help="Username to add"),
):
    code = cmd_team_add_member(team_id, username)
    raise typer.Exit(code)


@team_app.command("remove-member", help="Remove a member from a team")
def remove_member_command(
    team_id: str = typer.Argument(..., help="Team ID"),
    username: str = typer.Argument(..., help="Username to remove"),
):
    code = cmd_team_remove_member(team_id, username)
    raise typer.Exit(code)


@team_app.command("delete", help="Delete a team")
def delete_command(
    team_id: str = typer.Argument(..., help="Team ID"),
):
    code = cmd_team_delete(team_id)
    raise typer.Exit(code)
