"""Async SDK compatibility uses local fakes; these are not inference evaluations."""
import asyncio
from contextlib import aclosing
from types import SimpleNamespace

import pytest

from itlr.chatbot import llm_client as lc


@pytest.fixture
def sdk(monkeypatch):
    state = {"pieces": ["answer"], "finish": "stop", "closed": 0, "calls": 0, "fail": 0}
    monkeypatch.setattr(lc, "provider_status", lambda: "openai")
    monkeypatch.setattr(lc, "api_key", lambda *_: "fixture-only")
    monkeypatch.setattr(lc, "_retries", lambda: 2)
    monkeypatch.setattr(lc, "DEFAULT_BACKOFF_S", 0)

    class Response:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            state["closed"] += 1

        def __aiter__(self):
            return self.events()

        async def events(self):
            yield SimpleNamespace(choices=[])
            for text in state["pieces"]:
                yield SimpleNamespace(choices=[SimpleNamespace(
                    delta=SimpleNamespace(content=text), finish_reason=None)])
            yield SimpleNamespace(choices=[SimpleNamespace(
                delta=SimpleNamespace(content=None), finish_reason=state["finish"])])

    class Client:
        def __init__(self, **_kwargs):
            self.chat = SimpleNamespace(completions=self)

        async def create(self, **kwargs):
            state["calls"] += 1
            state["kwargs"] = kwargs
            if state["calls"] <= state["fail"]:
                raise OSError("fixture transport unavailable")
            return Response()

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            pass

    import openai
    monkeypatch.setattr(openai, "AsyncOpenAI", Client)
    return state


def test_async_stream_preserves_history_and_completion(sdk):
    messages = [{"role": "system", "content": "sys"}, {"role": "user", "content": "question"}]

    async def run():
        return [text async for text in lc.astream(messages)]

    assert asyncio.run(run()) == ["answer"]
    assert sdk["kwargs"]["messages"] == messages
    assert sdk["closed"] == 1


def test_async_stream_closes_provider_when_consumer_stops(sdk):
    async def run():
        async with aclosing(lc.astream([])) as response:
            assert await anext(response) == "answer"
    asyncio.run(run())
    assert sdk["closed"] == 1


def test_async_stream_retries_only_before_partial_output(sdk):
    sdk["fail"] = 1

    async def run():
        return [text async for text in lc.astream([])]

    assert asyncio.run(run()) == ["answer"]
    assert sdk["calls"] == 2


def test_async_stream_rejects_truncated_completion_without_replaying_tokens(sdk):
    sdk["finish"] = "length"
    pieces = []

    async def run():
        with pytest.raises(lc.LLMError, match="Incomplete"):
            async for text in lc.astream([]):
                pieces.append(text)
    asyncio.run(run())
    assert pieces == ["answer"]
    assert sdk["calls"] == 1
    assert sdk["closed"] == 1


def test_async_stream_preserves_visible_legacy_metadata_warning(sdk, caplog):
    sdk["finish"] = None

    async def run():
        return [text async for text in lc.astream([])]
    assert asyncio.run(run()) == ["answer"]
    assert "completion unverified" in caplog.text
