"""Validate all YAML templates in the templates/ directory.

Runs the same validation logic as the bot's card_templates loader.
Used by CI (GitHub Actions) and locally.

Usage:
    python validate.py
    python validate.py templates/cake_freedom.yaml   # single file
"""
import sys
from pathlib import Path

import yaml


REQUIRED_FIELDS = {"card_id", "card_name", "bank"}
REQUIRED_CONFIG = {"cashback_rate", "cap_period"}


def validate_file(path: Path) -> list[str]:
    """Validate a single YAML template. Returns list of error strings."""
    errors = []

    try:
        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f)
    except yaml.YAMLError as e:
        return [f"YAML parse error: {e}"]

    if not isinstance(data, dict):
        return ["Root must be a YAML mapping"]

    # Required top-level fields
    for field in REQUIRED_FIELDS:
        if not data.get(field):
            errors.append(f"Missing required field: {field}")

    # Config validation
    cfg = data.get("config", {})
    if not isinstance(cfg, dict):
        errors.append("config must be a mapping")
    else:
        rate = cfg.get("cashback_rate")
        if rate is not None:
            try:
                r = float(rate)
                if r < 0 or r > 1:
                    errors.append(f"config.cashback_rate must be 0-1, got {r}")
            except (ValueError, TypeError):
                errors.append(f"config.cashback_rate must be a number, got {rate!r}")

        for field in REQUIRED_CONFIG:
            if field not in cfg:
                errors.append(f"Missing config field: {field}")

        spend = cfg.get("min_eligible_spend")
        if spend is not None:
            try:
                if float(spend) < 0:
                    errors.append("config.min_eligible_spend cannot be negative")
            except (ValueError, TypeError):
                errors.append(f"config.min_eligible_spend must be a number")

    # Tiers validation
    tiers = data.get("tiers", [])
    if not isinstance(tiers, list):
        errors.append("tiers must be a list")
    else:
        for i, tier in enumerate(tiers):
            if not isinstance(tier, dict):
                errors.append(f"tiers[{i}] must be a mapping")
                continue
            cap = tier.get("per_tx_cap")
            if cap is not None and float(cap) <= 0:
                errors.append(f"tiers[{i}].per_tx_cap must be > 0")
            tx_min = float(tier.get("tx_min", 0))
            tx_max = tier.get("tx_max")
            if tx_max not in (None, "", "null") and float(tx_max) < tx_min:
                errors.append(f"tiers[{i}].tx_max < tx_min")

    # Rules validation
    rules = data.get("rules", [])
    if not isinstance(rules, list):
        errors.append("rules must be a list")
    else:
        mcc_codes = set()
        for i, rule in enumerate(rules):
            if not isinstance(rule, dict):
                errors.append(f"rules[{i}] must be a mapping")
                continue
            mcc = str(rule.get("mcc", ""))
            if not mcc:
                errors.append(f"rules[{i}].mcc is required")
            if not rule.get("name"):
                errors.append(f"rules[{i}].name is required")
            if mcc in mcc_codes:
                errors.append(f"rules[{i}].mcc '{mcc}' is duplicate")
            mcc_codes.add(mcc)

            rule_rate = rule.get("rate")
            if rule_rate not in (None, "", "null"):
                try:
                    rr = float(rule_rate)
                    if rr < 0 or rr > 1:
                        errors.append(f"rules[{i}].rate must be 0-1, got {rr}")
                except (ValueError, TypeError):
                    errors.append(f"rules[{i}].rate must be a number")

            cap = rule.get("monthly_cap")
            if cap is not None and float(cap) < 0:
                errors.append(f"rules[{i}].monthly_cap cannot be negative")

            daily = rule.get("daily_limit")
            if daily is not None and int(daily) < 0:
                errors.append(f"rules[{i}].daily_limit cannot be negative")

    # Patterns validation
    patterns = data.get("patterns", {})
    if not isinstance(patterns, dict):
        errors.append("patterns must be a mapping")
    else:
        rule_mccs = {str(r.get("mcc", "")) for r in rules if isinstance(r, dict)}
        for mcc in patterns:
            if str(mcc) not in rule_mccs:
                errors.append(f"patterns reference MCC '{mcc}' not in rules")

    return errors


def main():
    """Validate templates. Exit 1 if any errors found."""
    templates_dir = Path(__file__).parent

    # Specific files or all templates
    if len(sys.argv) > 1:
        files = [Path(f) for f in sys.argv[1:]]
    else:
        files = sorted(templates_dir.glob("*.yaml"))

    if not files:
        print("⚠️  No templates found.")
        sys.exit(0)

    total_errors = 0
    for f in files:
        errors = validate_file(f)
        if errors:
            print(f"❌ {f.name}:")
            for e in errors:
                print(f"   - {e}")
            total_errors += len(errors)
        else:
            print(f"✅ {f.name}")

    print(f"\n{'='*40}")
    print(f"Templates: {len(files)}, Errors: {total_errors}")

    if total_errors > 0:
        sys.exit(1)
    print("All templates valid! ✅")


if __name__ == "__main__":
    main()
