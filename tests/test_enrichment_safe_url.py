import asyncio
import sys
from types import ModuleType, SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest

from saletool.enrichment import discovery, safe_url
from saletool.enrichment.fetcher import HttpFetcher, PlaywrightFetcher, RobotsCache
from saletool.enrichment.safe_url import UnsafeURLError, public_get, resolve_public_url

PUBLIC_IP = "93.184.216.34"


@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1/",
        "https://10.0.0.1/",
        "http://169.254.169.254/",
        "http://192.168.1.1/",
        "http://0.0.0.0/",
        "http://[::1]/",
        "http://[::ffff:127.0.0.1]/",
        "http://224.0.0.1/",
        "http://localhost/",
        "http://app.localhost/",
        "file:///etc/passwd",
        "ftp://example.com/file",
        "http://user:pass@example.com/",
    ],
)
def test_non_public_or_non_http_destinations_are_rejected(url):
    with pytest.raises(UnsafeURLError):
        asyncio.run(resolve_public_url(url))


def test_dns_with_any_private_address_is_rejected(monkeypatch):
    monkeypatch.setattr(
        safe_url, "_resolve_addresses", AsyncMock(return_value=[PUBLIC_IP, "10.0.0.1"])
    )
    with pytest.raises(UnsafeURLError):
        asyncio.run(resolve_public_url("https://public.example"))


def test_connection_is_pinned_and_preserves_host_tls_name_and_public_url(monkeypatch):
    resolver = AsyncMock(side_effect=[[PUBLIC_IP], ["127.0.0.1"]])
    monkeypatch.setattr(safe_url, "_resolve_addresses", resolver)
    requests = []

    def respond(request):
        requests.append(request)
        return httpx.Response(200, text="Public page")

    async def run():
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(respond), trust_env=False
        ) as client:
            return await public_get(client, "https://public.example:8443/about")

    response = asyncio.run(run())
    assert resolver.await_count == 1
    assert requests[0].url.host == PUBLIC_IP
    assert requests[0].headers["host"] == "public.example:8443"
    assert requests[0].extensions["sni_hostname"] == "public.example"
    assert str(response.url) == "https://public.example:8443/about"


def test_redirect_to_private_network_is_blocked_before_a_second_request(monkeypatch):
    monkeypatch.setattr(
        safe_url, "_resolve_addresses", AsyncMock(side_effect=[[PUBLIC_IP], ["10.0.0.1"]])
    )
    requests = []

    def redirect(request):
        requests.append(request)
        return httpx.Response(302, headers={"Location": "http://private.example/secret"})

    async def run():
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(redirect), trust_env=False
        ) as client:
            await public_get(client, "https://public.example")

    with pytest.raises(UnsafeURLError):
        asyncio.run(run())
    assert len(requests) == 1


def test_public_redirect_checks_robots_and_limits_each_destination(monkeypatch):
    monkeypatch.setattr(safe_url, "_resolve_addresses", AsyncMock(return_value=[PUBLIC_IP]))
    allowed = AsyncMock(return_value=True)
    wait = AsyncMock()

    def respond(request):
        if request.url.path == "/":
            return httpx.Response(301, headers={"Location": "/about"})
        return httpx.Response(200, text="About")

    async def run():
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(respond), trust_env=False
        ) as client:
            return await public_get(client, "https://public.example/", allowed=allowed, wait=wait)

    assert asyncio.run(run()).text == "About"
    assert [call.args[0] for call in allowed.await_args_list] == [
        "https://public.example/",
        "https://public.example/about",
    ]
    assert wait.await_count == 2


def test_fetcher_robots_and_discovery_never_send_to_private_ips():
    async def run():
        assert not (await HttpFetcher("Bot").fetch("http://127.0.0.1")).ok
        assert not (await PlaywrightFetcher("Bot").fetch("http://127.0.0.1")).ok
        assert not await RobotsCache("Bot").allowed("http://127.0.0.1")
        assert await discovery.urls_from_sitemap("127.0.0.1", "Bot") == []

    asyncio.run(run())


def test_sitemap_cannot_fetch_a_private_child_url(monkeypatch):
    async def resolve(host, port):
        return ["10.0.0.1"] if host == "private.example" else [PUBLIC_IP]

    monkeypatch.setattr(safe_url, "_resolve_addresses", resolve)
    requests = []

    def respond(request):
        requests.append(request)
        return httpx.Response(
            200, text="<sitemapindex><loc>http://private.example/child.xml</loc></sitemapindex>"
        )

    original_client = httpx.AsyncClient
    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda **kwargs: original_client(transport=httpx.MockTransport(respond), **kwargs),
    )
    assert asyncio.run(discovery.urls_from_sitemap("public.example", "Bot")) == []
    assert requests and all(request.url.host == PUBLIC_IP for request in requests)


def test_browser_blocks_private_subresources_and_websockets(monkeypatch):
    async def resolve(host, port):
        return ["10.0.0.1"] if host == "private.example" else [PUBLIC_IP]

    monkeypatch.setattr(safe_url, "_resolve_addresses", resolve)
    handlers = {}
    private_route = SimpleNamespace(
        request=SimpleNamespace(
            method="GET",
            url="http://private.example/secret",
            all_headers=AsyncMock(return_value={}),
        ),
        abort=AsyncMock(),
        fulfill=AsyncMock(),
    )
    socket_route = SimpleNamespace(close=AsyncMock())

    async def goto(*args, **kwargs):
        await handlers["request"](private_route)
        await handlers["socket"](socket_route)

    async def route(pattern, handler):
        handlers["request"] = handler

    async def route_socket(pattern, handler):
        handlers["socket"] = handler

    page = SimpleNamespace(goto=goto, content=AsyncMock(return_value="<html>Public page</html>"))
    context = SimpleNamespace(
        route=route, route_web_socket=route_socket, new_page=AsyncMock(return_value=page)
    )
    browser = SimpleNamespace(new_context=AsyncMock(return_value=context), close=AsyncMock())

    class FakePlaywright:
        async def __aenter__(self):
            return SimpleNamespace(chromium=SimpleNamespace(launch=AsyncMock(return_value=browser)))

        async def __aexit__(self, *args):
            pass

    module = ModuleType("playwright.async_api")
    module.async_playwright = FakePlaywright
    monkeypatch.setitem(sys.modules, "playwright.async_api", module)
    assert asyncio.run(PlaywrightFetcher("Bot").fetch("https://public.example")).ok
    private_route.abort.assert_awaited_once()
    private_route.fulfill.assert_not_awaited()
    socket_route.close.assert_awaited_once()
