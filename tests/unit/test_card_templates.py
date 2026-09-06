"""Tests for card_templates — loader, validator, export, and schema."""
import os
import tempfile
import pytest
import yaml

from card_templates import (
    list_templates,
    load_template,
    export_template,
    validate_template,
    invalidate_cache,
)
from card_templates.schema import CardConfig, CardTemplate, RuleConfig, TierConfig


class TestListTemplates:
    """list_templates() should discover YAML files in the templates dir."""

    def test_discovers_bundled_templates(self):
        names = list_templates()
        assert "cake_freedom" in names
        assert "example_visa" in names

    def test_returns_sorted(self):
        names = list_templates()
        assert names == sorted(names)

    def test_excludes_underscore_prefix(self, tmp_path):
        (tmp_path / "_schema.yaml").write_text("x: 1")
        (tmp_path / "card_a.yaml").write_text("card_id: a\ncard_name: A\nbank: X")
        os.environ["CARD_TEMPLATES_DIR"] = str(tmp_path)
        try:
            names = list_templates()
            assert "_schema" not in names
            assert "card_a" in names
        finally:
            os.environ.pop("CARD_TEMPLATES_DIR", None)
            invalidate_cache()


class TestLoadTemplate:
    """load_template() parses YAML into validated CardTemplate."""

    def test_load_cake_freedom(self):
        tpl = load_template("cake_freedom", force_reload=True)
        assert tpl.card_id == "cake_freedom"
        assert tpl.card_name == "Cake by VPBank Freedom"
        assert tpl.bank == "VPBank"
        assert tpl.config.cashback_rate == 0.20
        assert tpl.config.min_eligible_spend == 5_000_000
        assert tpl.config.cap_period == "statement_cycle"
        assert len(tpl.tiers) == 2
        assert len(tpl.rules) == 5
        # Check specific rules
        tmdt = tpl.rule_by_mcc("5262")
        assert tmdt is not None
        assert tmdt.name == "Sàn TMĐT"
        assert tmdt.emoji == "🛍"
        assert tmdt.monthly_cap == 200_000
        # Cake rules inherit card rate (rate=None)
        assert tmdt.rate is None

    def test_load_example_visa(self):
        tpl = load_template("example_visa", force_reload=True)
        assert tpl.card_id == "example_visa"
        assert tpl.bank == "Example Bank"
        assert tpl.config.cashback_rate == 0.01  # base 1%
        assert tpl.config.min_eligible_spend == 0  # no gate
        assert tpl.config.cap_period == "calendar_month"
        assert len(tpl.tiers) == 0  # no per-tx tiers
        assert len(tpl.rules) == 10
        # The example card gives each rule its own rate
        restaurant = tpl.rule_by_mcc("5812")
        assert restaurant is not None
        assert restaurant.rate == 0.03
        entertainment = tpl.rule_by_mcc("4899")
        assert entertainment is not None
        assert entertainment.rate == 0.05

    def test_cache_works(self):
        invalidate_cache()
        tpl1 = load_template("cake_freedom")
        tpl2 = load_template("cake_freedom")
        assert tpl1 is tpl2  # same object from cache

    def test_force_reload(self):
        invalidate_cache()
        tpl1 = load_template("cake_freedom")
        tpl2 = load_template("cake_freedom", force_reload=True)
        assert tpl1 is not tpl2

    def test_not_found_raises(self):
        with pytest.raises(FileNotFoundError, match="Template not found"):
            load_template("nonexistent_card", force_reload=True)

    def test_invalid_template_raises(self, tmp_path):
        # Missing required card_id
        (tmp_path / "bad.yaml").write_text("card_name: Bad\nbank: X\nconfig:\n  cashback_rate: 2.0")
        os.environ["CARD_TEMPLATES_DIR"] = str(tmp_path)
        try:
            with pytest.raises(ValueError, match="validation errors"):
                load_template("bad", force_reload=True)
        finally:
            os.environ.pop("CARD_TEMPLATES_DIR", None)
            invalidate_cache()


class TestMccChoices:
    """CardTemplate.mcc_choices and emoji_map properties."""

    def test_cake_mcc_choices(self):
        tpl = load_template("cake_freedom", force_reload=True)
        choices = tpl.mcc_choices
        assert len(choices) == 5
        # Each choice is (mcc_code, "emoji name")
        codes = [c[0] for c in choices]
        assert "5262" in codes
        assert "5411" in codes
        # Labels include emoji
        tmdt_label = next(c[1] for c in choices if c[0] == "5262")
        assert "🛍" in tmdt_label
        assert "Sàn TMĐT" in tmdt_label

    def test_example_mcc_choices(self):
        tpl = load_template("example_visa", force_reload=True)
        choices = tpl.mcc_choices
        assert len(choices) == 10

    def test_emoji_map(self):
        tpl = load_template("cake_freedom", force_reload=True)
        emap = tpl.emoji_map
        assert emap["5411"] == "🛒"
        assert emap["5262"] == "🛍"


class TestValidation:
    """validate_template() catches schema errors."""

    def test_valid_template(self):
        tpl = load_template("cake_freedom", force_reload=True)
        errors = validate_template(tpl)
        assert errors == []

    def test_missing_card_id(self):
        tpl = CardTemplate(card_id="", card_name="Test", bank="Bank")
        errors = validate_template(tpl)
        assert any("card_id" in e for e in errors)

    def test_rate_out_of_range(self):
        tpl = CardTemplate(card_id="t", card_name="T", bank="B",
                           config=CardConfig(cashback_rate=1.5))
        errors = validate_template(tpl)
        assert any("cashback_rate" in e for e in errors)

    def test_non_finite_financial_values_are_rejected(self):
        tpl = CardTemplate(card_id="t", card_name="T", bank="B",
                           config=CardConfig(cashback_rate=float("nan")))
        assert any("cashback_rate" in error for error in validate_template(tpl))

    def test_duplicate_mcc(self):
        tpl = CardTemplate(card_id="t", card_name="T", bank="B",
                           rules=[
                               RuleConfig(mcc="5411", name="A"),
                               RuleConfig(mcc="5411", name="B"),
                           ])
        errors = validate_template(tpl)
        assert any("duplicate" in e for e in errors)

    def test_tier_max_less_than_min(self):
        tpl = CardTemplate(card_id="t", card_name="T", bank="B",
                           tiers=[TierConfig(tx_min=100, tx_max=50, per_tx_cap=10)])
        errors = validate_template(tpl)
        assert any("tx_max" in e for e in errors)

    def test_pattern_mcc_not_in_rules(self):
        tpl = CardTemplate(card_id="t", card_name="T", bank="B",
                           patterns={"9999": ["PATTERN"]})
        errors = validate_template(tpl)
        assert any("9999" in e for e in errors)

    def test_rule_rate_out_of_range(self):
        tpl = CardTemplate(card_id="t", card_name="T", bank="B",
                           rules=[RuleConfig(mcc="5411", name="A", rate=5.0)])
        errors = validate_template(tpl)
        assert any("rate" in e for e in errors)


class TestExport:
    """export_template() roundtrip: load → export → reload should match."""

    def test_roundtrip_cake(self, tmp_path):
        tpl = load_template("cake_freedom", force_reload=True)
        yaml_str = export_template(tpl)

        # Write to temp file and reload
        out_path = tmp_path / "cake_freedom.yaml"
        out_path.write_text(yaml_str)

        os.environ["CARD_TEMPLATES_DIR"] = str(tmp_path)
        try:
            tpl2 = load_template("cake_freedom", force_reload=True)
            assert tpl2.card_id == tpl.card_id
            assert tpl2.card_name == tpl.card_name
            assert tpl2.config.cashback_rate == tpl.config.cashback_rate
            assert len(tpl2.rules) == len(tpl.rules)
            assert len(tpl2.tiers) == len(tpl.tiers)
        finally:
            os.environ.pop("CARD_TEMPLATES_DIR", None)
            invalidate_cache()

    def test_export_is_valid_yaml(self):
        tpl = load_template("example_visa", force_reload=True)
        yaml_str = export_template(tpl)
        data = yaml.safe_load(yaml_str)
        assert data["card_id"] == "example_visa"
        assert len(data["rules"]) == 10


class TestPatterns:
    """Pattern data in templates."""

    def test_cake_has_patterns(self):
        tpl = load_template("cake_freedom", force_reload=True)
        assert "5262" in tpl.patterns
        assert "SHOPEE" in tpl.patterns["5262"]
        assert "LAZADA" in tpl.patterns["5262"]

    def test_example_has_patterns(self):
        tpl = load_template("example_visa", force_reload=True)
        assert "5812" in tpl.patterns
        assert any("KICHI" in p for p in tpl.patterns["5812"])

    def test_all_pattern_mccs_have_rules(self):
        for name in list_templates():
            tpl = load_template(name, force_reload=True)
            rule_mccs = {r.mcc for r in tpl.rules}
            for mcc in tpl.patterns:
                assert mcc in rule_mccs, f"{name}: pattern MCC {mcc} has no rule"
