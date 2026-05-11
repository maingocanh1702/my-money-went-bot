# MyMoneyWent

> SaaS fintech consumer + business — **dual-market strategy**: VN (primary, near-term) + Global (parallel track, validation phase).

**Markets:**
- 🇻🇳 **VN market** (primary): SePay webhook + email parsing bank emails. ICP: office worker / freelancer / online seller. Branding: Tiền Về Nơi Đâu. Spec: [brd-vi.md v3.1.0](docs/brd-vi.md).
- 🌐 **Global market** (parallel, validation phase): Plaid/TrueLayer/Tink + e-commerce platform APIs (Stripe/PayPal/Shopify/Etsy/Amazon SP-API) + payout email parsing. ICP: e-commerce solopreneur. Branding: My Money Went. Spec: [brd-en.md v4.0.0](docs/brd-en.md). Strategic background: [strategic-pivot-global.md](docs/strategic-pivot-global.md).

**Channels:** Telegram + Discord + Messenger shared cho cả 2 markets (qua `messenger.send()` interface). **Zalo VN-exclusive** (Phase 3+). WhatsApp global-only (Phase 2).

→ **Read [Market Strategy Overview](docs/market-strategy-overview.md) first** to understand how the 2 tracks coexist.

**Status:** Pre-development. VN track ready cho Phase 1 SaaS foundation refactor (brd-vi.md v3.1.0 + 5 critical specs written ✅: admin tools v1.1.0, DR runbook v1.2.0, observability v1.1.0, Messenger channel v1.1.1, VietQR+email impl plan v1.0.0). Global track pending validation sprint per brd-en.md Section 11. Phase 1-2 foundation work (multi-tenant DB, messenger interface, auth) is **shared infrastructure** for both tracks.
**Target launch (VN):** Tháng 9/2026 — Telegram + Discord MVP, Messenger Phase 3+
**Target launch (Global):** TBD post-validation

---

## Quick links

- ⭐ [**Market Strategy Overview** — VN vs Global](docs/market-strategy-overview.md) — read first
- 🇻🇳 [**BRD v3.1.0 — VN canonical spec** (Tiền Về Nơi Đâu)](docs/brd-vi.md)
- 🌐 [**BRD v4.0.0 — Global canonical spec** (My Money Went)](docs/brd-en.md) — pending validation
- [Strategic rationale — Global market](docs/strategic-pivot-global.md) — background for brd-en.md
- 🇻🇳 [PRD-VI v1.7.1 — VN product requirements](docs/prd-vi.md)
- 🇻🇳 [TDD-VI v1.8.1 — VN technical design](docs/tdd-vi.md)
- 🌐 [PRD-EN v2.0.0 — Global product requirements](docs/prd-en.md)
- 🌐 [TDD-EN v1.0.0 — Global technical design](docs/tdd-en.md)
- [Persona Hùng+ deep dive](docs/research/persona-business-deep-dive.md)
- [Pricing tier redesign](docs/strategy/pricing-redesign.md)
- [Cost projection (Railway)](docs/strategy/cost-projection.md)
- [Feature spec: Personal vs Business toggle](docs/features/feature-personal-business-toggle.md)
- [Feature spec: Refactor personal → SaaS multi-tenant v1.3.0](docs/features/feature-saas-refactor.md)
- [Feature spec: Payment via bank transfer v1.3.0 (SePay + Email auto-detect + VietQR)](docs/features/feature-payment.md)
- [Feature spec: Multi-channel Messenger v1.1.1](docs/features/feature-messenger-channel.md)
- [Implementation plan: Messenger channel build v1.0.0](docs/implementation-plans/implementation-plan-messenger.md)
- [Decision: Onboarding UI strategy (chat-only vs web)](docs/adr/0002-onboarding-ui-strategy.md)
- [Implementation plan: VietQR + email parallel v1.0.0](docs/implementation-plans/implementation-plan-payment-vietqr-email.md)
- [Implementation plan: scale to 500 users and more v1.3.0](docs/implementation-plans/implementation-plan-500-users-and-more.md)
- [Feature spec: Admin tools & audit v1.1.0](docs/features/feature-admin-tools.md)
- [Runbook: Disaster recovery v1.2.0](docs/runbooks/disaster-recovery.md)
- [Observability plan v1.1.0](docs/operations/observability-plan.md)

## Product summary (VN market — per [brd-vi.md v3.1.0](docs/brd-vi.md))

Bot Telegram + Discord tự động track giao dịch ngân hàng VN. 3 entry path cover full TAM:

1. **SePay quick connect** — user đã có SePay → 2-5 phút setup
2. **SePay setup wizard** — user chưa có → bot guide step-by-step (10-15 phút)
3. **Email forwarding parser** — user chỉ muốn dùng email → forward bank email tới `u<id>@in.tienvenoidau.com`, bot parse tự động (6 banks MVP: TCB, Cake, ACB, Sacombank/STB, BIDV, MB; VCB Phase 2 pending verification)

3-tier pricing: **Free** (45 tx/tháng, 1 bank) / **Pro 79k VND** (~$3.16, 3 banks, reports, CSV) / **Business 199k VND** (~$7.96, 5 banks, P&L, Personal-vs-Business split, Sheets sync).

## Personas

- **Minh** (24-35, nhân viên văn phòng) — Free → Pro
- **Linh** (22-30, freelancer) — Pro
- **Hùng+** (28-42, online seller / chủ shop nhỏ) — Business *(revenue driver)*

## Tech stack (Phase 1 onwards)

- Backend: Python + python-telegram-bot
- Database: PostgreSQL (multi-tenant)
- Hosting: Railway Hobby plan (~$15-20/mo MVP)
- Email parsing: Postmark Inbound ($10/mo)
- Payment: **Bank transfer + auto-detect** qua SePay (primary, ≤60s) + Email parsing (backup, ≤5min). 0% fee. Xem [feature-spec-payment-bank-transfer.md](docs/features/feature-payment.md). PayPal/USDT optional secondary Phase 2.
- Backup: Backblaze B2

## Development setup

Python 3.11+. Setup dev environment:

```bash
# 1. Create venv (recommended)
python3.11 -m venv .venv && source .venv/bin/activate

# 2. Install runtime + dev deps
pip install -r requirements.txt        # runtime (FastAPI, gspread, httpx, ...)
pip install -e ".[dev]"                # dev tooling (ruff, black, mypy, import-linter, ...)

# 3. Install pre-commit hooks
pre-commit install

# 4. (First-time) refresh detect-secrets baseline against current repo
detect-secrets scan > .secrets.baseline
```

**Lint + test commands:**

```bash
pre-commit run --all-files     # ruff + black + mypy + detect-secrets + import-linter
lint-imports                    # ADR-0001 boundary check (core ↛ markets)
pytest tests/ -v                # smoke + unit tests
```

**Boundary enforcement:** `core/` MUST NOT import from `markets/`. Verified by `import-linter` (config in `.importlinter`). 3 contracts active:
- `core ↛ markets` (ADR-0001 strict)
- `markets.vn ↛ markets.global_`
- `markets.global_ ↛ markets.vn`

**Note on Python keyword:** the global market package is `markets/global_/` (trailing underscore) because `global` is a Python reserved word. ADR-0001 intent unchanged.

Full workflow doc: [docs/operations/development-workflow.md](docs/operations/development-workflow.md).

## Roadmap (14-16 tuần MVP)

| Phase | Tuần | Deliverable |
|---|---|---|
| 1. Foundation | 1-2 | Repo, DB schema (incl. admin_audit_log), `messenger.send()` interface, multi-user routing |
| 2. Handlers refactor | 3-4 | Multi-tenant handlers via messenger, auth, isolation, admin command framework |
| 3. Pricing logic | 5 | Free limits, trial, upgrade triggers |
| 4. SePay onboarding | 6 | Quick connect + Wizard |
| 5. Email parsing | 7-9 | Postmark + 6 banks parser (TCB, Cake, ACB, STB, BIDV, MB) |
| 6. Polish + Deploy | **10-12** | Payment integration, **admin tools commands**, **observability dashboard + alerts**, Railway deploy, scheduling |
| 7. Closed beta | 13-14 | 5-10 users, validate cost + parser accuracy, DR restore test |
| 8. Soft launch | 15-16 | 20-30 users, monitor 3 path. Buffer absorbed if needed |

Phase 2 (~tháng 11-12): Business tier launch — Personal/Business toggle + Tag-based P&L + Sheets sync (must-have bundle ship đồng thời).

## Architecture decisions

- 🏗️ [**ADR-0001: Monorepo over split repos**](docs/adr/0001-monorepo-not-split-repos.md) (2026-05-10) — single repo cho cả 2 markets, dùng `core/ + markets/vn/ + markets/global/` adapter pattern. Re-evaluate Q3 2026 hoặc sau 7 explicit triggers.

## Repo structure (current — pre-refactor)

Code hiện tại là legacy single-tenant VN. Phase 1-2 refactor sẽ migrate sang target structure (xem section dưới).

```
MyMoneyWent/
├── README.md                  # This file
├── CHANGELOG.md                # Repo-level changelog
├── main.py                    # Entry point (legacy single-tenant — to refactor)
├── config.py                  # Configuration
├── sheets.py                  # Google Sheets integration (legacy)
├── telegram_api.py            # Telegram bot wrapper
├── handlers/                  # Command + event handlers (to refactor multi-tenant)
│   ├── allocation.py
│   ├── email_parser.py        # ⭐ Existing email parser → markets/vn/capture/
│   ├── manage.py
│   ├── reports.py
│   ├── sepay.py               # → markets/vn/capture/sepay_webhook.py
│   └── transaction.py         # → core/ (shared)
├── requirements.txt, railway.toml, crontab.txt, setup.sh
├── .env.example, .gitignore
└── docs/
    ├── market-strategy-overview.md  # ⭐ READ FIRST — VN vs Global tracks
    ├── strategic-pivot-global.md    # Global market strategic background
    ├── brd-vi.md              # 🇻🇳 VN canonical BRD v3.1.0 (Tiền Về Nơi Đâu)
    ├── brd-en.md              # 🌐 Global canonical BRD v4.0.0 (My Money Went)
    ├── prd-vi.md              # 🇻🇳 VN PRD v1.7.1
    ├── prd-en.md              # 🌐 Global PRD v2.0.0
    ├── tdd-vi.md              # 🇻🇳 VN TDD v1.8.1
    ├── tdd-en.md              # 🌐 Global TDD v1.0.0
    ├── adr/                   # Architecture Decision Records
    │   ├── 0001-monorepo-not-split-repos.md
    │   └── 0002-onboarding-ui-strategy.md
    ├── features/              # 16 feature specs (kebab-case)
    │   ├── feature-admin-tools.md, feature-categorization.md, ...
    │   └── BE/                # 15 backend tech specs
    ├── implementation-plans/  # 4 implementation plans
    │   ├── implementation-plan-telegram.md, implementation-plan-messenger.md
    │   ├── implementation-plan-payment-vietqr-email.md
    │   └── implementation-plan-500-users-and-more.md
    ├── strategy/              # Pricing + cost projections
    │   ├── pricing-redesign.md
    │   └── cost-projection.md
    ├── operations/            # Production ops
    │   └── observability-plan.md
    ├── runbooks/              # Operational runbooks
    │   └── disaster-recovery.md
    ├── marketing/             # Landing page + marketing assets
    │   ├── landing-page-handoff-vi.md
    │   └── landing-page-handoff-en.md
    ├── reviews/               # Code reviews
    │   └── review-bank-account-tracking.md
    ├── research/              # All competitive/user research consolidated
    │   ├── 2026-05-07-competitive-round1/   # was plans/reports/
    │   ├── 2026-05-08-feature-landscape-round3/  # was assets/research/
    │   ├── persona-business-deep-dive.md
    │   ├── competitive-pricing-research.md
    │   ├── researcher-{ynab,monarch,copilot,money-lover,spendee}.md
    │   └── ... (18 docs total)
    └── archive/               # Original Bot Finance docs + early SaaS planning + restructure history
                                # Includes: brd-fintrack-v2.9.0-archived.md (legacy FinTrack BRD,
                                # superseded by brd-vi.md + brd-en.md split)
```

## Repo structure (target — Phase 1 refactor goal, per ADR-0001)

```
MyMoneyWent/
├── core/                      # Market-agnostic foundation — both markets reuse
│   ├── messenger/             # Telegram + Discord + Messenger adapters
│   ├── auth/                  # Multi-tenant auth, channel_user_id resolution
│   ├── db/                    # Multi-tenant schema, migrations
│   ├── tenant_context.py      # Resolves user's market → routes to markets/<m>/
│   ├── pricing/               # Generic tier framework
│   ├── categorization/        # Generic rules engine
│   └── observability/
├── markets/
│   ├── vn/                    # 🇻🇳 Tiền Về Nơi Đâu
│   │   ├── capture/           # SePay webhook + VN bank email parsers
│   │   ├── payment/           # VietQR + bank transfer auto-detect
│   │   ├── pricing/tiers_vnd.py  # $4 / $9 in VND
│   │   ├── channels/zalo.py   # VN-only channel
│   │   └── locale/            # Vietnamese strings
│   └── global/                # 🌐 My Money Went
│       ├── capture/           # Plaid + TrueLayer + Tink + Stripe/PayPal/Shopify/Etsy/Amazon
│       ├── payment/stripe_billing.py
│       ├── pricing/tiers_usd.py  # $6 / $12 + annual
│       ├── web_dashboard/     # Next.js + Supabase (Global-only MVP)
│       └── locale/
├── handlers/                  # Common command/event handlers (refactored Phase 2)
├── tests/{core,markets}/
└── docs/                      # (same as current)
```

**Lint rule:** `core/` MUST NOT import from `markets/`. Adapter dispatch happens at one boundary (`core/tenant_context.py`).

## Migration from Bot Finance

Repo này được fork từ `Bot Finance/` (personal bot). Strategy:

1. ✅ Copy tất cả source code + config làm baseline
2. ✅ Copy main BRD + supporting docs vào `docs/`
3. ✅ Archive original planning docs vào `docs/archive/` cho reference
4. ⏳ Phase 1: Migrate single-tenant → multi-tenant DB schema
5. ⏳ Phase 1: Import founder's existing data (Apr 2026 onwards) làm test cohort

**Original Bot Finance repo:** giữ nguyên ở `/Users/maingocanh/Projects/Bot Finance` làm reference + để founder vẫn tiếp tục dùng cho personal trong giai đoạn dev.

## Validation gates (VN track — must pass before next phase)

> Global track has its own validation plan in [brd-en.md Section 11](docs/brd-en.md) (50-100 user survey + 10 interviews + Plaid sandbox quote + Stripe Connect partner application).

| Gate | Threshold | Phase |
|---|---|---|
| Customer interview Hùng+ | ≥4/7 structured interviews confirm pain "đập đầu Excel cuối tháng" | Before scaling beyond Phase 1 foundation |
| MVP cost validation | Actual ≤ $25/mo @ 10-20 users | Phase 7 |
| Email parser accuracy | ≥85% per bank (TCB, Cake, ACB, STB, BIDV, MB) | Phase 5 |
| Backup recovery test | Pass full restore vào staging | Phase 7 |
| Onboarding completion | ≥80% complete trong 1 session | Phase 8 |
| **Hộ kinh doanh registration** | Hoàn tất đăng ký + có MST | **Pre-Phase 6 (BLOCKER cho launch)** |
| Payment match accuracy | Layer 1 ≥95%, Layer 4 manual ≤5% | Phase 6-7 |
| Error budget | Rolling 30-day error rate < 0.1% | Phase 7 onwards |
| Cost margin | > 50% sustained ở 100 users | Phase 8 |
| `@FinTrackUpdates` channel | Created + 1 test announcement | Pre-launch |
| Business tier validation | ≥3/5 concierge user nói "trả $9/mo" | Trước Phase 2 (post-launch) |

## Decision log

- **2026-05-05:** Decision lock B+C combined (email parsing + SePay wizard trong MVP). Trade-off: timeline 14-16 tuần, cost +$10/mo Postmark, đổi lại full TAM coverage. Lý do: runway >5 tháng, 6 Hùng+ chat informal signal đủ để start Phase 1 foundation; structured validation gate vẫn cần pass trước khi scale/build Business tier assumptions.
- **2026-05-05:** Decision lock **bank transfer auto-detect** làm payment primary (0% fee, reuse SePay+email infra). PayPal/USDT defer Phase 2. Hộ kinh doanh registration là pre-launch blocker (lead time 1-2 tuần, start ngay). Detail: [feature-spec-payment-bank-transfer.md](docs/features/feature-payment.md).
- **2026-05-10:** Decision lock **dual-market structure** với 2 BRD canonical riêng biệt: brd-vi.md (VN) + brd-en.md (Global). Legacy brd.md (FinTrack v2.9.0) archived. Channel architecture confirmed shared (Telegram + Discord + Messenger), Zalo VN-exclusive Phase 3+, WhatsApp Global-only Phase 2. brd-en.md promoted from strategic-pivot-global.md với Plaid + e-commerce APIs stack, e-commerce solopreneur ICP, $6/$12 pricing.

## Contact

- Founder: Ngoc-Anh
- Repo: `/Users/maingocanh/Projects/MyMoneyWent`
