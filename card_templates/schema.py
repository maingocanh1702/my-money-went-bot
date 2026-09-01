"""Card template schema — dataclasses for cashback card configuration.

A CardTemplate is the validated, in-memory representation of a YAML template.
It carries everything needed to seed a credit card's cashback program:
rules, tiers, patterns, and card-level config.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class TierConfig:
    """Per-transaction cap tier (amount band → max cashback per tx)."""
    tx_min: float
    tx_max: float | None = None   # None = ∞
    per_tx_cap: float = 0.0


@dataclass
class RuleConfig:
    """One cashback rule: a match condition + rate + caps."""
    mcc: str
    name: str
    emoji: str = "🏷️"
    monthly_cap: float = 0.0
    daily_limit: int = 0
    rate: float | None = None     # None = inherit card-level cashback_rate
    min_tx_amount: float = 0.0
    stackable: bool = False
    priority: int = 1


@dataclass
class CardConfig:
    """Card-level cashback configuration."""
    cashback_rate: float = 0.0
    min_eligible_spend: float = 0.0
    cap_period: str = "statement_cycle"
    alert_pct: float = 0.80


@dataclass
class CardTemplate:
    """Full cashback template for a credit card program."""
    card_id: str
    card_name: str
    bank: str
    version: str = ""
    description: str = ""
    config: CardConfig = field(default_factory=CardConfig)
    tier_set: str = ""
    tiers: list[TierConfig] = field(default_factory=list)
    rules: list[RuleConfig] = field(default_factory=list)
    patterns: dict[str, list[str]] = field(default_factory=dict)

    @property
    def mcc_choices(self) -> list[tuple[str, str]]:
        """MCC picker choices derived from rules: [(mcc_code, "emoji name"), ...]."""
        return [(r.mcc, f"{r.emoji} {r.name}") for r in self.rules]

    @property
    def emoji_map(self) -> dict[str, str]:
        """MCC code → emoji, for use in reports."""
        return {r.mcc: r.emoji for r in self.rules}

    def rule_by_mcc(self, mcc: str) -> RuleConfig | None:
        """Find rule by MCC code."""
        return next((r for r in self.rules if r.mcc == mcc), None)
