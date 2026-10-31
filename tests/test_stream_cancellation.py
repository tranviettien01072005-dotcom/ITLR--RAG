"""Local TCP provider tests prove transport cleanup, not real model inference."""
import asyncio
import inspect
import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from types import SimpleNamespace

import pytest


@pytest.fixture
def upstream(monkeypatch):
    started = threading.Event()
    closed = threading.Event()
    release = threading.Event()
    state = {"first_delta": False}

    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, *_args):
            pass

        def do_GET(self):
            body = json.dumps({"models": [{"name": "qwen2.5:3b"}]}).encode()
            self.send_response(200)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_POST(self):
            self.rfile.read(int(self.headers["Content-Length"]))
            self.send_response(200)
            self.send_header("Content-Type", "application/x-ndjson")
            self.send_header("Transfer-Encoding", "chunked")
            self.end_headers()
            if "response_bytes" in state:
                data = state["response_bytes"]
                for byte in data:
                    self.wfile.write(b"1\r\n" + bytes([byte]) + b"\r\n")
                self.wfile.write(b"0\r\n\r\n")
                self.wfile.flush()
                return
            if state["first_delta"]:
                data = b'{"message":{"content":"draft"},"done":false}\n'
                self.wfile.write(f"{len(data):x}\r\n".encode() + data + b"\r\n")
                self.wfile.flush()
            started.set()
            self.connection.settimeout(0.05)
            while not release.is_set():
                try:
                    if self.connection.recv(1) == b"":
                        closed.set()
                        return
                except TimeoutError:
                    continue
                except ConnectionError:
                    closed.set()
                    return

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("USE_OLLAMA", "1")
    monkeypatch.setenv("OLLAMA_MODEL", "qwen2.5:3b")
    monkeypatch.setenv("OLLAMA_BASE_URL", f"http://127.0.0.1:{server.server_port}")
    monkeypatch.setenv("OLLAMA_TIMEOUT", "3")
    from itlr.chatbot import llm_client
    llm_client.reset_cache()
    try:
        yield state, started, closed
    finally:
        release.set()
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
        llm_client.reset_cache()


def prepared_engine(monkeypatch):
    from itlr.chatbot.chatbot import EducationalChatbot
    from itlr.engine import RecommenderEngine
    bot = object.__new__(EducationalChatbot)
    bot.search_index = {}
    prepared = {"sources": [], "all_recs": [], "mode": "answer", "sys_prompt": "SYS",
                "llm_message": "question", "history": []}
    monkeypatch.setattr(bot, "_prepare", lambda *_args: ("generate", prepared))
    return RecommenderEngine([], None, {}, None, bot)


@pytest.mark.parametrize("after_delta", [False, True], ids=["before-first-delta", "after-first-delta"])
def test_api_disconnect_closes_stalled_provider_without_final(monkeypatch, upstream, after_delta):
    from itlr.api import server as srv
    state, provider_started, provider_closed = upstream
    state["first_delta"] = after_delta
    monkeypatch.setattr(srv, "load_engine", lambda: prepared_engine(monkeypatch))

    async def run():
        response = srv.api_chat_stream(srv.ChatReq(message="question"))
        if inspect.isawaitable(response):
            response = await response
        text_sent = asyncio.Event()
        events = []

        async def send(message):
            if message["type"] != "http.response.body":
                return
            for frame in message.get("body", b"").decode().split("\n\n"):
                if frame.startswith("data: "):
                    event = json.loads(frame[6:])
                    events.append(event)
                    if event["type"] == "text":
                        text_sent.set()

        disconnected_at = None

        async def receive():
            nonlocal disconnected_at
            assert await asyncio.to_thread(provider_started.wait, 2), "Provider request was never started"
            if after_delta:
                await asyncio.wait_for(text_sent.wait(), 2)
            disconnected_at = time.monotonic()
            return {"type": "http.disconnect"}

        # Keep the response alive: cleanup must not depend on CPython destruction.
        await response({"type": "http", "asgi": {"spec_version": "2.0"}}, receive, send)
        assert disconnected_at is not None
        assert time.monotonic() - disconnected_at < 1, "Disconnect waited for the provider read timeout"
        assert await asyncio.to_thread(provider_closed.wait, 0.5), "Provider socket remains open after client disconnect"
        assert not {"final", "done"} & {event["type"] for event in events}

    asyncio.run(run())


@pytest.mark.parametrize("invalid", [b"\xff", b"\xe2\x82"])
def test_async_provider_rejects_corrupt_utf8(monkeypatch, upstream, invalid):
    from itlr.chatbot import llm_client
    state, _started, _closed = upstream
    state["response_bytes"] = (b'{"message":{"content":"' + invalid + b'"},"done":false}\n'
                               b'{"message":{"content":""},"done":true,"done_reason":"stop"}\n')

    async def run():
        with pytest.raises(llm_client.LLMError):
            _ = [piece async for piece in llm_client.astream([{"role": "user", "content": "q"}])]

    asyncio.run(run())


def test_async_provider_preserves_fragmented_utf8(upstream):
    from itlr.chatbot import llm_client
    state, _started, _closed = upstream
    state["response_bytes"] = (json.dumps({"message": {"content": "Tiếng Việt"}, "done": False}, ensure_ascii=False).encode()
                               + b'\n{"message":{"content":""},"done":true,"done_reason":"stop"}\n')

    async def run():
        assert [piece async for piece in llm_client.astream([{"role": "user", "content": "q"}])] == ["Tiếng Việt"]

    asyncio.run(run())


def test_api_send_disconnect_closes_suspended_engine_generator(monkeypatch):
    from itlr.api import server as srv
    from starlette.requests import ClientDisconnect
    closed = []

    async def engine_stream(*_args, **_kwargs):
        try:
            yield "sources", []
            await asyncio.Event().wait()
        finally:
            closed.append(True)

    monkeypatch.setattr(srv, "load_engine", lambda: SimpleNamespace(achat_stream=engine_stream))

    async def run():
        response = srv.api_chat_stream(srv.ChatReq(message="question"))
        if inspect.isawaitable(response):
            response = await response

        async def send(message):
            if message["type"] == "http.response.body":
                raise OSError("client connection closed")

        async def receive():
            await asyncio.Event().wait()

        with pytest.raises(ClientDisconnect):
            await response({"type": "http", "asgi": {"spec_version": "2.4"}}, receive, send)
        assert closed == [True]

    asyncio.run(run())


def test_api_provider_timeout_replaces_partial_text_with_one_failed_final(monkeypatch, upstream):
    from itlr.api import server as srv
    state, _started, provider_closed = upstream
    state["first_delta"] = True
    monkeypatch.setenv("OLLAMA_TIMEOUT", "0.3")
    monkeypatch.setattr(srv, "load_engine", lambda: prepared_engine(monkeypatch))

    async def run():
        response = srv.api_chat_stream(srv.ChatReq(message="question"))
        if inspect.isawaitable(response):
            response = await response
        events = []

        async def send(message):
            for frame in message.get("body", b"").decode().split("\n\n"):
                if frame.startswith("data: "):
                    events.append(json.loads(frame[6:]))

        async def receive():
            await asyncio.Event().wait()

        await asyncio.wait_for(response({"type": "http", "asgi": {"spec_version": "2.0"}}, receive, send), 2)
        assert any(event.get("text") == "draft" for event in events)
        finals = [event for event in events if event["type"] == "final"]
        assert len(finals) == 1
        assert finals[0]["generation_mode"] == "insufficient_evidence"
        assert finals[0]["generation_error"]
        assert finals[0]["response"] != "draft"
        assert sum(event["type"] == "done" for event in events) == 1
        assert await asyncio.to_thread(provider_closed.wait, 0.5)

    asyncio.run(run())
