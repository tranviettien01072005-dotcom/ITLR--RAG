"""Hợp đồng pipeline chatbot sau refactor (2026-11-02).

Ghim từng giai đoạn qua public behavior (_prepare / chat_stream / achat_stream):
greeting, cổng off-topic, multi-intent không LLM, handler trả None, extractive final,
CF fallback, evidence selection schema, và finalize stream (empty/error semantics).
Không gọi LLM/API thật; module function được monkeypatch để deterministic.
"""
import asyncio

import pandas as pd
import pytest

from itlr.chatbot import chatbot as cb
from itlr.chatbot.citations import INSUFFICIENT_EVIDENCE
from itlr.chatbot.chatbot import OFF_TOPIC_MESSAGE

from test_chatbot_retrieval_fixes import (  # noqa: F401  (dùng chung fixture nhỏ)
    BotHarness, CountingEncoder, build_service,
)


def patched(monkeypatch, understand=None, route=None, multi=None, llm=None, note=None):
    monkeypatch.setattr(cb, 'understand_query', understand or (lambda *a: {
        'corrected': 'docker', 'display': 'docker', 'corrections': []}))
    monkeypatch.setattr(cb, 'route_intent', route or (lambda *a: (None, {})))
    monkeypatch.setattr(cb, '_route_multi', lambda *a: multi)
    monkeypatch.setattr(cb, '_llm_available', (lambda: False) if llm is None else (lambda: llm))
    monkeypatch.setattr(cb, 'intent_note', note or (lambda *a: ''))
    monkeypatch.setattr(cb, 'concept_overview_block', lambda *a: '')


def pipeline_harness(enc, svc):
    """BotHarness sẵn sàng chạy _prepare: vocab trống bỏ qua understand_query thật."""
    bot = BotHarness(embed_model=enc, search_index={'retrieval': svc} if svc else None)
    bot.vocab = frozenset()
    return bot


# ------------------------------------------------------------------- greeting

def test_greeting_returns_welcome_without_any_encoding(monkeypatch):
    enc = CountingEncoder()
    bot = pipeline_harness(enc, build_service(enc))
    kind, result = bot._prepare('xin chào')
    assert kind == 'final' and result['intent'] == 'greeting'
    assert result['response'] == cb.EducationalChatbot.WELCOME_MESSAGE
    assert result['sources'] == [] and result['recommendations'] == []
    assert enc.calls == [], 'greeting phải trả lời trước khi encode/ retrieve'


# ------------------------------------------------------------------ off-topic

def test_off_topic_query_refused_with_single_encode(monkeypatch):
    # Catalog chỉ nói nấu ăn; query nấu ăn phải bị cổng chặn, 1 lần encode duy nhất.
    enc = CountingEncoder(vec=(0., 1.))
    svc = build_service(enc, texts=('công thức xào', 'món tráng miệng'),
                        vectors=((1., 0.), (.9, .44)))
    bot = pipeline_harness(enc, svc)
    bot.rag.detect_category = lambda query: None
    kind, result = bot._prepare('công thức phở nấu sao')
    assert kind == 'final' and result['intent'] == 'off_topic'
    assert result['response'] == OFF_TOPIC_MESSAGE
    assert result['sources'] == [] and result['recommendations'] == []
    assert len(enc.calls) == 1, f'gate tái dùng vector, encoded {enc.calls}'


# -------------------------------------------------------------- intent stages

def test_multi_intent_composes_without_llm(monkeypatch):
    df = pd.DataFrame([dict(item_id=1, type='Tài liệu', category='DevOps', level='Cơ bản'),
                       dict(item_id=2, type='Khóa học', category='AI', level='')])
    bot = pipeline_harness(None, build_service(CountingEncoder()))
    bot.item_list = df
    multi = [('admin_stat', {'raw': 'thống kê tổng'}, 'câu 1'),
             ('admin_stat', {'raw': 'top chuyên mục'}, 'câu 2')]
    patched(monkeypatch, multi=multi, llm=False)
    kind, result = bot._prepare('thống kê tổng và top chuyên mục')
    assert kind == 'final' and result['intent'] == 'multi'
    assert result['response'].count('## 📊') >= 2
    assert '\n\n---\n\n' in result['response']


def test_admin_stat_finalizes_with_note_prefix_without_llm(monkeypatch):
    df = pd.DataFrame([dict(item_id=1, type='Tài liệu', category='DevOps', level='Cơ bản')])
    bot = pipeline_harness(None, build_service(CountingEncoder()))
    bot.item_list = df
    patched(monkeypatch, route=lambda *a: ('admin_stat', {'raw': 'thống kê tài liệu'}),
            llm=False, note=lambda *a: '[Chú ý] ')
    kind, result = bot._prepare('thống kê tài liệu')
    assert kind == 'final' and result['intent'] == 'admin_stat'
    assert result['response'].startswith('[Chú ý] ')


def test_handler_returning_none_falls_through_to_retrieval(monkeypatch):
    enc = CountingEncoder()
    bot = pipeline_harness(enc, build_service(enc))
    # salary với role ngoài bảng ROLES → handler None → pipeline chạy tiếp retrieval.
    patched(monkeypatch, route=lambda *a: ('salary', {'role': 'unknown_role'}), llm=False)
    kind, result = bot._prepare('lương unknown_role')
    assert kind == 'final' and result['generation_mode'] == 'extractive'
    assert result['sources'], 'phải có nguồn retrieval sau khi handler bỏ qua'


# --------------------------------------------------------------- final/LLM ctx

def test_extractive_final_has_inline_citations_valid(monkeypatch):
    enc = CountingEncoder()
    bot = pipeline_harness(enc, build_service(enc))
    patched(monkeypatch, llm=False)
    kind, result = bot._prepare('docker')
    assert kind == 'final' and result['generation_mode'] == 'extractive'
    assert result['generation_error'] is None
    assert '[item_id:' in result['response'] and '[chunk_id:' in result['response']
    assert result['citation_validation']['status'] == 'valid'


def test_cf_fallback_recommendations_when_no_chunk_index(monkeypatch):
    bot = pipeline_harness(None, None)
    bot.search_index = {'embeddings': [[1., 0.]], 'chunk_meta': []}
    sources = [{'item': {'item_id': 1}, 'excerpt': 'docker', 'chunk_id': '1:0',
                'evidence_kind': 'source_text'}]
    bot.rag.build_context = lambda *a, **kw: ('ctx', sources)
    bot.rag.get_recommendations = lambda *a, **kw: [
        {'item_id': 9, 'title': 'Gợi ý', 'score': 3.0}]
    patched(monkeypatch, llm=False)
    kind, result = bot._prepare('docker')
    assert kind == 'final'
    scores = [r.get('score') for r in result['recommendations'] if r.get('item_id') == 9]
    assert scores and all(s <= 100.0 for s in scores), 'điểm CF phải hiệu chỉnh 0-100'


def test_llm_context_builds_evidence_selection_schema(monkeypatch):
    enc = CountingEncoder()
    bot = pipeline_harness(enc, build_service(enc))
    patched(monkeypatch, llm=True)
    kind, ctx = bot._prepare('docker')
    assert kind == 'generate' and ctx['evidence_selection'] is True
    enum = ctx['output_schema']['items']['enum']
    assert enum == ['1:0', '2:0', '3:0']
    assert ctx['llm_message'] == 'docker'
    assert len(ctx['sources']) <= 5


def test_llm_context_without_source_text_is_final_insufficient(monkeypatch):
    enc = CountingEncoder()
    bot = pipeline_harness(enc, build_service(enc))
    patched(monkeypatch, llm=True)
    bot._semantic_retrieve = lambda *a, **kw: []
    kind, result = bot._prepare('docker')
    assert kind == 'final' and result['generation_mode'] == 'insufficient_evidence'
    assert result['generation_error'] == 'no_source_text'
    assert result['response'] == INSUFFICIENT_EVIDENCE


# ------------------------------------------------- llm-aware routing branches

def test_definition_intent_demoted_to_llm_when_available(monkeypatch):
    enc = CountingEncoder()
    bot = pipeline_harness(enc, build_service(enc))
    patched(monkeypatch, llm=True)
    kind, ctx = bot._prepare('docker')
    assert kind == 'generate', 'definition có LLM phải qua LLM, không dùng template'
    assert 'evidence_selection' in ctx and ctx['sources']


def test_multi_intent_demoted_to_llm_when_available(monkeypatch):
    enc = CountingEncoder()
    bot = pipeline_harness(enc, build_service(enc))
    multi = [('admin_stat', {'raw': 'a'}, 'câu 1'), ('admin_stat', {'raw': 'b'}, 'câu 2')]
    patched(monkeypatch, multi=multi, llm=True)
    kind, ctx = bot._prepare('thống kê a và b')
    assert kind == 'generate', 'multi có LLM phải qua LLM'
    assert 'evidence_selection' in ctx


def test_handler_result_becomes_kb_block_before_llm_generation(monkeypatch):
    # interview có role thật + LLM: kết quả handler thành KB block, pipeline tiếp sang LLM.
    enc = CountingEncoder()
    bot = pipeline_harness(enc, build_service(enc))
    patched(monkeypatch, route=lambda *a: ('interview', {'role': 'frontend'}), llm=True)
    kind, ctx = bot._prepare('phỏng vấn frontend')
    assert kind == 'generate'
    assert 'evidence_selection' in ctx


def test_llm_context_legacy_prompt_when_no_chunk_index(monkeypatch):
    bot = pipeline_harness(CountingEncoder(), None)
    bot.search_index = {'embeddings': [[1., 0.]], 'chunk_meta': []}
    source = {'item': {'item_id': 1, 'origin': 'crawl:example.org', 'link': 'https://ex.org',
                       'description': 'docker'},
               'excerpt': 'Docker container cơ bản', 'chunk_id': '1:0', 'evidence_kind': 'source_text'}
    bot._semantic_retrieve = lambda *a, **kw: [source]
    bot.rag.get_recommendations = lambda *a, **kw: []
    patched(monkeypatch, llm=True)
    kind, ctx = bot._prepare('docker')
    assert kind == 'generate' and 'evidence_selection' not in ctx
    assert 'Đoạn trích nguồn' in ctx['sys_prompt'] and '1:0' in ctx['sys_prompt']


def test_explanation_query_forces_answer_mode_in_gather(monkeypatch):
    enc = CountingEncoder()
    bot = pipeline_harness(enc, build_service(enc))
    patched(monkeypatch, llm=False)
    original_mode = cb.detect_response_mode

    def spy(text):
        assert original_mode(text) in {'search', 'answer'}
        return 'search'

    monkeypatch.setattr(cb, 'detect_response_mode', spy)
    kind, result = bot._prepare('docker dùng để làm gì')
    assert kind == 'final', '_is_explanation_query phải ép mode answer'
    assert result['intent'] == 'answer'


# ---------------------------------------------------- kb_block điều khiển want_llm

def test_handler_kb_block_promotes_search_mode_to_llm(monkeypatch):
    enc = CountingEncoder()
    bot = pipeline_harness(enc, build_service(enc))
    # mode 'search' vốn KHÔNG want_llm; chỉ kb_block từ handler career_guidance mới bật.
    monkeypatch.setattr(cb, 'detect_response_mode', lambda text: 'search')
    patched(monkeypatch, route=lambda *a: ('career_guidance', {}), llm=True)
    kind, ctx = bot._prepare('gợi ý ngành nghề hợp với mình')
    assert kind == 'generate', 'kb_block có LLM phải đưa pipeline qua LLM'
    assert 'evidence_selection' in ctx


def test_search_mode_without_kb_block_stays_extractive_even_with_llm(monkeypatch):
    enc = CountingEncoder()
    bot = pipeline_harness(enc, build_service(enc))
    monkeypatch.setattr(cb, 'detect_response_mode', lambda text: 'search')
    patched(monkeypatch, route=lambda *a: ('salary', {'role': 'unknown_role'}), llm=True)
    kind, result = bot._prepare('lương unknown_role')
    assert kind == 'final' and result['generation_mode'] == 'extractive', \
        'không kb_block không bao giờ muốn LLM ở mode search'


# ------------------------------------------------------------------- streams

def stream_p():
    """p cố định cho stream legacy (không evidence_selection) và selective."""
    source = {"item": {"item_id": 5001, "title": "Python", "origin": "crawl:devto",
                       "link": "https://dev.to/python", "description": "Python đơn giản."},
              "chunk_id": "5001:0", "excerpt": "Python uses indentation.",
              "evidence_kind": "source_text"}
    selective = {"sources": [source], "all_recs": [], "mode": "answer",
                 "sys_prompt": "SYS", "llm_message": "q", "history": [],
                 "evidence_selection": True}
    legacy = dict(selective)
    legacy.pop("evidence_selection")
    return legacy, selective


def test_stream_selective_silent_until_collection_then_tail_before_final(monkeypatch):
    _, selective = stream_p()
    bot = object.__new__(cb.EducationalChatbot)
    bot.search_index = {"retrieval": object()}
    monkeypatch.setattr(bot, "_prepare", lambda *a: ("generate", selective))
    monkeypatch.setattr(cb, "try_llm_response_stream",
                        lambda *a, **kw: iter(['["5001:0"]']))
    events = list(bot.chat_stream("q"))
    assert events[-1][0] == "final"


def test_stream_selective_tail_text_is_final_bound_quote(monkeypatch):
    _, selective = stream_p()
    bot = object.__new__(cb.EducationalChatbot)
    bot.search_index = {"retrieval": object()}
    monkeypatch.setattr(bot, "_prepare", lambda *a: ("generate", selective))
    monkeypatch.setattr(cb, "try_llm_response_stream",
                        lambda *a, **kw: iter(['["5001:0"]']))
    events = list(bot.chat_stream("q"))
    final = events[-1]
    text_pos = next(i for i, (k, _) in enumerate(events) if k == "text")
    assert text_pos == len(events) - 2 and final[0] == "final"
    assert events[text_pos][1] == final[1]["response"]


def test_stream_ended_with_no_chunks_marks_generation_unavailable(monkeypatch):
    legacy, _ = stream_p()
    bot = object.__new__(cb.EducationalChatbot)
    bot.search_index = {"retrieval": object()}
    monkeypatch.setattr(bot, "_prepare", lambda *a: ("generate", legacy))
    monkeypatch.setattr(cb, "try_llm_response_stream", lambda *a, **kw: iter([]))
    events = list(bot.chat_stream("q"))
    result = events[-1][1]
    assert result["generation_error"] == "generation_unavailable"
    assert result["generation_mode"] == "insufficient_evidence"
    assert not [e for e, _ in events if e == "text"]


def test_stream_raises_before_token_keeps_generation_failed_semantics(monkeypatch):
    """Ghim semantics: lỗi TRƯỚC token đầu → error 'generation_failed' (không nhảy sang
    'generation_unavailable') — finalize phải giữ error đã có và không tự ý đổi."""
    legacy, _ = stream_p()
    bot = object.__new__(cb.EducationalChatbot)
    bot.search_index = {"retrieval": object()}
    monkeypatch.setattr(bot, "_prepare", lambda *a: ("generate", legacy))
    def broken(*a, **kw):
        raise RuntimeError("upstream")
        yield  # pragma: no cover
    monkeypatch.setattr(cb, "try_llm_response_stream", broken)
    events = list(bot.chat_stream("q"))
    result = events[-1][1]
    assert result["generation_error"] == "generation_failed"
    assert result["generation_mode"] == "insufficient_evidence"


def test_stream_skips_empty_chunks_without_breaking_semantics(monkeypatch):
    legacy, _ = stream_p()
    bot = object.__new__(cb.EducationalChatbot)
    bot.search_index = {"retrieval": object()}
    monkeypatch.setattr(bot, "_prepare", lambda *a: ("generate", legacy))
    monkeypatch.setattr(cb, "try_llm_response_stream",
                        lambda *a, **kw: iter(["Python ", "", "uses indentation. [item_id:5001] [chunk_id:5001:0]"]))
    events = list(bot.chat_stream("q"))
    texts = [d for e, d in events if e == "text"]
    assert "" not in texts and len(texts) == 2
    assert events[-1][1]["citation_validation"]["status"] == "valid"


@pytest.mark.parametrize("asynchronous", [False, True], ids=["sync", "async"])
def test_async_and_sync_stream_finalize_the_same(monkeypatch, asynchronous):
    legacy, _ = stream_p()
    bot = object.__new__(cb.EducationalChatbot)
    bot.search_index = {"retrieval": object()}
    monkeypatch.setattr(bot, "_prepare", lambda *a: ("generate", legacy))
    if asynchronous:
        from itlr.chatbot import llm_adapter

        async def tokens(*_args, **_kwargs):
            for piece in ("Python ", "uses indentation. [item_id:5001] [chunk_id:5001:0]"):
                yield piece

        monkeypatch.setattr(llm_adapter, "try_llm_response_astream", tokens)

        async def collect():
            return [event async for event in bot.achat_stream("q")]

        events = asyncio.run(collect())
    else:
        monkeypatch.setattr(cb, "try_llm_response_stream",
                            lambda *a, **kw: iter(["Python ",
                                                   "uses indentation. [item_id:5001] [chunk_id:5001:0]"]))
        events = list(bot.chat_stream("q"))
    result = events[-1][1]
    assert events[-1][0] == "final"
    assert result["generation_mode"] == "llm"
    assert result["citation_validation"]["status"] == "valid"
    assert result["response"] == "Python uses indentation. [item_id:5001] [chunk_id:5001:0]"
