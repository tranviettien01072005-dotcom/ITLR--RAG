"""Test cho itlr.chatbot.llm_client — lớp LLM client với thứ tự ưu tiên
DeepSeek → OpenAI → Ollama, retry/backoff, token tracking, che giấu API key.

Không dùng key thật: mọi test đều mock SDK (fake client được nạp qua _make_client).
"""

import types
import json

import pytest

import itlr.chatbot.llm_client as lc


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    """Xóa mọi biến env LLM để test không phụ thuộc môi trường thật; dọn cache module."""
    for var in ("DEEPSEEK_API_KEY", "DEEPSEEK_BASE_URL", "DEEPSEEK_MODEL",
                "OPENAI_API_KEY", "OPENAI_MODEL", "USE_OLLAMA",
                "OLLAMA_BASE_URL", "OLLAMA_MODEL", "OLLAMA_TIMEOUT",
                "DEEPSEEK_RETRIES", "DEEPSEEK_TIMEOUT_S", "DEEPSEEK_STREAM_TIMEOUT_S"):
        monkeypatch.delenv(var, raising=False)
    lc.reset_cache()
    yield
    lc.reset_cache()


class _FakeChatCompletions:
    """Fake openai client.chat.completions: n lần đầu raise, rồi trả content + usage."""

    def __init__(self, behavior: dict, recorder: list):
        self._behavior = behavior
        self._recorder = recorder
        self.calls = 0

    def create(self, **kwargs):
        self.calls += 1
        self._behavior["__calls"] = self._behavior.get("__calls", 0) + 1
        self._recorder.append({"provider_kwargs": kwargs})
        if self._behavior["__calls"] <= self._behavior.get("fail_times", 0):
            errors = self._behavior["errors"]
            raise errors[min(self._behavior["__calls"] - 1, len(errors) - 1)]
        if kwargs.get("stream"):
            Chunk = types.SimpleNamespace
            chunks = []
            for piece in self._behavior.get("stream_chunks", ["a", "b"]):
                chunks.append(Chunk(choices=[Chunk(delta=Chunk(content=piece))]))
            if 'finish_reason' in self._behavior:
                chunks.append(Chunk(choices=[Chunk(delta=Chunk(content=None),
                    finish_reason=self._behavior['finish_reason'])]))
            if self._behavior.get('usage_only'):
                chunks.append(Chunk(choices=[], usage=Chunk(
                    prompt_tokens=120, completion_tokens=45, total_tokens=165)))
            class FakeStream:
                def __iter__(self):
                    return iter(chunks)

                def close(self):
                    pass

            return FakeStream()

        usage = types.SimpleNamespace(
            prompt_tokens=120, completion_tokens=45, total_tokens=165)
        choice = types.SimpleNamespace(message=types.SimpleNamespace(
            content=self._behavior.get("text", "Câu trả lời mô phỏng.")),
            finish_reason=self._behavior.get('finish_reason'))
        return types.SimpleNamespace(choices=[choice], usage=usage)


class _FakeChat:
    def __init__(self, behavior: dict, recorder: list):
        self.completions = _FakeChatCompletions(behavior, recorder)


class _FakeClient:
    """Fake OpenAI-compatible client: ghi nhớ api_key/base_url nhận được."""

    instantiations: list = []

    def __init__(self, api_key: str, base_url: str, behavior: dict, recorder: list):
        self.api_key = api_key
        self.base_url = base_url
        self.chat = _FakeChat(behavior, recorder)
        _FakeClient.instantiations.append(self)

    def close(self):
        pass


@pytest.fixture()
def recorder():
    return []


@pytest.fixture()
def wire(monkeypatch, recorder):
    """Nối _make_client tới _FakeClient; test đặt hành vi qua wire.set({...})."""
    holder = {"behavior": {"fail_times": 0, "text": "OK"}}

    class _Wire:
        @staticmethod
        def set(new_behavior: dict):
            holder["behavior"] = new_behavior

    monkeypatch.setattr(lc, "_make_client", lambda provider, api_key_value, timeout_s: _FakeClient(
        api_key=api_key_value,
        base_url=f"https://api.{provider}.example",
        behavior=holder["behavior"], recorder=recorder))
    return _Wire()


def test_provider_priority_deepseek_over_openai(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-x")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-y")
    assert lc.provider_status() == "deepseek"


@pytest.mark.parametrize('streaming,name,value', [
    (False, 'DEEPSEEK_RETRIES', '3.5'),
    (True, 'DEEPSEEK_RETRIES', '3.5'),
    (False, 'DEEPSEEK_TIMEOUT_S', 'invalid'),
    (True, 'DEEPSEEK_STREAM_TIMEOUT_S', 'invalid'),
])
def test_invalid_numeric_config_raises_llmerror(wire, monkeypatch, name, value, streaming):
    monkeypatch.setenv('DEEPSEEK_API_KEY', 'fake-key')
    monkeypatch.setenv(name, value)
    with pytest.raises(lc.LLMError, match=name):
        if streaming:
            list(lc.stream([{'role': 'user', 'content': 'test'}]))
        else:
            lc.chat([{'role': 'user', 'content': 'test'}])


def test_provider_priority_openai_when_no_deepseek(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-y")
    assert lc.provider_status() == "openai"


def test_provider_ollama_or_none(monkeypatch):
    """Không key + Ollama không chạy + không tắt tường minh -> phải là 'none'
    (đproductive-quyết định thiết kế; không chấp nhận trạng thái mơ hồ)."""
    monkeypatch.setattr(lc, "ollama_reachable", lambda: False)
    assert lc.provider_status() == "none"
    monkeypatch.setattr(lc, "ollama_reachable", lambda: True)
    assert lc.provider_status() == "ollama"
    monkeypatch.setenv("USE_OLLAMA", "0")
    assert lc.provider_status() == "none"


def test_chat_nonstream_uses_deepseek_key_and_base_url(wire, recorder, monkeypatch):
    wire.set({"fail_times": 0, "text": "Xin chào!"})
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-real-deepseek")
    res = lc.chat([{"role": "user", "content": "câu hỏi"}])
    assert isinstance(res, lc.LLMResult)
    assert res.text == "Xin chào!"
    assert res.provider == "deepseek"
    assert res.model.startswith("deepseek")
    inst = _FakeClient.instantiations[-1]
    assert inst.api_key == "sk-real-deepseek"
    # base_url mặc định của DeepSeek (factory fake trả https://api.deepseek.example —
    # phần REAL của base_url default được kiểm riêng trong test_defaults_base_url)
    assert inst.base_url == "https://api.deepseek.example"


def test_defaults_base_url_and_model(monkeypatch):
    assert lc.DEFAULT_BASE_URLS["deepseek"] == "https://api.deepseek.com"
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-real")
    assert lc.default_model("deepseek") == "deepseek-flash"


def test_base_url_rejects_non_http_scheme(monkeypatch):
    monkeypatch.setenv("OLLAMA_BASE_URL", "file:///etc/passwd")
    with pytest.raises(lc.LLMError):
        lc.base_url("ollama")


def test_default_model_env_overridable(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk")
    monkeypatch.setenv("DEEPSEEK_MODEL", "deepseek-reasoner")
    assert lc.default_model("deepseek") == "deepseek-reasoner"


def test_retry_backoff_then_success(wire, monkeypatch):
    wire.set({"fail_times": 2, "text": "OK",
              "errors": [TimeoutError("t1"), RuntimeError("boom")]})
    slept = []
    monkeypatch.setattr(lc.time, "sleep", lambda s: slept.append(s))
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk")
    res = lc.chat([{"role": "user", "content": "h"}])
    assert res.text == "OK"
    assert len(slept) == 2 and slept[1] >= slept[0]


def test_exhausted_retries_raise_llmerror_no_key_leak(wire, monkeypatch):
    wire.set({"fail_times": 10, "errors": [TimeoutError("ttt")]})
    monkeypatch.setattr(lc.time, "sleep", lambda s: None)
    secret = "sk-vibikiet-EXAMPLE-2019"
    monkeypatch.setenv("DEEPSEEK_API_KEY", secret)
    with pytest.raises(lc.LLMError) as excinfo:
        lc.chat([{"role": "user", "content": "h"}])
    msg = str(excinfo.value)
    assert secret not in msg, "API key không được xuất hiện trong thông báo lỗi"


def test_stream_yields_pieces(wire, monkeypatch):
    wire.set({"stream_chunks": ["X", "y", "z"]})
    monkeypatch.setenv("OPENAI_API_KEY", "sk-o")
    pieces = list(lc.stream([{"role": "user", "content": "h"}]))
    assert pieces == ["X", "y", "z"]


@pytest.mark.parametrize('provider', ['deepseek', 'openai'])
def test_stream_accepts_usage_only_chunk(wire, monkeypatch, provider):
    wire.set({'stream_chunks': ['answer'], 'usage_only': True})
    monkeypatch.setenv(provider.upper() + '_API_KEY', 'fixture-key')
    assert list(lc.stream([])) == ['answer']


@pytest.mark.parametrize('reason', ['length', 'content_filter', 'tool_calls', 'function_call'])
def test_stream_rejects_incomplete_text_without_retry(wire, recorder, monkeypatch, reason):
    wire.set({'stream_chunks': ['partial'], 'finish_reason': reason})
    monkeypatch.setenv('DEEPSEEK_API_KEY', 'fixture-key')
    iterator = lc.stream([])
    assert next(iterator) == 'partial'
    with pytest.raises(lc.LLMError):
        next(iterator)
    assert len(recorder) == 1


def test_stream_accepts_stop_followed_by_usage(wire, monkeypatch):
    wire.set({'stream_chunks': ['complete'], 'finish_reason': 'stop', 'usage_only': True})
    monkeypatch.setenv('DEEPSEEK_API_KEY', 'fixture-key')
    assert list(lc.stream([])) == ['complete']


def test_legacy_stream_without_finish_metadata_is_visible(wire, monkeypatch, caplog):
    wire.set({'stream_chunks': ['legacy answer']})
    monkeypatch.setenv('DEEPSEEK_API_KEY', 'fixture-key')
    with caplog.at_level('WARNING', logger='itlr.llm'):
        assert list(lc.stream([])) == ['legacy answer']
    assert 'completion unverified' in caplog.text


@pytest.mark.parametrize('reason', ['length', 'content_filter', 'tool_calls', 'function_call'])
def test_chat_rejects_incomplete_text(wire, monkeypatch, reason):
    wire.set({'text': 'partial', 'finish_reason': reason})
    monkeypatch.setenv('DEEPSEEK_API_KEY', 'fixture-key')
    monkeypatch.setenv('DEEPSEEK_RETRIES', '1')
    with pytest.raises(lc.LLMError):
        lc.chat([])


@pytest.mark.parametrize('tail', [None, b'not-json', b'[]', b'{"error":"upstream failure"}',
    b'{"done":true,"done_reason":"length"}', b'{"done":"true"}',
    b'{"message":{"content":123}}'])
def test_ollama_rejects_corrupt_or_incomplete_stream(monkeypatch, tail):
    monkeypatch.setattr(lc, 'provider_status', lambda: 'ollama')
    monkeypatch.setattr(lc, 'ollama_model', lambda: 'fixture')
    closed = []
    class Response:
        def __enter__(self):
            return self
        def __exit__(self, *args):
            closed.append(True)
        def __iter__(self):
            yield b'{"message":{"content":"partial"},"done":false}'
            if tail is not None:
                yield tail
    monkeypatch.setattr(lc.urllib.request, 'urlopen', lambda *a, **kw: Response())
    iterator = lc.stream([])
    assert next(iterator) == 'partial'
    with pytest.raises(lc.LLMError):
        next(iterator)
    assert closed == [True]


def test_ollama_completion_and_timeout_contract(monkeypatch):
    monkeypatch.setattr(lc, 'provider_status', lambda: 'ollama')
    monkeypatch.setattr(lc, 'ollama_model', lambda: 'fixture')
    class Response:
        def __enter__(self):
            return iter([b'{"message":{"content":"answer"}}', b'{"done":true,"done_reason":"stop"}'])
        def __exit__(self, *args):
            pass
    monkeypatch.setattr(lc.urllib.request, 'urlopen', lambda *a, **kw: Response())
    assert list(lc.stream([])) == ['answer']
    def timeout(*a, **kw):
        raise TimeoutError('fixture timeout')
    monkeypatch.setattr(lc.urllib.request, 'urlopen', timeout)
    with pytest.raises(lc.LLMError, match='ollama stream failed'):
        list(lc.stream([]))


def test_ollama_continuous_tokens_cannot_bypass_generation_budget(monkeypatch):
    monkeypatch.setattr(lc, 'provider_status', lambda: 'ollama')
    monkeypatch.setattr(lc, 'ollama_model', lambda: 'fixture')
    monkeypatch.setenv('OLLAMA_TIMEOUT', '1')
    ticks = iter([0., .4, .8, 1.2, 1.6])
    monkeypatch.setattr(lc.time, 'monotonic', lambda: next(ticks))
    closed = []

    class Response:
        def __enter__(self):
            return iter([b'{"message":{"content":"piece"},"done":false}'] * 3 +
                        [b'{"done":true,"done_reason":"stop"}'])

        def __exit__(self, *args):
            closed.append(True)

    monkeypatch.setattr(lc.urllib.request, 'urlopen', lambda *a, **kw: Response())
    with pytest.raises(lc.LLMError, match='budget'):
        list(lc.stream([]))
    assert closed == [True]


@pytest.mark.parametrize('payload', [
    {'message': {'content': 'partial'}, 'done': True, 'done_reason': 'length'},
    {'message': {'content': 'partial'}, 'done': False},
    {'message': {'content': 'partial'}},
    {'error': 'upstream failure'},
    {'message': {'content': 123}, 'done': True},
    [],
])
def test_ollama_nonstream_rejects_invalid_completion(monkeypatch, payload):
    monkeypatch.setattr(lc, 'provider_status', lambda: 'ollama')
    monkeypatch.setattr(lc, 'ollama_model', lambda: 'fixture')
    closed = []

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            closed.append(True)

        def read(self):
            return json.dumps(payload).encode()

    monkeypatch.setattr(lc.urllib.request, 'urlopen', lambda *a, **kw: Response())
    with pytest.raises(lc.LLMError):
        lc.chat([])
    assert closed == [True]


def test_ollama_explicit_model_is_not_substituted(monkeypatch):
    monkeypatch.setenv('OLLAMA_MODEL', 'qwen2.5:3b')
    monkeypatch.setattr(lc, 'ollama_reachable', lambda: True)
    lc._OLLAMA_CACHE['models'] = ['qwen2.5:1.5b']
    assert lc.ollama_model() == 'qwen2.5:3b'


@pytest.mark.parametrize('streaming', [False, True])
def test_ollama_applies_history_budget(monkeypatch, streaming):
    monkeypatch.setattr(lc, 'provider_status', lambda: 'ollama')
    messages = [{'role': 'system', 'content': 'system'},
                {'role': 'user', 'content': 'old' * 30},
                {'role': 'user', 'content': 'latest'}]
    received = []

    def generate(msgs, **kwargs):
        received.extend(msgs)
        return iter(['answer']) if streaming else 'answer'

    monkeypatch.setattr(lc, '_stream_ollama' if streaming else 'ollama_chat', generate)
    if streaming:
        assert list(lc.stream(messages, char_budget=20)) == ['answer']
    else:
        assert lc.chat(messages, char_budget=20).text == 'answer'
    assert received == [messages[0], messages[-1]]
    assert len(messages) == 3


def test_usage_tracker_records(wire, monkeypatch):
    wire.set({"text": "hi"})
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk")
    lc.chat([{"role": "user", "content": "h"}], track_usage=("q1",))
    snap = lc.usage_snapshot()
    assert snap["total_calls"] >= 1
    assert snap["total_prompt_tokens"] >= 120
    assert snap["total_completion_tokens"] >= 45


def test_usage_snapshot_does_not_expose_mutable_provider_state():
    lc._record_usage('deepseek', 120, 45)
    snapshot = lc.usage_snapshot()
    snapshot['by_provider']['deepseek']['calls'] = -1
    assert lc.usage_snapshot()['by_provider']['deepseek']['calls'] == 1


def test_mask_key_admin():
    masked = lc.mask_key("sk-abcdef0123456789")
    assert "abcdef" not in masked and "sk-" in masked


def test_trim_messages_keeps_system():
    msgs = ([{"role": "system", "content": "S" * 500}]
            + [{"role": "user", "content": "u" * 900}] * 40)
    trimmed = lc.trim_messages(list(msgs), char_budget=8000)
    assert trimmed[0]["role"] == "system"
    total = sum(len(m["content"]) for m in trimmed)
    assert total <= 8000 + 900 + 100  # dung sai: tin nhắn LƯU TRỮ gần nhất giữ nguyên vẹn


@pytest.mark.parametrize('value', ['nan', 'inf', '-inf', '0', '-1'])
@pytest.mark.parametrize('streaming', [False, True])
def test_timeout_must_be_finite_positive(monkeypatch, value, streaming):
    name = 'DEEPSEEK_STREAM_TIMEOUT_S' if streaming else 'DEEPSEEK_TIMEOUT_S'
    monkeypatch.setenv(name, value)
    with pytest.raises(lc.LLMError, match=name):
        lc.timeout_for('deepseek', streaming)


@pytest.mark.parametrize('streaming', [False, True])
def test_documented_ollama_timeout_overrides_cloud_timeout(monkeypatch, streaming):
    monkeypatch.setenv('OLLAMA_TIMEOUT', '123')
    monkeypatch.setenv('DEEPSEEK_TIMEOUT_S', '5')
    monkeypatch.setenv('DEEPSEEK_STREAM_TIMEOUT_S', '6')
    assert lc.timeout_for('ollama', streaming) == 123


@pytest.mark.parametrize('value', ['invalid', 'nan', 'inf', '0', '-1'])
def test_ollama_timeout_must_be_finite_positive(monkeypatch, value):
    monkeypatch.setenv('OLLAMA_TIMEOUT', value)
    with pytest.raises(lc.LLMError, match='OLLAMA_TIMEOUT'):
        lc.timeout_for('ollama', False)


@pytest.mark.parametrize('mode', ['chat', 'chat-error', 'stream', 'stream-error', 'cancel'])
def test_sdk_resources_close_on_completion_error_and_cancel(monkeypatch, mode):
    monkeypatch.setenv('DEEPSEEK_API_KEY', 'fixture-key')
    monkeypatch.setenv('DEEPSEEK_RETRIES', '1')
    state = {'client_closed': False, 'stream_closed': False}

    class Response:
        def __iter__(self):
            yield types.SimpleNamespace(choices=[types.SimpleNamespace(
                delta=types.SimpleNamespace(content='piece'))])
            if mode == 'stream-error':
                raise RuntimeError('fixture stream failure')

        def close(self):
            state['stream_closed'] = True

    class Client:
        def __init__(self):
            self.chat = types.SimpleNamespace(completions=self)

        def create(self, **kwargs):
            if mode == 'chat-error':
                raise RuntimeError('fixture call failure')
            if kwargs['stream']:
                return Response()
            return types.SimpleNamespace(choices=[types.SimpleNamespace(
                message=types.SimpleNamespace(content='answer'))], usage=None)

        def close(self):
            state['client_closed'] = True

    monkeypatch.setattr(lc, '_make_client', lambda *a: Client())
    if mode.startswith('chat'):
        if mode.endswith('error'):
            with pytest.raises(lc.LLMError):
                lc.chat([])
        else:
            assert lc.chat([]).text == 'answer'
    else:
        iterator = lc.stream([])
        if mode == 'cancel':
            assert next(iterator) == 'piece'
            iterator.close()
        elif mode.endswith('error'):
            with pytest.raises(lc.LLMError):
                list(iterator)
        else:
            assert list(iterator) == ['piece']
        assert state['stream_closed']
    assert state['client_closed']
