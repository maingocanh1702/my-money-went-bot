# ADR-0001: Monorepo over split repos for VN + Global markets

> **Status:** ✅ Accepted
> **Date:** 2026-05-10
> **Decision maker:** Founder (Ngoc-Anh)
> **Context cross-refs:** [market-strategy-overview.md](../market-strategy-overview.md) · [brd-vi.md](../brd-vi.md) · [brd-en.md](../brd-en.md) · [strategic-pivot-global.md](../strategic-pivot-global.md)

---

## Context

MyMoneyWent runs a **dual-market strategy** with materially different transaction-capture stacks:

- 🇻🇳 **VN market** ("Tiền Về Nơi Đâu") — SePay webhook + Vietnamese bank email parsing. ICP: office worker / freelancer / online seller. Pricing: $4 / $9. Channels: Telegram + Discord MVP, Messenger + Zalo Phase 3+.
- 🌐 **Global market** ("My Money Went") — Plaid/TrueLayer/Tink + e-commerce platform APIs (Stripe/PayPal/Shopify/Etsy/Amazon SP-API) + payout email parsing. ICP: e-commerce solopreneur. Pricing: $6 / $12 + annual. Channels: Telegram + Discord + Messenger MVP + read-only web dashboard.

Both markets share **Phase 1-2 multi-tenant foundation**: DB schema, `messenger.send()` interface (channel-agnostic), auth, admin tools, observability.

The question: **should the project be split into 2 separate Git repositories** (`tien-ve-noi-dau/` + `my-money-went/`), or stay as a single monorepo (`MyMoneyWent/`)?

This decision was prompted by founder's question on 2026-05-10 after dual-BRD restructure (brd-vi.md v3.1.0 + brd-en.md v4.0.0).

## Decision

**Stay monorepo.** Single Git repository (`MyMoneyWent/`) covering both markets, with **code-level adapter pattern** to separate market-specific implementations from shared foundation.

Re-evaluate split when one of the explicit triggers below fires.

## Target code structure (Phase 1 refactor target)

```
MyMoneyWent/
├── core/                          # Shared foundation — ONE implementation, both markets use
│   ├── messenger/                 # Telegram, Discord, Messenger adapters (channel-agnostic)
│   │   ├── interface.py           # `messenger.send()` abstract API
│   │   ├── telegram_adapter.py
│   │   ├── discord_adapter.py
│   │   └── messenger_adapter.py
│   ├── auth/                      # Multi-tenant auth, channel_user_id resolution
│   ├── db/                        # Multi-tenant schema, migrations
│   ├── tenant_context.py          # Resolves market per user (VN vs global)
│   ├── pricing/                   # Generic tier framework (Free/Pro/Higher)
│   ├── categorization/            # Generic rules engine
│   └── observability/             # Logging, metrics, alerts
├── markets/
│   ├── vn/                        # 🇻🇳 Tiền Về Nơi Đâu specifics
│   │   ├── capture/
│   │   │   ├── sepay_webhook.py
│   │   │   └── email_vn_banks.py  # TCB/Cake/ACB/STB/BIDV/MB parsers
│   │   ├── payment/
│   │   │   ├── vietqr.py
│   │   │   └── bank_transfer_detect.py
│   │   ├── pricing/tiers_vnd.py   # $4/$9 in VND
│   │   ├── channels/zalo.py       # VN-only channel (Phase 3+)
│   │   └── locale/                # Vietnamese strings
│   └── global/                    # 🌐 My Money Went specifics
│       ├── capture/
│       │   ├── plaid.py
│       │   ├── truelayer.py
│       │   ├── tink.py
│       │   ├── stripe.py
│       │   ├── paypal.py
│       │   ├── shopify.py
│       │   └── etsy.py
│       ├── payment/stripe_billing.py
│       ├── pricing/tiers_usd.py   # $6/$12 + annual
│       ├── web_dashboard/         # Next.js + Supabase (Global-only MVP)
│       └── locale/                # English strings (+ future i18n)
├── handlers/                      # Common command/event handlers (refactored Phase 2)
├── docs/
└── tests/
    ├── core/
    └── markets/
```

**Key rules:**
1. `core/` is **market-agnostic**. Anything that imports from `markets/vn/` or `markets/global/` does NOT belong in `core/`.
2. Market routing happens at one boundary: `core/tenant_context.py` resolves user's market (per channel registration, locale, explicit setting) and dispatches to `markets/vn/` or `markets/global/` adapter.
3. **No `if market == "vn"` scattered throughout `core/`.** Adapter pattern at module boundaries only.
4. `core/messenger/` supports Telegram + Discord + Messenger natively (shared channels). Zalo lives in `markets/vn/channels/`. WhatsApp (when added) lives in `markets/global/channels/`.

## Rationale

### Why monorepo wins for current context

| Factor | Monorepo | Split repos |
|---|---|---|
| Phase 1-2 foundation work | Code once, both markets reuse | Duplicate or build shared lib (with versioning + coordination overhead) |
| Solo founder bandwidth | 1× CI, 1× deploy, 1× dependency update | 2× everything |
| Global validation status | No infra commit before validation pass | Repo created before knowing Global is worth it |
| Code reuse | Categorization, tx schema, pricing framework, scheduled jobs naturally shared | Fork or shared lib |
| Branding | Folder name flexibility (rename if needed) | Folder name locked to product brand |
| Atomic cross-cutting changes | 1 PR for `core/` change benefits both markets | 2 PRs + version bump of shared lib |

### Why split-repos was rejected (now)

1. **Phase 1-2 has not started.** Code today (`handlers/`, `main.py`, `sheets.py`) is single-tenant VN. There is no shared code yet to protect from "monorepo problems." Splitting now creates 1 VN-only repo + 1 empty repo.
2. **Solo founder operational load.** 1 person × 2 repos = 2× CI, 2× security patches, 2× deploy pipelines, 2× dependency updates, 2× monitoring setups. Real cost, no realized benefit pre-MVP.
3. **Global market unvalidated.** Per `strategic-pivot-global.md` Section 7, validation sprint hasn't run. 30-50% non-trivial chance Global doesn't pass thresholds (≥30% solopreneur "very likely" pay $12, ≥40% use ≥2 platforms, etc.). Splitting commits infra cost before validation — premature optimization.
4. **No team to justify split.** Conway's law: repo boundaries should mirror team boundaries. Solo founder = 1 team = 1 repo. If a Global-dedicated contributor joins, the calculus changes.

### Why pure feature-flag approach was rejected

Considered: keep monorepo, no `markets/` separation, just `if market == "vn"` everywhere.

Rejected because:
- Conditional logic scattered in business code becomes unmaintainable at >5-10 sites
- Hard to test market-specific paths in isolation
- `core/` ends up with VN-specific dependencies (e.g., SePay client) imported "just in case"
- New market in future would require touching every conditional site

Adapter pattern at `markets/<market>/` boundary is the middle ground: cleaner than feature flags, lower overhead than split repos.

### Why "1 repo, 2 deployments" is also adopted

Even though codebase is shared, **runtime is separate**:
- 2 Railway services running same container image
- Env var `MARKET=vn` or `MARKET=global` selects adapter set
- 2 PostgreSQL databases (`db_vn`, `db_global`) — tenant data does NOT mix
- 2 sets of bot tokens (TG/Discord/Messenger × VN/Global)
- 2 domains (`tienvenoidau.com`, `mymoneywent.com`)

This gives compliance/data-residency separation at deployment layer without splitting the code.

## Re-evaluation triggers

This decision is **not permanent**. Re-open this ADR (write a follow-up ADR-NNNN superseding this one) if any of the following fires:

| Trigger | Threshold | Action |
|---|---|---|
| **Dedicated Global contributor onboards** | ≥1 person owning Global track full-time, not founder | Re-evaluate per Conway's law — split likely warranted |
| **Web dashboard scope grows beyond MVP** | Next.js + Supabase + 4-5 OAuth flows + charts → ≥6-8 weeks of work, separate deployment story | Consider splitting `web/` into a sub-repo (still monorepo for backend) |
| **Compliance / data residency requires separation** | EU regulator or VN authority requires market data on different servers AND different code paths AND audit trail per-codebase | Split likely required |
| **CI runtime exceeds 30 minutes** | Test suite for both markets at every PR slows velocity | Either invest in test parallelization, or split |
| **Adapter pattern collisions are frequent (>1× per sprint)** | `core/` changes routinely break `markets/vn/` and `markets/global/` simultaneously, indicating leaky abstraction | Re-design abstraction OR split |
| **Open-source one market** | Decision to OSS Global codebase but keep VN closed (or vice versa) | Split required |
| **Different tech stacks emerge** | E.g., Global team chooses Go for Plaid latency optimization while VN stays Python | Split inevitable |

**Default re-evaluation cadence:** Review at end of Q3 2026 (~3 months post VN MVP launch + Global validation sprint complete).

## Consequences

### Positive

- Phase 1-2 foundation builds once, benefits both markets
- Solo founder operational load minimized
- Atomic cross-market refactors (e.g., add new shared category to `core/categorization/`) in 1 PR
- Lower Cognitive load — 1 repo to navigate
- Test infrastructure shared (1 CI config, 1 set of fixtures for `core/`)
- Easier onboarding for future contributor — full context in 1 repo

### Negative

- VN-specific dependencies (e.g., `sepay-sdk`) and Global-specific dependencies (e.g., `plaid-python`) coexist in `requirements.txt` — slightly larger Docker image even though only 1 set is active per deploy. Acceptable.
- Test suite runs both markets' tests on every PR — slower than VN-only CI. Mitigation: separate test markers, run VN tests on VN-track PRs, full suite on `core/` changes.
- Risk of "leaky abstractions" — discipline required to keep `core/` market-agnostic. Mitigation: lint rule (e.g., `core/` must not import from `markets/`), code review checklist.
- Folder name "MyMoneyWent" is global-leaning. Possible follow-up: rename folder to brand-neutral name (e.g., `fintrack-platform/`) — separate decision, not blocked by this ADR.

### Neutral / TBD

- Some shared docs may need to grow market-specific sections (e.g., `tdd.md` currently VN-only). Address when Phase 1 refactor starts.
- Pricing framework in `core/pricing/` needs to handle both VND and USD with different annual-discount semantics — designable, not blocking.

## Alternatives considered

| Alternative | Rejected because |
|---|---|
| **Split into 2 repos now** | Phase 1-2 not started, no shared code to protect, solo founder, Global unvalidated |
| **Keep monorepo, no `markets/` separation, `if market == ...` everywhere** | Scattered conditionals don't scale past 5-10 sites; tests harder; new market = touch everywhere |
| **Shared library + 2 thin app repos** | Shared lib versioning + coordination overhead; premature for solo founder pre-MVP |
| **Microservices per market** | Massive over-engineering for solo founder pre-MVP; deploy/observability complexity |
| **Plugin architecture (markets as plugins discovered at runtime)** | Reflection-based discovery hard to type-check; over-engineered for 2 markets |

## Implementation notes

This ADR is **target architecture for Phase 1 refactor**, not a description of current state. Current code is single-tenant VN-flavored:

```
MyMoneyWent/  (current)
├── main.py                    # Single-tenant entry
├── handlers/
│   ├── sepay.py               # VN-specific (will move to markets/vn/capture/)
│   ├── email_parser.py        # VN-specific (will move to markets/vn/capture/)
│   ├── transaction.py         # Shared (will move to core/ or handlers/)
│   ├── reports.py             # Shared
│   ├── manage.py              # Shared
│   └── allocation.py          # VN-flavored (refactor target)
├── sheets.py                  # Legacy GAS integration
└── ...
```

**Phase 1-2 refactor work** (per brd-vi.md and brd-en.md roadmaps):
1. Extract `core/messenger/interface.py` → make Telegram/Discord/Messenger adapters interchangeable
2. Multi-tenant DB schema (`users`, `channels`, `tenants`, market column)
3. Move `handlers/sepay.py` → `markets/vn/capture/sepay_webhook.py`
4. Move `handlers/email_parser.py` → `markets/vn/capture/email_vn_banks.py`
5. Stub `markets/global/capture/plaid.py` (interface only, implementation pending Global validation)
6. Add lint rule preventing `core/` from importing `markets/`

**Acceptance criteria for ADR adoption:**
- ☐ This ADR linked from README, market-strategy-overview, brd-vi, brd-en
- ☐ Phase 1 refactor follows `core/ + markets/` structure
- ☐ Lint rule enforces `core/` market-agnostic discipline
- ☐ Re-evaluation reminder set for Q3 2026

## Changelog

| Date | Change |
|---|---|
| 2026-05-10 | v1.0 — Initial decision after founder Q on 2026-05-10. Rejected split-now in favor of monorepo + adapter pattern with 7 explicit re-evaluation triggers. |
