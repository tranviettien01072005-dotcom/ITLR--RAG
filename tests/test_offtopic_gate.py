"""Regression: ngưỡng off-topic phải là 0.80 (dữ liệu 121 câu), không phải 0.55.

0.55 cho F1 0.663 = accept-all (refusal 0/21); 0.800 cho F1 0.929 theo
reports/offtopic_eval.md. Nếu ai hạ ngưỡng về 0.55 mà không có eval mới, test đỏ.
"""

from __future__ import annotations

from itlr.chatbot.chatbot import (
    CHATBOT_OFFTOPIC_GATE,
    OFFTOPIC_GATE_ENV,
    _offtopic_gate,
    below_offtopic_gate,
)


def test_default_gate_is_data_backed_threshold():
    assert CHATBOT_OFFTOPIC_GATE == 0.80


def test_below_gate_logic():
    assert below_offtopic_gate(0.55) is True
    assert below_offtopic_gate(0.79) is True
    assert below_offtopic_gate(0.80) is False
    assert below_offtopic_gate(0.95) is False


def test_env_override_is_validated(monkeypatch):
    monkeypatch.setenv(OFFTOPIC_GATE_ENV, "0.9")
    assert _offtopic_gate() == 0.9

    monkeypatch.setenv(OFFTOPIC_GATE_ENV, "không-phải-số")
    assert _offtopic_gate() == 0.80

    monkeypatch.setenv(OFFTOPIC_GATE_ENV, "1.5")
    assert _offtopic_gate() == 0.80
