"""Freeze offline answer formatting before separating it from orchestration.

Digests preserve complete Unicode Markdown, ordering and whitespace; these are
synthetic contract fixtures, not measures of answer quality.
"""
import hashlib

import pandas as pd
import pytest

from itlr.chatbot import chatbot as cb


def catalog():
    return [dict(item_id=i, title=f"Python {level}", type="Course", level=level,
                 description=f"Python practice {i}", category="Programming",
                 topics=f"Python, topic{i}", instructor="Author", platform="Docs",
                 link=f"https://example.org/{i}")
            for i, level in enumerate(("beginner", "intermediate", "advanced"), 1)]


EXPECTED = {'answer': '5adc8ed2fc80d2db6133c302ea0f3b735898b4f8f4ed7cccce71f9702a507840',
 'recommend': '75cd8aad1b57c6f33ba3456304b54317938887a1b8296f06facc43ae7e53e19f',
 'search': '1df75fc1fbede78d66b6a97c24f10ff6dc19277888591b0840c25ce7752fe51e',
 'compare': '553894f3eb5c702b15dfd1061997a8e3e0d217d32dec44e8b979fe3644df6c9d',
 'learning_path': 'd955b4752e137c044a878daff9bff59ee772fc451d5276cbe03067eec3ba29c3'}


@pytest.mark.parametrize("mode", ["answer", "recommend", "search", "compare", "learning_path"])
def test_template_markdown_contract(mode):
    items = catalog()
    answer = cb.synthesize_answer("Python", [{"item": items[0]}], items[1:], mode,
                                  category="Programming", item_list=pd.DataFrame(items))
    assert hashlib.sha256(answer.encode("utf-8")).hexdigest() == EXPECTED[mode]


def test_empty_sources_contract():
    assert cb.synthesize_answer("Python", [], [], "answer").startswith("T\u00f4i ch\u01b0a")


def test_deduplication_preserves_first_evidence():
    first = {"item_id": 1, "title": "original"}
    assert cb.dedupe_items([first, {"item_id": 1, "title": "duplicate"}]) == [first]
