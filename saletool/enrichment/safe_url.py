"""Fetch only public URLs; pin the validated IP to prevent DNS rebinding."""

from __future__ import annotations

import asyncio
import ipaddress
import socket
from collections.abc import Awaitable, Callable

import httpx


class UnsafeURLError(ValueError):
    pass


def _is_public(address: str) -> bool:
    ip = ipaddress.ip_address(address.split("%")[0])
    if not ip.is_global or ip.is_multicast:
        return False
    if isinstance(ip, ipaddress.IPv6Address):
        if ip.ipv4_mapped:
            return _is_public(str(ip.ipv4_mapped))
        # Block IPv4-mapped addresses so encoded internal addresses cannot slip through.
        if ip.sixtofour or ip.teredo or ip in ipaddress.ip_network("64:ff9b::/96"):
            return False
    return True


async def _resolve_addresses(host: str, port: int) -> list[str]:
    try:
        ipaddress.ip_address(host)
        return [host]
    except ValueError:
        pass
    try:
        records = await asyncio.get_running_loop().getaddrinfo(host, port, type=socket.SOCK_STREAM)
    except OSError as exc:
        raise httpx.ConnectError(f"Could not resolve crawler host: {host}") from exc
    return list(dict.fromkeys(record[4][0] for record in records))


async def resolve_public_url(
    raw: str | httpx.URL, timeout: float = 15.0
) -> tuple[httpx.URL, list[str]]:
    try:
        url = httpx.URL(raw)
        if url.scheme not in ("http", "https") or not url.host or url.userinfo:
            raise UnsafeURLError(
                "Blocked URL: only public HTTP(S) URLs without credentials are allowed."
            )
        if url.host.lower().rstrip(".") == "localhost" or url.host.lower().rstrip(".").endswith(
            ".localhost"
        ):
            raise UnsafeURLError("Blocked URL: localhost is not a public crawler destination.")
        addresses = await asyncio.wait_for(
            _resolve_addresses(url.host, url.port or (443 if url.scheme == "https" else 80)),
            timeout=timeout,
        )
        if not addresses or not all(_is_public(address) for address in addresses):
            raise UnsafeURLError(
                "Blocked URL: the destination resolves to a non-public IP address."
            )
        return url, addresses
    except (httpx.InvalidURL, ValueError) as exc:
        if isinstance(exc, UnsafeURLError):
            raise
        raise UnsafeURLError("Blocked URL: invalid crawler destination.") from exc
    except asyncio.TimeoutError as exc:
        raise httpx.ConnectTimeout("Crawler DNS resolution timed out.") from exc


async def public_get(
    client: httpx.AsyncClient,
    url: str | httpx.URL,
    headers: dict[str, str] | None = None,
    allowed: Callable[[str], Awaitable[bool]] | None = None,
    wait: Callable[[str], Awaitable[None]] | None = None,
    follow_redirects: bool = True,
) -> httpx.Response:
    """Validate each redirect, preserve Host/SNI, and connect only to an approved IP."""
    for _ in range(11):
        target, addresses = await resolve_public_url(url, client.timeout.connect or 15.0)
        if allowed is not None and not await allowed(str(target)):
            raise UnsafeURLError("Blocked by robots.txt")
        if wait is not None:
            await wait(str(target))
        request_headers = httpx.Headers(headers)
        request_headers["Host"] = target.netloc.decode("ascii")
        # Do not reuse a TLS session from another hostname on the same IP.
        request_headers["Connection"] = "close"
        # Do not reuse client cookies by IP because multiple hostnames may share an IP.
        original = httpx.Request("GET", target, headers=request_headers)
        pinned = httpx.Request(
            "GET",
            target.copy_with(host=addresses[0]),
            headers=request_headers,
            extensions={"sni_hostname": target.host},
        )
        response = await client.send(pinned, follow_redirects=False)
        response.request = original
        if (
            not follow_redirects
            or response.status_code not in (301, 302, 303, 307, 308)
            or "location" not in response.headers
        ):
            return response
        url = target.join(response.headers["location"])
        await response.aclose()
    raise httpx.TooManyRedirects("Crawler exceeded the redirect limit.")
