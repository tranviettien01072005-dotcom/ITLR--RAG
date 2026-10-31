"""Untrusted excerpt formatting must remain visibly quoted for Markdown line endings."""
import pytest

from itlr.chatbot.citations import bind_evidence_selection


@pytest.mark.parametrize("newline", ["\n", "\r\n", "\r"], ids=["LF", "CRLF", "CR"])
def test_source_heading_stays_quoted_for_all_markdown_line_endings(newline):
    excerpt = f"First quoted sentence.{newline}# This must stay quoted"
    sources = [{"chunk_id": "5061:0", "item_id": 5061,
                "evidence_kind": "source_text", "excerpt": excerpt}]
    response = bind_evidence_selection('["5061:0"]', sources)
    # Preserve source line endings while preventing source headings escaping the quote.
    assert f"> First quoted sentence.{newline}> # This must stay quoted" in response


def test_literal_code_uses_a_fence_longer_than_backticks_in_the_source():
    excerpt = "Context managers use __enter__() and __exit__(); literal ``` example."
    sources = [{"chunk_id": "5061:0", "item_id": 5061,
                "evidence_kind": "source_text", "excerpt": excerpt}]
    response = bind_evidence_selection('["5061:0"]', sources)
    assert "> ````text\n> " + excerpt + "\n> ````" in response
