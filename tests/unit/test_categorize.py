"""Category picker rendering unit tests."""

from __future__ import annotations

from core.handlers.categorize import _render_markup, _render_picker_text


def test_render_picker_text_and_markup_are_zalo_number_friendly() -> None:
    entry = {
        "tx_id": 9,
        "amount": 50000,
        "direction": "out",
        "description": "Coffee",
        "options": [
            {"index": 1, "category_id": 10, "name": "Food"},
            {"index": 2, "category_id": 11, "name": "Transport"},
        ],
    }

    text = _render_picker_text(entry, "vi")
    assert "chi 50,000 VND" in text
    assert "Coffee" in text
    assert "Chọn danh mục cho giao dịch:" in text

    markup = _render_markup(entry)
    assert [row[0].label for row in markup.rows] == ["Food", "Transport"]
    assert [row[0].callback_data for row in markup.rows] == ["cat:9:10", "cat:9:11"]


def test_render_picker_text_uses_english_locale() -> None:
    entry = {
        "tx_id": 1,
        "amount": 10000,
        "direction": "in",
        "description": "Salary",
        "options": [],
    }
    text = _render_picker_text(entry, "en")
    assert "in 10,000 VND" in text
    assert "Pick a category" in text
