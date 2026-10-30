"""Citation identity is checked; semantic entailment is deliberately not claimed."""
import pytest
from itlr.chatbot import chatbot as cb


def prepared(monkeypatch):
    bot = object.__new__(cb.EducationalChatbot)
    bot.item_list = None
    source = {"item": {"item_id": 5001, "title": "Python", "origin": "crawl:devto", "link": "https://dev.to/python", "description": "Python uses indentation."}, "document": "Python uses indentation.", "excerpt": "Python uses indentation.", "evidence_kind": "source_text", "chunk_id": "5001:0"}
    p = {"sources": [source], "recommendations": [], "all_recs": [], "mode": "answer", "prefix": "", "sys_prompt": "SYS", "llm_message": "q", "history": []}
    monkeypatch.setattr(bot, "_prepare", lambda *args: ("generate", p))
    return bot


def test_unknown_citation_rejected(monkeypatch):
    bot = prepared(monkeypatch)
    monkeypatch.setattr(cb, "try_llm_response", lambda *a, **kw: "Fabricated [item_id:9999]")
    result = bot.chat("q")
    assert "Fabricated" not in result["response"]
    assert result["generation_mode"] == "insufficient_evidence"
    assert result["citation_validation"]["invalid_ids"] == [9999]


def test_sources_and_pending_meta_precede_generation(monkeypatch):
    bot = prepared(monkeypatch)
    invoked = []
    def tokens(*a, **kw):
        invoked.append(True)
        yield "Python "
        yield "[item_id:5001]"
    monkeypatch.setattr(cb, "try_llm_response_stream", tokens)
    events = bot.chat_stream("q")
    event, data = next(events)
    assert event == "sources"
    assert data[0]["excerpt"] == "Python uses indentation."
    assert data[0]["url"] == "https://dev.to/python"
    assert not invoked
    assert next(events)[0] == "meta"
    assert not invoked
    rest = list(events)
    assert rest[0] == ("text", "Python ")
    assert rest[-1][0] == "final"
    assert rest[-1][1]["citation_validation"]["status"] == "valid"
    assert rest[-1][1]["citation_validation"]["semantic_grounding"] == "not_verified"


@pytest.mark.parametrize("answer", ["No citation", "Bad [item_id:9999]", "Bad [item_id:abc]"])
def test_stream_final_replaces_unsupported_answer(monkeypatch, answer):
    bot = prepared(monkeypatch)
    monkeypatch.setattr(cb, "try_llm_response_stream", lambda *a, **kw: iter([answer]))
    result = list(bot.chat_stream("q"))[-1][1]
    assert result["generation_mode"] == "insufficient_evidence"
    assert answer not in result["response"]


def test_synthetic_source_not_real_evidence(monkeypatch):
    bot = prepared(monkeypatch)
    kind, p = bot._prepare("q")
    p["sources"][0]["item"]["origin"] = "legacy:synthetic"
    monkeypatch.setattr(cb, "try_llm_response", lambda *a, **kw: "Assertion [item_id:5001]")
    result = bot.chat("q")
    assert result["generation_mode"] == "insufficient_evidence"
    assert result["sources"][0]["evidence_kind"] == "synthetic"


@pytest.mark.parametrize('streaming', [False, True])
@pytest.mark.parametrize('kind', ['final', 'generate'])
def test_public_recommendations_are_json_safe_without_full_source_text(monkeypatch, streaming, kind):
    import json

    bot = prepared(monkeypatch)
    _, p = bot._prepare('q')
    item = {'item_id': 5001, 'title': 'Python', 'source_updated_at': float('nan'),
            'full_text': 'private internal snapshot body'}
    if kind == 'final':
        p = dict(response='hello', intent='greeting', sources=[], recommendations=[item])
    else:
        p['all_recs'] = [item]
    monkeypatch.setattr(bot, '_prepare', lambda *a: (kind, p))
    monkeypatch.setattr(cb, 'try_llm_response', lambda *a, **kw: 'Python [item_id:5001]')
    monkeypatch.setattr(cb, 'try_llm_response_stream', lambda *a, **kw: iter(['Python [item_id:5001]']))
    if streaming:
        events = list(bot.chat_stream('q'))
        for _, event in events:
            json.dumps(event, allow_nan=False)
        result = events[-1][1]
    else:
        result = bot.chat('q')
        json.dumps(result, allow_nan=False)
    assert result['recommendations'][0]['source_updated_at'] is None
    assert 'full_text' not in result['recommendations'][0]


def test_stream_failure_after_token_never_finalizes_partial(monkeypatch):
    from itlr.chatbot import llm_client
    bot = prepared(monkeypatch)
    def broken(*a, **kw):
        yield "Partial [item_id:5001]"
        raise llm_client.LLMError("secret upstream detail")
    monkeypatch.setattr(cb, "try_llm_response_stream", broken)
    events = list(bot.chat_stream("q"))
    result = events[-1][1]
    assert result["generation_error"] == "generation_failed"
    assert "Partial" not in result["response"]
    assert "secret" not in str(result)


def test_metadata_is_not_source_text(monkeypatch):
    bot = prepared(monkeypatch)
    _, p = bot._prepare("q")
    p["sources"][0].pop("evidence_kind")
    monkeypatch.setattr(cb, "try_llm_response", lambda *a, **kw: "Assertion [item_id:5001]")
    assert bot.chat("q")["generation_mode"] == "insufficient_evidence"


def test_api_preserves_sources_and_early_events(monkeypatch):
    from itlr.api import server
    bot = prepared(monkeypatch)
    monkeypatch.setattr(cb, "try_llm_response", lambda *a, **kw: "Python [item_id:5001]")
    monkeypatch.setattr(cb, "try_llm_response_stream", lambda *a, **kw: iter(["Python ", "[item_id:5001]"]))
    monkeypatch.setattr(server, "_engine", lambda: bot)
    result = server.api_chat(server.ChatReq(message="q"))
    assert result["sources"][0]["chunk_id"] == "5001:0"
    import json
    monkeypatch.setattr(server, "StreamingResponse", lambda body, **kwargs: body)
    frames = [json.loads(frame[6:]) for frame in server.api_chat_stream(server.ChatReq(message="q"))]
    assert [f["type"] for f in frames] == ["sources", "meta", "text", "text", "final", "done"]
    assert frames[-2]["response"] == result["response"]


def test_v3_generation_requires_chunk_reference(monkeypatch):
    bot=prepared(monkeypatch)
    bot.search_index={'retrieval':object()}
    monkeypatch.setattr(cb,'try_llm_response',lambda *a,**kw:'Python [item_id:5001]')
    assert bot.chat('q')['generation_mode']=='insufficient_evidence'


def test_v3_generation_accepts_selected_chunk(monkeypatch):
    bot=prepared(monkeypatch)
    bot.search_index={'retrieval':object()}
    monkeypatch.setattr(cb,'try_llm_response',lambda *a,**kw:'Python [item_id:5001] [chunk_id:5001:0]')
    assert bot.chat('q')['generation_mode']=='llm'
