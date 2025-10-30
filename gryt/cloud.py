"""Cloud subcommands for Gryt CLI."""
from __future__ import annotations

import json
from typing import Optional
import typer

from .config import Config
from .cloud_client import GrytCloudClient


cloud_app = typer.Typer(name="cloud", help="Manage Gryt Cloud resources", no_args_is_help=True)


def _get_client() -> GrytCloudClient:
    """Get an authenticated cloud client."""
    config = Config.load_with_repo_context()
    if not config.has_credentials():
        typer.echo("Error: Not logged in. Run 'gryt cloud login' first.", err=True)
        raise typer.Exit(1)
    return GrytCloudClient(
        username=config.username,
        password=config.password,
        gryt_url=config.gryt_url,
        api_key_id=config.api_key_id,
        api_key_secret=config.api_key_secret,
    )


# Authentication Commands


@cloud_app.command("login", help="Configure cloud credentials")
def login(
    method: str = typer.Option("credentials", "--method", "-m", help="Authentication method (credentials or api-key)"),
):
    """Log in to Gryt Cloud by saving credentials."""
    config = Config.load_with_repo_context()
    if method == "api-key":
        api_key_id = typer.prompt("API key ID")
        api_key_secret = typer.prompt("API key secret", hide_input=True)
        config.set("api_key_id", api_key_id)
        config.set("api_key_secret", api_key_secret)
        config.set("username", None)
        config.set("password", None)
        typer.echo(f"✓ Logged in with API key {api_key_id}")
    elif method == "credentials":
        username = typer.prompt("Username")
        password = typer.prompt("Password", hide_input=True)
        config.set("username", username)
        config.set("password", password)
        config.set("api_key_id", None)
        config.set("api_key_secret", None)
        typer.echo(f"✓ Logged in as {username}")
    else:
        typer.echo("Error: Invalid authentication method. Please choose either 'credentials' or 'api-key'.", err=True)
        raise typer.Exit(1)
    config.save()


@cloud_app.command("signup", help="Create a new Gryt Cloud account")
def signup(
    username: str = typer.Option(..., "--username", "-u", prompt=True, help="Choose a username"),
    password: str = typer.Option(..., "--password", "-p", prompt=True, hide_input=True, confirmation_prompt=True, help="Choose a password"),
):
    """Create a new account and save credentials."""
    client = GrytCloudClient()
    try:
        result = client.create_account(username=username, password=password)
        typer.echo(json.dumps(result, indent=2))
        # Auto-login after signup
        config = Config.load_with_repo_context()
        config.set("username", username)
        config.set("password", password)
        config.save()
        typer.echo(f"✓ Account created and logged in as {username}")
    except RuntimeError as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(1)


@cloud_app.command("logout", help="Remove saved credentials")
def logout():
    """Log out by removing saved credentials."""
    config = Config.load_with_repo_context()
    config.set("username", None)
    config.set("password", None)
    config.set("api_key_id", None)
    config.set("api_key_secret", None)
    config.save()
    typer.echo("✓ Logged out")


@cloud_app.command("whoami", help="Show current user")
def whoami():
    """Display the currently logged-in user."""
    config = Config.load_with_repo_context()
    if config.api_key_id:
        typer.echo(f"Logged in with API key: {config.api_key_id}")
    elif config.username:
        typer.echo(f"Logged in as: {config.username}")
    else:
        typer.echo("Not logged in")
        raise typer.Exit(1)


# API Key Commands


api_key_app = typer.Typer(name="api-keys", help="Manage API keys", no_args_is_help=True)
cloud_app.add_typer(api_key_app)


@api_key_app.command("create", help="Create a new API key")
def create_api_key(
    name: str = typer.Option(..., "--name", "-n", help="API key name"),
    expires_in_days: Optional[int] = typer.Option(None, "--expires-in-days", "-d", help="Expiration in days"),
):
    """Create a new API key."""
    client = _get_client()
    try:
        result = client.create_api_key(name=name, expires_in_days=expires_in_days)
        typer.echo(json.dumps(result, indent=2))
    except RuntimeError as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(1)


@api_key_app.command("list", help="List all API keys")
def list_api_keys():
    """List all API keys."""
    client = _get_client()
    try:
        result = client.list_api_keys()
        typer.echo(json.dumps(result, indent=2))
    except RuntimeError as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(1)


@api_key_app.command("revoke", help="Revoke an API key")
def revoke_api_key(
    key_id: str = typer.Argument(..., help="API key ID to revoke"),
):
    """Revoke an API key."""
    client = _get_client()
    try:
        result = client.revoke_api_key(key_id=key_id)
        typer.echo(json.dumps(result, indent=2))
    except RuntimeError as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(1)


# Apply Command


@cloud_app.command("apply", help="Apply a declarative YAML configuration")
def apply(
    yaml_file: typer.FileText = typer.Argument(..., help="Path to the YAML configuration file"),
):
    """Apply a declarative YAML configuration (kubectl-style)."""
    client = _get_client()
    try:
        yaml_content = yaml_file.read()
        result = client.apply(yaml_content=yaml_content)
        typer.echo(json.dumps(result, indent=2))
    except RuntimeError as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(1)


# Pipeline Commands


pipeline_app = typer.Typer(name="pipelines", help="Manage cloud pipelines", no_args_is_help=True)
cloud_app.add_typer(pipeline_app)


@pipeline_app.command("list", help="List all pipelines")
def list_pipelines():
    """List all pipelines."""
    client = _get_client()
    try:
        result = client.list_pipelines()
        typer.echo(json.dumps(result, indent=2))
    except RuntimeError as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(1)


@pipeline_app.command("create", help="Create a new pipeline")
def create_pipeline(
    name: str = typer.Option(..., "--name", "-n", help="Pipeline name"),
    description: str = typer.Option("", "--description", "-d", help="Pipeline description"),
    config: str = typer.Option("", "--config", "-c", help="Pipeline configuration (YAML/JSON)"),
):
    """Create a new pipeline."""
    client = _get_client()
    try:
        result = client.create_pipeline(name=name, description=description, config=config)
        typer.echo(json.dumps(result, indent=2))
    except RuntimeError as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(1)


@pipeline_app.command("get", help="Get a pipeline by ID")
def get_pipeline(
    pipeline_id: str = typer.Argument(..., help="Pipeline ID"),
):
    """Get a specific pipeline."""
    client = _get_client()
    try:
        result = client.get_pipeline(pipeline_id=pipeline_id)
        typer.echo(json.dumps(result, indent=2))
    except RuntimeError as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(1)


@pipeline_app.command("delete", help="Delete a pipeline by ID")
def delete_pipeline(
    pipeline_id: str = typer.Argument(..., help="Pipeline ID"),
):
    """Delete a specific pipeline."""
    client = _get_client()
    try:
        result = client.delete_pipeline(pipeline_id=pipeline_id)
        typer.echo(json.dumps(result, indent=2))
    except RuntimeError as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(1)


# GitHub Repo Commands


repo_app = typer.Typer(name="repos", help="Manage GitHub repositories", no_args_is_help=True)
cloud_app.add_typer(repo_app)


@repo_app.command("list", help="List all GitHub repositories")
def list_repos():
    """List all GitHub repository configurations."""
    client = _get_client()
    try:
        result = client.list_github_repos()
        typer.echo(json.dumps(result, indent=2))
    except RuntimeError as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(1)


@repo_app.command("create", help="Add a GitHub repository")
def create_repo(
    name: str = typer.Option(..., "--name", "-n", help="Repository name"),
    git_url: str = typer.Option(..., "--url", "-u", help="Git repository URL"),
    branch: str = typer.Option("main", "--branch", "-b", help="Default branch"),
    private: bool = typer.Option(False, "--private", help="Mark as private repository"),
    token: Optional[str] = typer.Option(None, "--token", "-t", help="GitHub access token for private repos"),
):
    """Add a GitHub repository configuration."""
    client = _get_client()
    try:
        result = client.create_github_repo(
            name=name,
            git_url=git_url,
            is_private=private,
            branch=branch,
            access_token=token,
        )
        typer.echo(json.dumps(result, indent=2))
    except RuntimeError as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(1)


@repo_app.command("get", help="Get a repository by ID")
def get_repo(
    repo_id: str = typer.Argument(..., help="Repository ID"),
):
    """Get a specific GitHub repository configuration."""
    client = _get_client()
    try:
        result = client.get_github_repo(repo_id=repo_id)
        typer.echo(json.dumps(result, indent=2))
    except RuntimeError as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(1)


@repo_app.command("delete", help="Delete a repository by ID")
def delete_repo(
    repo_id: str = typer.Argument(..., help="Repository ID"),
):
    """Delete a specific GitHub repository configuration."""
    client = _get_client()
    try:
        result = client.delete_github_repo(repo_id=repo_id)
        typer.echo(json.dumps(result, indent=2))
    except RuntimeError as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(1)


# Job Commands


job_app = typer.Typer(name="jobs", help="Manage jobs", no_args_is_help=True)
cloud_app.add_typer(job_app)


@job_app.command("list", help="List all jobs")
def list_jobs():
    """List all jobs."""
    client = _get_client()
    try:
        result = client.list_jobs()
        typer.echo(json.dumps(result, indent=2))
    except RuntimeError as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(1)


@job_app.command("create", help="Create a new job")
def create_job(
    name: str = typer.Option(..., "--name", "-n", help="Job name"),
    description: str = typer.Option("", "--description", "-d", help="Job description"),
    pipeline_id: str = typer.Option(..., "--pipeline-id", "-p", help="Pipeline ID"),
    repo_id: Optional[str] = typer.Option(None, "--repo-id", "-r", help="GitHub repository ID"),
    branch: Optional[str] = typer.Option(None, "--branch", "-b", help="Branch override"),
):
    """Create a new job."""
    client = _get_client()
    try:
        result = client.create_job(
            name=name,
            description=description,
            pipeline_id=pipeline_id,
            github_repo_id=repo_id,
            branch_override=branch,
        )
        typer.echo(json.dumps(result, indent=2))
    except RuntimeError as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(1)


@job_app.command("get", help="Get a job by ID")
def get_job(
    job_id: str = typer.Argument(..., help="Job ID"),
):
    """Get a specific job."""
    client = _get_client()
    try:
        result = client.get_job(job_id=job_id)
        typer.echo(json.dumps(result, indent=2))
    except RuntimeError as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(1)


@job_app.command("delete", help="Delete a job by ID")
def delete_job(
    job_id: str = typer.Argument(..., help="Job ID"),
):
    """Delete a specific job."""
    client = _get_client()
    try:
        result = client.delete_job(job_id=job_id)
        typer.echo(json.dumps(result, indent=2))
    except RuntimeError as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(1)


# Webhook Commands


webhook_app = typer.Typer(name="webhooks", help="Manage webhooks", no_args_is_help=True)
cloud_app.add_typer(webhook_app)


@webhook_app.command("list", help="List all webhooks")
def list_webhooks():
    """List all webhooks."""
    client = _get_client()
    try:
        result = client.list_webhooks()
        typer.echo(json.dumps(result, indent=2))
    except RuntimeError as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(1)


@webhook_app.command("create", help="Create a new webhook")
def create_webhook(
    name: str = typer.Option(..., "--name", "-n", help="Webhook name"),
    description: str = typer.Option("", "--description", "-d", help="Webhook description"),
    job_id: str = typer.Option(..., "--job-id", "-j", help="Job ID to trigger"),
):
    """Create a new webhook."""
    client = _get_client()
    try:
        result = client.create_webhook(name=name, description=description, job_id=job_id)
        typer.echo(json.dumps(result, indent=2))
    except RuntimeError as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(1)


@webhook_app.command("get", help="Get a webhook by ID")
def get_webhook(
    webhook_id: str = typer.Argument(..., help="Webhook ID"),
):
    """Get a specific webhook."""
    client = _get_client()
    try:
        result = client.get_webhook(webhook_id=webhook_id)
        typer.echo(json.dumps(result, indent=2))
    except RuntimeError as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(1)


@webhook_app.command("delete", help="Delete a webhook by ID")
def delete_webhook(
    webhook_id: str = typer.Argument(..., help="Webhook ID"),
):
    """Delete a specific webhook."""
    client = _get_client()
    try:
        result = client.delete_webhook(webhook_id=webhook_id)
        typer.echo(json.dumps(result, indent=2))
    except RuntimeError as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(1)


@webhook_app.command("trigger", help="Trigger a webhook")
def trigger_webhook(
    key: str = typer.Argument(..., help="Webhook key"),
):
    """Trigger a webhook by its key."""
    client = GrytCloudClient()  # No auth needed for webhook trigger
    try:
        result = client.trigger_webhook(webhook_key=key)
        typer.echo(json.dumps(result, indent=2))
    except RuntimeError as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(1)
