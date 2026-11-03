import asyncio

import httpx
import pytest

from saletool.llm_api import LLMTimeoutError, post_chat
from saletool.models import LLMSettings


def test_chat_does_not_require_python_311_timeout_api(monkeypatch, httpx_mock):
    monkeypatch.delattr(asyncio, "timeout", raising=False)
    httpx_mock.add_response(json={"choices": [{"message": {"content": "ok"}}]})
    assert asyncio.run(post_chat(LLMSettings(api_key="fake"), {"messages": []})) == "ok"


def test_chat_deadline_cancels_a_stalled_request(httpx_mock):
    cancelled = []

    async def stall(request):
        try:
            await asyncio.sleep(10)
        finally:
            cancelled.append(True)
        return httpx.Response(200)

    httpx_mock.add_callback(stall)
    with pytest.raises(LLMTimeoutError, match="timed out"):
        asyncio.run(post_chat(LLMSettings(api_key="fake"), {"messages": []}, timeout=0.02))
    assert cancelled == [True]
