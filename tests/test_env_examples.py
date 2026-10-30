"""Committed env examples are templates; they must never carry secret values."""

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
FILES = [".env.example", "web/.env.example"] + sorted(
    str(path.relative_to(ROOT)) for path in (ROOT / "deploy").glob("*.env.example")
)
SECRET_LINE = re.compile(
    r"^([A-Z0-9_]*(?:_API_KEY|_SECRET|_TOKEN|_PASSCODE|_PASSWORD|_PASS))[ \t]*=[ \t]*(.*)$", re.M
)


@pytest.mark.parametrize("name", FILES)
def test_example_secrets_are_empty(name):
    text = (ROOT / name).read_text(encoding="utf-8")
    populated = [key for key, value in SECRET_LINE.findall(text) if value.strip()]
    assert not populated, f"{name} ships secret values for: {populated}"
