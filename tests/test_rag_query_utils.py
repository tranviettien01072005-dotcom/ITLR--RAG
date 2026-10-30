"""Query rewriting used before retrieval must preserve intent and history."""

from itlr.core.rag import enrich_query_with_history, expand_query, item_to_document


def test_expand_query_adds_alias_expansion_and_matching_category():
    expanded = expand_query("k8s devops deployment", categories=["DevOps"])
    assert expanded.startswith("k8s devops deployment")
    assert "kubernetes" in expanded
    assert "DevOps" in expanded


def test_expand_query_does_not_match_aliases_inside_words():
    expanded = expand_query("database normalization")
    assert "artificial intelligence" not in expanded
    assert "database normalization" in expanded


def test_enrich_query_uses_recent_user_turns_only():
    history = [
        {"role": "assistant", "content": "ignore me"},
        {"role": "user", "content": "docker networks"},
        {"role": "user", "content": "compose volumes"},
        {"role": "user", "content": ""},
    ]
    assert enrich_query_with_history("how to mount?", history) == "compose volumes  how to mount?"
    assert enrich_query_with_history("plain", []) == "plain"
    assert enrich_query_with_history("plain", [{"role": "assistant", "content": "x"}]) == "plain"


def test_item_document_contains_all_catalog_fields():
    row = {
        "title": "Docker", "type": "Tài liệu", "category": "DevOps", "topics": "docker",
        "description": "Containers", "instructor": "Docs", "platform": "Docker",
        "link": "https://docs.docker.com",
    }
    text = item_to_document(row)
    for value in row.values():
        assert value in text
