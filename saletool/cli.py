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
@click.option("--provider", default="mock", show_default=True, help="Nhà cung cấp dữ liệu: mock, apollo, csv_import.")
@click.option("--api-key", default=None, help="API key của provider (mặc định lấy từ biến môi trường).")
@click.option(
    "--companies-csv",
    default=None,
    help="[csv_import] File CSV danh sách công ty bạn tự export/copy (vd: từ Sales Navigator).",
)
@click.option(
    "--contacts-csv",
    default=None,
    help="[csv_import] File CSV danh sách liên hệ bạn tự export/copy (tuỳ chọn).",
)
@click.option("--output", "output_path", default="output.csv", show_default=True, help="File kết quả (.csv hoặc .json).")
@click.option("--verbose", is_flag=True, help="In log chi tiết.")
def search(
    config_path: str,
    provider: str,
    api_key: str | None,
    companies_csv: str | None,
    contacts_csv: str | None,
    output_path: str,
    verbose: bool,
) -> None:
    """Chạy pipeline tìm công ty + liên hệ cấp cao theo file cấu hình."""

    logging.basicConfig(level=logging.INFO if verbose else logging.WARNING, format="%(levelname)s %(message)s")

    criteria = load_criteria(config_path)

    provider_kwargs = {}
    if provider == "apollo":
        provider_kwargs["api_key"] = api_key or os.environ.get("APOLLO_API_KEY", "")
    elif provider == "csv_import":
        if not companies_csv:
            raise click.UsageError("Provider csv_import cần --companies-csv")
        provider_kwargs["companies_csv"] = companies_csv
        if contacts_csv:
            provider_kwargs["contacts_csv"] = contacts_csv

    provider_instance = get_provider(provider, **provider_kwargs)
    results = run_search(criteria, provider_instance)

    if output_path.lower().endswith(".json"):
        write_json(results, output_path)
    else:
        write_csv(results, output_path)

    total_contacts = sum(len(r.contacts) for r in results)
    click.echo(f"Xong: {len(results)} công ty, {total_contacts} liên hệ -> {output_path}")


@cli.group()
def web() -> None:
    """Quản lý và chạy API cho web UI (React) có đăng nhập."""


@web.command("create-user")
@click.option("--username", prompt=True)
@click.option("--password", prompt=True, hide_input=True, confirmation_prompt=True)
def web_create_user(username: str, password: str) -> None:
    """Tạo tài khoản đăng nhập (không có tự đăng ký công khai).

    Dùng DB backend theo SALETOOL_DB_BACKEND (mặc định: sqlite).
    """
    from saletool.db.factory import get_user_repository
    from saletool.security import hash_password

    repo = get_user_repository()
    try:
        repo.create_user(username, hash_password(password))
    except ValueError as exc:
        raise click.ClickException(str(exc))
    click.echo(f"Đã tạo tài khoản '{username}'.")


@web.command("serve")
@click.option("--host", default="127.0.0.1", show_default=True)
@click.option("--port", default=8000, show_default=True)
@click.option("--reload", is_flag=True, help="Tự reload khi code thay đổi (chỉ dùng khi phát triển).")
def web_serve(host: str, port: int, reload: bool) -> None:
    """Chạy SaleTool API (FastAPI + uvicorn) để React frontend gọi vào."""
    import uvicorn

    uvicorn.run("saletool.api.app:app", host=host, port=port, reload=reload)


if __name__ == "__main__":
    cli()
