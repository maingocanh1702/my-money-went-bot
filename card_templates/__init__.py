"""Card template loader — discover, validate, and load YAML templates.

Templates are YAML files in the `card_templates/` directory (alongside this
module). Each file describes a credit card's cashback program: rules, tiers,
patterns, and card-level config.

Usage:
    from card_templates import list_templates, load_template
    names = list_templates()        # ["cake_freedom", "techcombank_visa"]
    tpl = load_template("cake_freedom")
    tpl.config.cashback_rate        # 0.20
    tpl.rules[0].mcc                # "5262"
"""
from __future__ import annotations

import os
from pathlib import Path

import yaml  # type: ignore[import-untyped]

from card_templates.schema import (
    CardConfig,
    CardTemplate,
    RuleConfig,
    TierConfig,
)

_TEMPLATES_DIR = Path(__file__).parent

# In-memory cache (templates are read-only, load once)
_cache: dict[str, CardTemplate] = {}


def _templates_dir() -> Path:
    """Resolve templates directory (allow override via env for testing)."""
    override = os.environ.get("CARD_TEMPLATES_DIR")
    return Path(override) if override else _TEMPLATES_DIR


def list_templates() -> list[str]:
    """Return sorted list of available template names (without .yaml)."""
    d = _templates_dir()
    return sorted(
        p.stem for p in d.glob("*.yaml")
        if not p.name.startswith("_")  # skip _schema.yaml etc.
    )


def load_template(name: str, *, force_reload: bool = False) -> CardTemplate:
    """Load and validate a template by name. Raises FileNotFoundError / ValueError."""
    if not force_reload and name in _cache:
        return _cache[name]

    path = _templates_dir() / f"{name}.yaml"
    if not path.exists():
        raise FileNotFoundError(f"Template not found: {name} (looked in {path})")

    with open(path, encoding="utf-8") as f:
        raw = yaml.safe_load(f)

    tpl = _parse_template(raw, name)
    errors = validate_template(tpl)
    if errors:
        raise ValueError(f"Template {name!r} validation errors:\n" + "\n".join(errors))

    _cache[name] = tpl
    return tpl


def _parse_template(raw: dict, name: str) -> CardTemplate:
    """Parse raw YAML dict into a CardTemplate dataclass."""
    cfg_raw = raw.get("config", {})
    config = CardConfig(
        cashback_rate=float(cfg_raw.get("cashback_rate", 0)),
        min_eligible_spend=float(cfg_raw.get("min_eligible_spend", 0)),
        cap_period=cfg_raw.get("cap_period", "statement_cycle"),
        alert_pct=float(cfg_raw.get("alert_pct", 0.80)),
    )

    tiers = [
        TierConfig(
            tx_min=float(t.get("tx_min", 0)),
            tx_max=float(t["tx_max"]) if t.get("tx_max") not in (None, "", "null") else None,
            per_tx_cap=float(t.get("per_tx_cap", 0)),
        )
        for t in raw.get("tiers", [])
    ]

    rules = [
        RuleConfig(
            mcc=str(r["mcc"]),
            name=r["name"],
            emoji=r.get("emoji", "🏷️"),
            monthly_cap=float(r.get("monthly_cap", 0)),
            daily_limit=int(r.get("daily_limit", 0)),
            rate=float(r["rate"]) if r.get("rate") not in (None, "", "null") else None,
            min_tx_amount=float(r.get("min_tx_amount", 0)),
            stackable=bool(r.get("stackable", False)),
            priority=int(r.get("priority", 1)),
        )
        for r in raw.get("rules", [])
    ]

    patterns = {}
    for mcc, pats in raw.get("patterns", {}).items():
        patterns[str(mcc)] = [str(p) for p in pats]

    return CardTemplate(
        card_id=raw.get("card_id", name),
        card_name=raw.get("card_name", name),
        bank=raw.get("bank", ""),
        version=raw.get("version", ""),
        description=raw.get("description", ""),
        config=config,
        tier_set=raw.get("tier_set", ""),
        tiers=tiers,
        rules=rules,
        patterns=patterns,
    )


def validate_template(tpl: CardTemplate) -> list[str]:
    """Validate a CardTemplate. Returns list of error messages (empty = valid)."""
    errors = []
    if not tpl.card_id:
        errors.append("card_id is required")
    if not tpl.card_name:
        errors.append("card_name is required")
    if not tpl.bank:
        errors.append("bank is required")
    if tpl.config.cashback_rate < 0 or tpl.config.cashback_rate > 1:
        errors.append(f"cashback_rate must be 0-1, got {tpl.config.cashback_rate}")
    if tpl.config.min_eligible_spend < 0:
        errors.append("min_eligible_spend cannot be negative")

    for i, tier in enumerate(tpl.tiers):
        if tier.per_tx_cap <= 0:
            errors.append(f"tiers[{i}].per_tx_cap must be > 0")
        if tier.tx_min < 0:
            errors.append(f"tiers[{i}].tx_min cannot be negative")
        if tier.tx_max is not None and tier.tx_max < tier.tx_min:
            errors.append(f"tiers[{i}].tx_max < tx_min")

    mcc_codes = set()
    for i, rule in enumerate(tpl.rules):
        if not rule.mcc:
            errors.append(f"rules[{i}].mcc is required")
        if not rule.name:
            errors.append(f"rules[{i}].name is required")
        if rule.mcc in mcc_codes:
            errors.append(f"rules[{i}].mcc '{rule.mcc}' is duplicate")
        mcc_codes.add(rule.mcc)
        if rule.rate is not None and (rule.rate < 0 or rule.rate > 1):
            errors.append(f"rules[{i}].rate must be 0-1 or null, got {rule.rate}")
        if rule.monthly_cap < 0:
            errors.append(f"rules[{i}].monthly_cap cannot be negative")
        if rule.daily_limit < 0:
            errors.append(f"rules[{i}].daily_limit cannot be negative")

    # Warn if patterns reference MCC codes not in rules
    for mcc in tpl.patterns:
        if mcc not in mcc_codes:
            errors.append(f"patterns reference MCC '{mcc}' not defined in rules")

    return errors


def export_template(tpl: CardTemplate) -> str:
    """Export a CardTemplate back to YAML string (for /cashback export)."""
    data = {
        "card_id": tpl.card_id,
        "card_name": tpl.card_name,
        "bank": tpl.bank,
        "version": tpl.version,
        "description": tpl.description,
        "config": {
            "cashback_rate": tpl.config.cashback_rate,
            "min_eligible_spend": tpl.config.min_eligible_spend,
            "cap_period": tpl.config.cap_period,
            "alert_pct": tpl.config.alert_pct,
        },
        "tier_set": tpl.tier_set,
        "tiers": [
            {"tx_min": t.tx_min, "tx_max": t.tx_max, "per_tx_cap": t.per_tx_cap}
            for t in tpl.tiers
        ],
        "rules": [
            {
                k: v
                for k, v in {
                    "mcc": r.mcc,
                    "name": r.name,
                    "emoji": r.emoji,
                    "monthly_cap": r.monthly_cap,
                    "daily_limit": r.daily_limit,
                    "rate": r.rate,
                    "min_tx_amount": r.min_tx_amount,
                    "stackable": r.stackable,
                    "priority": r.priority,
                }.items()
                if v  # omit zero/None/empty defaults for readability
            }
            for r in tpl.rules
        ],
        "patterns": {mcc: pats for mcc, pats in tpl.patterns.items()},
    }
    return yaml.dump(data, allow_unicode=True, default_flow_style=False, sort_keys=False)


def invalidate_cache():
    """Clear the template cache (useful after adding/modifying templates)."""
    _cache.clear()
