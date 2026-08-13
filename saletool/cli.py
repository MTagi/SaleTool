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
    """SaleTool: tìm công ty phù hợp trên LinkedIn và lấy liên hệ cấp cao."""


@cli.command()
@click.option("--config", "config_path", required=True, help="File input format (.yaml/.json) mô tả mục tiêu tìm kiếm.")
@click.option("--provider", default="mock", show_default=True, help="Nhà cung cấp dữ liệu: mock, apollo.")
@click.option("--api-key", default=None, help="API key của provider (mặc định lấy từ biến môi trường).")
@click.option("--output", "output_path", default="output.csv", show_default=True, help="File kết quả (.csv hoặc .json).")
@click.option("--verbose", is_flag=True, help="In log chi tiết.")
def search(config_path: str, provider: str, api_key: str | None, output_path: str, verbose: bool) -> None:
    """Chạy pipeline tìm công ty + liên hệ cấp cao theo file cấu hình."""

    logging.basicConfig(level=logging.INFO if verbose else logging.WARNING, format="%(levelname)s %(message)s")

    criteria = load_criteria(config_path)

    provider_kwargs = {}
    if provider == "apollo":
        provider_kwargs["api_key"] = api_key or os.environ.get("APOLLO_API_KEY", "")

    provider_instance = get_provider(provider, **provider_kwargs)
    results = run_search(criteria, provider_instance)

    if output_path.lower().endswith(".json"):
        write_json(results, output_path)
    else:
        write_csv(results, output_path)

    total_contacts = sum(len(r.contacts) for r in results)
    click.echo(f"Xong: {len(results)} công ty, {total_contacts} liên hệ -> {output_path}")


if __name__ == "__main__":
    cli()
