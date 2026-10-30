"""Regression tests cho các lỗi tìm thấy khi audit retrieval + chatbot (Batch A).

1. Gate off-topic + truy hồi semantic encodes query MỘT lần (dùng lại vector),
   không phải 2–3 lần encode E5 (~100ms CPU mỗi lần).
2. `_quick_resources` giữ điểm cosine hiện hành, không nâng thành confidence.
3. `_quick_resources` giữ hợp đồng lọc: hụt filter trả RỖNG, không trả nguyên
   danh sách bỏ lọc (ngược hợp đồng require_overlap).
4. `_answer_time_estimate` in khoảng tháng đúng chiều thấp→cao.
5. `_answer_next_skill` phân biệt "chưa nêu kỹ năng" với "đồ thị đã cạn".
6. `_answer_admin_stat` từ khoá top không quá khớp "topic".
7. `_answer_interview` chịu được dữ liệu role có roadmap=[].
"""
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

import itlr.chatbot.knowledge_base as kb
from itlr.chatbot.chatbot import EducationalChatbot


class CountingEncoder:
    """Encoder giả: đếm số lần encode và trả vector cố định."""

    def __init__(self, vec=(1.0, 0.0)):
        self.calls = []
        self._vec = np.asarray(vec, dtype="float32")

    def encode(self, texts, **kwargs):
        self.calls.extend(list(texts))
        return np.tile(self._vec, (len(texts), 1))


def build_service(encoder, texts=("docker networks", "docker volumes", "python lists"),
                  vectors=((1.0, 0.0), (0.8, 0.6), (0.0, 1.0)),
                  platforms=("Docs", "Coursera", "Coursera")):
    from itlr.retrieval.service import RetrievalService
    from itlr.core.chunks import ChunkIndex
    rows = [dict(item_id=i + 1, chunk_idx=0, chunk_text=t) for i, t in enumerate(texts)]
    items = pd.DataFrame([
        dict(item_id=i + 1, type='Tài liệu', title=f'Item {i + 1}', category='DevOps',
             description=f'Về {t}', topics=t, instructor='', platform=platforms[i],
             link='https://example.org', level='Cơ bản')
        for i, t in enumerate(texts)
    ])
    vecs = np.asarray(vectors, dtype='float32')[:len(texts)]
    return RetrievalService(ChunkIndex(rows, vecs), items, encoder, 'query: ')


def chatbot_stub(service):
    return SimpleNamespace(embed_model=object(), search_index={'retrieval': service})


class BotHarness(EducationalChatbot):
    """Test harness: bỏ __init__ nặng, chỉ wire các thuộc tính handler cần."""

    def __init__(self, item_list=None, embed_model=None, search_index=None, categories=()):
        self.item_list = item_list
        self.embed_model = embed_model
        self.search_index = search_index
        self.query_prefix = ''
        self.ann = None
        self.reranker = None
        self.retrieval_model = None
        self.rag = SimpleNamespace(categories=list(categories))


def count_encodes(enc):
    return len(enc.calls)


# ---------------------------------------------------------------- single-encode

def test_service_encodes_once_when_vector_shared():
    enc = CountingEncoder()
    svc = build_service(enc)
    vec = svc.vector('docker')
    gate = svc.relevance('docker', vector=vec)
    hits = svc.search('docker', vector=vec)
    assert count_encodes(enc) == 1, f"encoded {enc.calls} times"
    assert gate == pytest.approx(1.0)
    assert hits


def test_chatbot_gate_then_retrieve_encodes_once():
    enc = CountingEncoder()
    svc = build_service(enc)
    bot = chatbot_stub(svc)
    vec = svc.vector('docker')
    EducationalChatbot._is_off_topic(bot, 'docker', vector=vec)
    EducationalChatbot._semantic_retrieve(bot, 'docker', vector=vec, top_k=2)
    assert count_encodes(enc) == 1, f"encoded {enc.calls} times"


def test_shared_vector_without_param_still_works():
    """Backward compatible: không truyền vector vẫn encode như cũ."""
    enc = CountingEncoder()
    svc = build_service(enc)
    assert svc.relevance('docker') == pytest.approx(1.0)
    assert svc.search('docker')[0]['chunk_id']
    assert len(enc.calls) == 2


def test_prepare_reuses_encoding_through_type_filter_fallback(monkeypatch):
    from itlr.chatbot import chatbot as module

    enc = CountingEncoder()
    svc = build_service(enc)
    bot = BotHarness(embed_model=enc, search_index={'retrieval': svc})
    bot.vocab = frozenset()
    bot.rag.detect_category = lambda query: None
    monkeypatch.setattr(module, 'understand_query', lambda *a: {
        'corrected': 'docker', 'display': 'docker', 'corrections': []})
    monkeypatch.setattr(module, 'route_intent', lambda *a: (None, {}))
    monkeypatch.setattr(module, '_route_multi', lambda *a: None)
    monkeypatch.setattr(module, '_llm_available', lambda: False)
    monkeypatch.setattr(module, 'intent_note', lambda *a: '')
    monkeypatch.setattr(module, 'concept_overview_block', lambda *a: '')
    # Requested type is absent: exercise gate + empty filtered retrieval + retry.
    monkeypatch.setattr(module, 'detect_item_type', lambda *a: 'Khóa học')
    kind, result = bot._prepare('docker')
    assert kind == 'final' and result['sources']
    assert len(enc.calls) == 1


# ---------------------------------------------------- _quick_resources contract

def test_quick_resources_preserves_cosine_scores():
    svc = build_service(CountingEncoder([0.8, 0.6]))
    bot = chatbot_stub(svc)
    items = EducationalChatbot._quick_resources(bot, 'docker networks', k=3)
    assert items, "expected retrieval hits"
    scores = [it['score'] for it in items]
    assert sorted(scores) == pytest.approx([60.0, 80.0, 100.0])


def test_quick_resources_returns_empty_when_filter_cannot_match():
    svc = build_service(CountingEncoder(), texts=("docker networks", "docker volumes"),
                        vectors=((1.0, 0.0), (0.9, 0.43589)), platforms=("Coursera", "Coursera"))
    bot = BotHarness(item_list=pd.DataFrame(), search_index={'retrieval': svc})
    out = EducationalChatbot._quick_resources(bot, 'docker networks', k=2, filters={'free': True})
    assert out == [], "filter hụt phải trả rỗng, không trả nguyên danh sách bỏ lọc"


def test_quick_resources_positive_filter_still_applies():
    svc = build_service(CountingEncoder(), texts=("docker networks", "docker volumes"),
                        vectors=((1.0, 0.0), (0.9, 0.43589)), platforms=("Docs", "Coursera"))
    bot = BotHarness(item_list=pd.DataFrame(), search_index={'retrieval': svc})
    out = EducationalChatbot._quick_resources(bot, 'docker networks', k=3,
                                              filters={'platform': 'coursera'})
    assert out and all('coursera' in it.get('platform', '').lower() for it in out)


# ------------------------------------------------------------------- handlers

def test_time_estimate_month_range_is_low_to_high():
    bot = SimpleNamespace()
    career = next(iter(kb.CAREERS))
    result = EducationalChatbot._answer_time_estimate(bot, {'career': career}, 'q', 'm', [])
    import re
    m = re.search(r"khoảng (\d+)[–—-](\d+) tháng", result['response'])
    assert m, "missing month range in weekly-line"
    assert int(m.group(1)) <= int(m.group(2)), result['response']


def test_next_skill_distinguishes_exhausted_graph(monkeypatch):
    svc = build_service(CountingEncoder())
    bot = BotHarness(search_index={'retrieval': svc})
    result = EducationalChatbot._answer_next_skill(bot, {'known': ['TypeScript']}, 'q', 'q', [])
    assert 'Bạn chưa nêu kỹ năng đã học' not in result['response'], result['response']


def test_next_skill_unstated_message_kept_when_nothing_known():
    svc = build_service(CountingEncoder())
    bot = BotHarness(search_index={'retrieval': svc})
    result = EducationalChatbot._answer_next_skill(bot, {'known': []}, 'q', 'q', [])
    assert 'Bạn chưa nêu kỹ năng đã học' in result['response'], result['response']


def test_admin_stat_top_word_not_overmatched():
    df = pd.DataFrame([
        dict(item_id=i + 1, type='Khóa học' if i % 3 else 'Tài liệu',
             category='Docker', level='Cơ bản')
        for i in range(9)
    ])
    bot = SimpleNamespace(item_list=df, rag=SimpleNamespace(categories=[]))
    result = EducationalChatbot._answer_admin_stat(bot, {'raw': 'thống kê về topic AI'},
                                                   'q', 'm', [])
    assert 'Top chuyên mục' not in result['response'], result['response']
    assert 'Thống kê' in result['response']


def test_admin_stat_top_word_still_matches():
    df = pd.DataFrame([
        dict(item_id=i + 1, type='Khóa học', category=f'Cat{i}', level='')
        for i in range(4)
    ])
    bot = SimpleNamespace(item_list=df, rag=SimpleNamespace(categories=[]))
    result = EducationalChatbot._answer_admin_stat(bot, {'raw': 'top chuyên mục'},
                                                   'q', 'm', [])
    assert 'Top chuyên mục' in result['response'], result['response']


def test_interview_tolerates_empty_roadmap(monkeypatch):
    monkeypatch.setattr(kb, 'ROLES', {
        'qa': {'name': 'QA', 'interview': ['Câu hỏi 1?'], 'roadmap': []},
    })
    bot = BotHarness(item_list=pd.DataFrame(
        [dict(item_id=1, type='Tài liệu', title='QA', category='QA', description='qa',
              topics='qa', instructor='', platform='Docs', link='https://e.org', level='')
        ]), search_index={'retrieval': build_service(CountingEncoder())})
    result = EducationalChatbot._answer_interview(bot, {'role': 'qa'}, 'q', 'm', [])
    assert result and 'Câu hỏi 1' in result['response']
