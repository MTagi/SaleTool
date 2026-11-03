"""CLI entrypoint: saletool search --config examples/search_criteria.example.yaml"""

from __future__ import annotations

import logging
import os

import click

from saletool.config import load_criteria
from saletool.output import write_csv, write_json
from saletool.pipeline import run_search
from saletool.providers import get_provider


@click.group()
def cli() -> None:
    """SaleTool: find matching companies on LinkedIn and get senior contacts."""


@cli.command()
@click.option("--config", "config_path", required=True, help="Input file (.yaml/.json) describing the search criteria.")
@click.option("--api-key", default=None, help="Apollo API key (defaults to APOLLO_API_KEY).")
@click.option(
    "--no-reveal-emails",
    is_flag=True,
    help="Skip email lookup (uses Apollo credits) and only estimate matching companies and people.",
)
@click.option("--output", "output_path", default="output.csv", show_default=True, help="Output file (.csv or .json).")
@click.option("--verbose", is_flag=True, help="Print detailed logs.")
def search(
    config_path: str,
    api_key: str | None,
    no_reveal_emails: bool,
    output_path: str,
    verbose: bool,
) -> None:
    """Run the company and senior-contact search pipeline using a config file."""

    logging.basicConfig(level=logging.INFO if verbose else logging.WARNING, format="%(levelname)s %(message)s")

    criteria = load_criteria(config_path)

    key = api_key or os.environ.get("APOLLO_API_KEY", "")
    if not key:
        raise click.UsageError("Apollo API key required: use --api-key or the APOLLO_API_KEY environment variable")

    provider_instance = get_provider("apollo", api_key=key, reveal_emails=not no_reveal_emails)
    results = run_search(criteria, provider_instance)

    if output_path.lower().endswith(".json"):
        write_json(results, output_path)
    else:
        write_csv(results, output_path)

    total_contacts = sum(len(r.contacts) for r in results)
    click.echo(f"Done: {len(results)} companies, {total_contacts} contacts -> {output_path}")


@cli.group()
def web() -> None:
    """Manage and run the authenticated React web UI API."""


@web.command("create-user")
@click.option("--username", prompt=True)
@click.option("--password", prompt=True, hide_input=True, confirmation_prompt=True)
def web_create_user(username: str, password: str) -> None:
    """Create a login account (public self-registration is disabled).

    Uses the database backend selected by SALETOOL_DB_BACKEND (default: sqlite).
    """
    from saletool.db.factory import get_user_repository
    from saletool.security import hash_password

    repo = get_user_repository()
    try:
        repo.create_user(username, hash_password(password))
    except ValueError as exc:
        raise click.ClickException(str(exc)) from exc
    click.echo(f"Created account '{username}'.")


@web.command("serve")
@click.option("--host", default="127.0.0.1", show_default=True)
@click.option("--port", default=8000, show_default=True)
@click.option("--reload", is_flag=True, help="Reload automatically when code changes (development only).")
def web_serve(host: str, port: int, reload: bool) -> None:
    """Run the SaleTool API (FastAPI + uvicorn) for the React frontend."""
    import uvicorn

    uvicorn.run("saletool.api.app:app", host=host, port=port, reload=reload)


if __name__ == "__main__":
    cli()
