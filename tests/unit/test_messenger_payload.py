"""SendPayload + Button + Markup validation rules."""

from __future__ import annotations

import pytest

from core.messenger import Button, Markup, SendPayload
from core.messenger.base import _validate_payload


def test_payload_accepts_text_key_alone() -> None:
    _validate_payload({"text_key": "greeting", "text_params": {"name": "Alice"}})


def test_payload_accepts_text_alone() -> None:
    _validate_payload({"text": "hello"})


def test_payload_rejects_both_text_and_text_key() -> None:
    with pytest.raises(ValueError, match="exactly one of text_key or text"):
        _validate_payload({"text_key": "greeting", "text": "hello"})


def test_payload_rejects_neither_text_nor_text_key() -> None:
    payload: SendPayload = {}
    with pytest.raises(ValueError, match="exactly one of text_key or text"):
        _validate_payload(payload)


def test_payload_rejects_bad_parse_mode() -> None:
    payload: SendPayload = {"text": "hi"}
    # Force-cast a bad value through dict to bypass TypedDict literal check.
    bad = dict(payload)
    bad["parse_mode"] = "xml"
    with pytest.raises(ValueError, match="parse_mode must be one of"):
        _validate_payload(bad)  # type: ignore[arg-type]


def test_payload_rejects_non_markup_object() -> None:
    bad = {"text": "hi", "markup": {"some": "dict"}}
    with pytest.raises(TypeError, match="must be a core.messenger.Markup"):
        _validate_payload(bad)  # type: ignore[arg-type]


def test_button_requires_exactly_one_label_source() -> None:
    with pytest.raises(ValueError, match="exactly one of label_key or label"):
        Button(callback_data="x")
    with pytest.raises(ValueError, match="exactly one of label_key or label"):
        Button(label_key="k", label="L", callback_data="x")


def test_button_requires_exactly_one_action() -> None:
    with pytest.raises(ValueError, match="exactly one of callback_data or url"):
        Button(label_key="k")
    with pytest.raises(ValueError, match="exactly one of callback_data or url"):
        Button(label_key="k", callback_data="x", url="https://example.com")


def test_markup_accepts_empty_rows_and_buttons() -> None:
    m = Markup(rows=[[Button(label_key="btn_confirm", callback_data="ok")]])
    assert len(m.rows) == 1
    assert m.rows[0][0].callback_data == "ok"
