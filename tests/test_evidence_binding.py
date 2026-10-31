"""Selection binds exact passages; these fixtures are not human quality labels."""
import asyncio
import json

import pytest

from test_api_integration import client as client  # noqa: F401

from itlr.chatbot import chatbot as cb
from itlr.chatbot.citations import INSUFFICIENT_EVIDENCE


# Exact PSF-licensed passages captured by citation-support-spotcheck.json.
# Source: https://docs.python.org/3/library/contextlib.html, crawl 2026-10-29.
EXCERPTS = {0: 'contextlib — Utilities for with -statement contexts ¶ Source code: Lib/contextlib.py This '
    'module provides utilities for common tasks involving the with statement. For more information '
    'see also Context Manager Types and With Statement Context Managers . Utilities ¶ Functions '
    'and classes provided: class contextlib. AbstractContextManager ¶ An abstract base class for '
    'classes that implement __enter__() and __exit__() . A default implementation for __enter__() '
    'is provided which returns self while __exit__() is an abstract method which by default '
    'returns None . See also the definition of Context Manager Types . Added in version 3.6. An '
    'abstract base class for classes that implement __aenter__() and __aexit__() . A default '
    'implementation for __aenter__() is provided which returns self while __aexit__() is an '
    'abstract method which by default returns None . See also the definition of',
 7: 'led when the with block is exited. Note Most types managing resources support the context '
    'manager protocol, which closes thing on leaving the with statement. As such, closing() is '
    'most useful for third party types that don’t support context managers. This example is purely '
    'for illustration purposes, as urlopen() would normally be used in a context manager. '
    'contextlib. aclosing ( thing ) ¶ Return an async context manager that calls the aclose() '
    'method of thing upon completion of the block. This is basically equivalent to: from '
    'contextlib import asynccontextmanager @asynccontextmanager async def aclosing ( thing ): try '
    ': yield thing finally : await thing . aclose () Significantly, aclosing() supports '
    'deterministic cleanup of async generators when they happen to exit early by break or an '
    'exception. For example: from contextlib import aclosing async with aclosing ( my_generator '
    '()) as values',
 14: 'ke generators, where the program execution is temporarily relinquished – unless explicitly '
     'desired, you should not yield when this context manager is active. This is a simple wrapper '
     'around chdir() , it changes the current working directory upon entering and restores the old '
     'one on exit. This context manager is reentrant . Added in version 3.11. class contextlib. '
     'ContextDecorator ¶ A base class that enables a context manager to also be used as a '
     'decorator. Context managers inheriting from ContextDecorator have to implement __enter__() '
     'and __exit__() as normal. __exit__ retains its optional exception handling even when used as '
     'a decorator. ContextDecorator is used by @contextmanager , so you get this functionality '
     'automatically. Example of ContextDecorator : from contextlib import ContextDecorator class '
     "mycontext ( ContextDecorator ): def __enter__ ( self ): print ( 'Starting' ) return"}
UNSUPPORTED_COMPLETION = "Context manager Python triển khai hai phương thức là __enter__() và __exit__() khi vào và thoát with. [item_id:5061] [chunk_id:5061:7]"


def prepared(monkeypatch):
    bot = object.__new__(cb.EducationalChatbot)
    bot.search_index = {"retrieval": object()}
    sources = [{"item": {"item_id": 5061, "title": "contextlib",
                         "origin": "crawl:python-official",
                         "link": "https://docs.python.org/3/library/contextlib.html"},
                "chunk_id": f"5061:{index}", "excerpt": excerpt,
                "evidence_kind": "source_text"} for index, excerpt in EXCERPTS.items()]
    p = {"sources": sources, "all_recs": [], "mode": "answer", "sys_prompt": "SYS",
         "llm_message": "Context manager Python triển khai hai phương thức nào?",
         "history": [], "evidence_selection": True}
    monkeypatch.setattr(bot, "_prepare", lambda *_args: ("generate", p))
    return bot, p


def test_real_wrong_passage_paraphrase_is_not_accepted_as_selected_evidence(monkeypatch):
    bot, p = prepared(monkeypatch)
    assert "__enter__()" not in EXCERPTS[7] and "__exit__()" not in EXCERPTS[7]
    result = bot._generated_result(UNSUPPORTED_COMPLETION, p)
    assert result["generation_mode"] == "insufficient_evidence"
    assert result["response"] == INSUFFICIENT_EVIDENCE


@pytest.mark.parametrize("selected", [["5061:0"], ["5061:7"], ["5061:14"], ["5061:0", "5061:14"]])
def test_valid_selection_quotes_exact_bound_sources(monkeypatch, selected):
    bot, p = prepared(monkeypatch)
    result = bot._generated_result(json.dumps(selected), p)
    assert result["generation_mode"] == "llm_extractive"
    assert result["generation_error"] is None
    assert result["citation_validation"]["status"] == "valid"
    for chunk_id in selected:
        assert EXCERPTS[int(chunk_id.split(":")[1])] in result["response"]
        assert f"[chunk_id:{chunk_id}]" in result["response"]
    assert "[item_id:5061]" in result["response"]
    if selected == ["5061:7"]:
        assert "__enter__()" not in result["response"]
        assert "__exit__()" not in result["response"]
    if "5061:14" in selected:
        assert "should not yield" in result["response"]
        assert "3.11" in result["response"]
        assert "__enter__() and __exit__()" in result["response"]


@pytest.mark.parametrize("selection", [
    '[]', '["9999:0"]', '["5061:0", "9999:0"]', '["5061:0", "5061:0"]',
    '["5061:0"', '{"chunks":["5061:0"]}', '[5061]', '[null]', 'null',
    '```json\n["5061:0"]\n```', 'The answer is ["5061:0"].', None,
])
def test_selection_rejects_invalid_or_empty_output_without_repair(monkeypatch, selection):
    bot, p = prepared(monkeypatch)
    result = bot._generated_result(selection, p)
    assert result["generation_mode"] == "insufficient_evidence"
    assert result["response"] == INSUFFICIENT_EVIDENCE


def test_selection_cannot_promote_synthetic_metadata_to_source_evidence(monkeypatch):
    bot, p = prepared(monkeypatch)
    p["sources"][0]["item"]["origin"] = "synthetic:fixture"
    result = bot._generated_result('["5061:0"]', p)
    assert result["generation_mode"] == "insufficient_evidence"
    assert result["response"] == INSUFFICIENT_EVIDENCE


def test_generation_error_cannot_promote_an_already_complete_json_selection(monkeypatch):
    bot, p = prepared(monkeypatch)
    result = bot._generated_result('["5061:0"]', p, "generation_failed")
    assert result["generation_mode"] == "insufficient_evidence"
    assert result["generation_error"] == "generation_failed"
    assert result["response"] == INSUFFICIENT_EVIDENCE


@pytest.mark.parametrize("asynchronous", [False, True], ids=["sync", "async"])
def test_selector_fragments_never_reach_provisional_text(monkeypatch, asynchronous):
    bot, _p = prepared(monkeypatch)
    fragments = ['[', '"5061', ':0"', ']']
    if asynchronous:
        from itlr.chatbot import llm_adapter

        async def tokens(*_args, **_kwargs):
            for fragment in fragments:
                yield fragment

        monkeypatch.setattr(llm_adapter, "try_llm_response_astream", tokens)

        async def collect():
            return [event async for event in bot.achat_stream("q")]

        events = asyncio.run(collect())
    else:
        monkeypatch.setattr(cb, "try_llm_response_stream", lambda *_args, **_kwargs: iter(fragments))
        events = list(bot.chat_stream("q"))
    final = events[-1][1]
    assert events[-1][0] == "final"
    assert final["generation_mode"] == "llm_extractive"
    assert EXCERPTS[0] in final["response"]
    # A transport may emit the validated quote, but must never display selector tokens.
    assert all(text == final["response"] for event, text in events if event == "text")


def test_legacy_generation_keeps_its_existing_citation_contract(monkeypatch):
    bot, p = prepared(monkeypatch)
    bot.search_index = {}
    p.pop("evidence_selection")
    answer = "Legacy response [item_id:5061]"
    result = bot._generated_result(answer, p)
    assert result["generation_mode"] == "llm"
    assert result["response"] == answer


def test_evidence_char_budget_helper(monkeypatch):
    from itlr.chatbot.chatbot import _evidence_char_budget
    monkeypatch.delenv("ITLR_EVIDENCE_EXCERPT_CHAR_BUDGET", raising=False)
    assert _evidence_char_budget() is None
    monkeypatch.setenv("ITLR_EVIDENCE_EXCERPT_CHAR_BUDGET", "900")
    assert _evidence_char_budget() == 900
    for invalid in ("", "0", "-3", "abc"):
        monkeypatch.setenv("ITLR_EVIDENCE_EXCERPT_CHAR_BUDGET", invalid)
        assert _evidence_char_budget() is None


def test_multiline_source_remains_inside_markdown_quote(monkeypatch):
    bot, p = prepared(monkeypatch)
    p["sources"][0]["excerpt"] = "First sentence.\n\n# Source heading, not a generated claim"
    result = bot._generated_result('["5061:0"]', p)
    assert "\n> # Source heading" in result["response"]
    assert "\n# Source heading" not in result["response"]


def test_prompt_keeps_full_excerpt_without_budget():
    """Default behavior: no truncation unless an explicit char budget is configured."""
    from itlr.chatbot.citations import evidence_selection_prompt
    sources = [{"item_id": 5061, "title": "contextlib", "url": "https://example.test/x",
                "chunk_id": "5061:0", "excerpt": EXCERPTS[0], "evidence_kind": "source_text"},
               {"item_id": 5061, "title": "contextlib", "url": "https://example.test/x",
                "chunk_id": "5061:7", "excerpt": EXCERPTS[7], "evidence_kind": "source_text"},
               {"item_id": 9001, "title": "synthetic", "url": "https://example.test/s",
                "chunk_id": "9001:0", "excerpt": "metadata", "evidence_kind": "metric"}]
    prompt = evidence_selection_prompt(sources)
    assert EXCERPTS[0] in prompt and EXCERPTS[7] in prompt


def test_prompt_char_budget_truncates_excerpts_but_not_chunk_ids():
    from itlr.chatbot.citations import evidence_selection_prompt
    excerpt = EXCERPTS[0]
    assert len(excerpt) > 200
    prompt = evidence_selection_prompt(
        [{"item_id": 5061, "title": "contextlib", "url": "https://example.test/x",
          "chunk_id": "5061:0", "excerpt": excerpt, "evidence_kind": "source_text"}],
        char_budget_per_chunk=200)
    assert "Chunk 5061:0" in prompt
    assert excerpt[:200] in prompt and excerpt[:201] not in prompt
    assert "…" in prompt
    # the budgeted prompt must be shorter than the full excerpt view
    assert len(prompt) < len(excerpt)


def test_prompt_budget_not_applied_for_invalid_values():
    from itlr.chatbot.citations import evidence_selection_prompt
    excerpt = EXCERPTS[0]
    for invalid in (None, 0, -5, "abc"):
        prompt = evidence_selection_prompt(
            [{"item_id": 5061, "title": "contextlib", "url": "https://example.test/x",
              "chunk_id": "5061:0", "excerpt": excerpt, "evidence_kind": "source_text"}],
            char_budget_per_chunk=invalid)
        assert excerpt in prompt


def test_prepare_budget_wiring_and_binding_remain_full(client, monkeypatch):
    """_evidence_sys_prompt routes env budget into the selection view only."""
    from itlr.chatbot.chatbot import _evidence_char_budget, _evidence_sys_prompt
    excerpt = EXCERPTS[0]
    assert len(excerpt) > 120
    evidence = [{"item_id": 5061, "title": "contextlib", "url": "https://docs.python.org/x",
                 "chunk_id": "5061:0", "excerpt": excerpt, "evidence_kind": "source_text"}]
    monkeypatch.setenv("ITLR_EVIDENCE_EXCERPT_CHAR_BUDGET", "120")
    prompt = _evidence_sys_prompt(evidence)
    assert excerpt[:120] in prompt and "…" in prompt
    assert excerpt[120:126] not in prompt
    # stored evidence still binds the full excerpt into the user answer
    from itlr.chatbot.citations import bind_evidence_selection
    answer = bind_evidence_selection(json.dumps(["5061:0"]), [
        {"item_id": 5061, "chunk_id": "5061:0", "excerpt": excerpt,
         "evidence_kind": "source_text"}])
    assert excerpt in answer
