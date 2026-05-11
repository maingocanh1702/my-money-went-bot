# Changelog

All notable changes to MyMoneyWent are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html) where applicable. Pre-release pre-development phase has no formal version yet — entries below are dated.

## Conventions

- **Repo-level changes:** structural moves, doc restructure, tooling, repo hygiene → in this file
- **BRD/PRD/TDD/feature spec changes:** in their own changelog tables at the bottom of each doc
- **Code changes (post Phase 1):** standard `[Added]`, `[Changed]`, `[Fixed]`, `[Removed]`, `[Deprecated]`, `[Security]` sections per release

---

## [Unreleased]

### Phase 1 — Foundation refactor (target: Tuần 1-2)

Pending. Per [BRD-VI v3.1.0](docs/brd-vi.md) Phase 1.

---

## 2026-05-11 — F01 W0.1: Repo skeleton + lint boundary (Wave 0)

### Added
- `pyproject.toml` — project metadata (name=mymoneywent, version=0.0.1, py>=3.11) + tool configs (ruff/black/mypy/pytest) + `[project.optional-dependencies.dev]`. Legacy code excluded from strict checks via `extend-exclude` (will be cleaned in W0.6). Runtime deps stay in `requirements.txt` for Railway nixpacks compat.
- `requirements-dev.txt` — pointer to `-e .[dev]`.
- `core/__init__.py`, `markets/__init__.py`, `markets/vn/__init__.py`, `markets/global_/__init__.py` — empty package skeletons với module docstring giải thích boundary rule. **Note:** `markets/global_/` dùng trailing underscore vì `global` là Python reserved keyword (ADR-0001 intent unchanged).
- `tests/__init__.py`, `tests/test_import_boundary.py` — 3 smoke tests: config exists, positive run clean, **negative test** (deliberate `core → markets` violation phải bị catch).
- `.pre-commit-config.yaml` — hooks: ruff (lint+fix), black (format), mypy (strict on core/markets/tests), detect-secrets (against `.secrets.baseline`), import-linter (lint-imports).
- `.importlinter` — 3 contracts: `core ↛ markets` (ADR-0001 strict), `markets.vn ↮ markets.global_` (market isolation 2 chiều).
- `.secrets.baseline` — detect-secrets baseline với 22 plugins enabled. User runs `detect-secrets scan > .secrets.baseline` để populate against current repo.
- `.github/workflows/ci.yml` — GitHub Actions trên push main + PR: pre-commit (all files) → lint-imports → pytest. Python 3.11, timeout 10min.

### Changed
- `README.md` — thêm section "Development setup" với install commands, lint/test commands, boundary rule note, link đến workflow doc.

### Verified locally
- `ruff check core/ markets/ tests/`: All checks passed
- `black --check core/ markets/ tests/`: 6 files unchanged
- `mypy core/ markets/ tests/`: Success, no issues found in 6 source files
- `lint-imports`: 3 contracts kept, 0 broken
- **Negative test:** deliberate `core/_test_violation.py` with `from markets import vn` → lint-imports correctly reports "core MUST NOT import from markets (ADR-0001) BROKEN", exit 1. Boundary enforced.

### Notes
- W0.1 = first PR của Wave 0 split (6 PRs sequential per docs/operations/development-workflow.md §4). No business logic, no DB schema. Boring foundation.
- Pre-commit uses **black for format, ruff for lint only** (dropped `ruff-format` hook để tránh conflict với black).
- Next PR: W0.2 — alembic migration framework + initial schema (depends Gap 1 decision = YES per project_wave0_gap_decisions.md memory).

### Fixed (post-Codex adversarial review)
- **[HIGH] `tests/test_import_boundary.py` negative test race** — rewrite negative test: thay vì write violation file vào `core/_test_boundary_violation.py` (real package tree, race-prone), build isolated mini-project trong `tmp_path` với synthetic `.importlinter` config + plant violation ở đó. Thêm `test_real_config_declares_core_markets_contract` static check để guard against accidental removal of contract block. 4 tests, all pass; verified KHÔNG còn leftover file trong `core/`.
- **[MED] GitHub Actions floating tags** — `.github/workflows/ci.yml`: pin `actions/checkout@v4` → `@11bd71901bbe5b1630ceea73d27597364c9af683` (v4.2.2), `actions/setup-python@v5` → `@0b93645e9fea7318ecaed2b359559ac225c90a2b` (v5.3.0). Comment ghi rõ SemVer tag để readable. Thêm `.github/dependabot.yml` để auto-bump SHAs hằng tuần.
- **[MED] Empty `.secrets.baseline`** — chạy thật `detect-secrets scan` toàn repo. Found 2 false positives trong legacy code: (1) `docs/tdd-vi.md:647` placeholder `postgresql://user:pass@host:5432/fintrack` trong env var doc; (2) `google_apps_script.js:19` template string `"your_random_email_secret_here"`. Cả 2 đã audit + marked `is_secret: false` trong baseline. New secrets in future commits sẽ bị block.
- **[P2 mini-review] Static contract test quá permissive** — Codex mini-review trên fix diff phát hiện `test_real_config_declares_core_markets_contract` chỉ substring-match `"type = forbidden"`, `"core"`, `"markets"` trên toàn file text → một edit weakening contract (vd đổi source_modules sang `handlers`) vẫn pass nhờ decoy tokens ở sections khác. Rewrite dùng `configparser` parse exact section `[importlinter:contract:core-must-not-import-markets]`, assert `type == 'forbidden'`, `source_modules == ['core']` (exact list), `forbidden_modules == ['markets']` (exact list). Không còn substring lurking attack surface.

---

## 2026-05-11 — Development workflow doc

### Added
- `docs/operations/development-workflow.md` v1.0.0 — Quy trình code-review-test per-feature (10 steps: spec → test plan → code+test → codex review → fix → CHANGELOG → PR → squash-merge → tag). Wave 0-6 dependency graph cho 16 feature spec (Wave 0 F-saas-refactor là blocker; F08 → F02 sequential trong Wave 2; F-discord/F-messenger parallel với Wave ≥3). Test strategy 3 layer (unit / integration real-Postgres / contract tests cho `messenger.send()` + `bank_email_parser` plugin), tenant isolation test mandatory. PR template + branch naming `feat/F##-name` + tag pattern `v0.X.0-F##`. Skills mapping (`engineering:testing-strategy`, `engineering:debug`, etc.). Anti-patterns + revise triggers.

---

## 2026-05-11 — Feature spec: Funding Sources (F08)

### Added
- `docs/features/feature-funding-sources.md` v1.0.0 — FE/UX spec cho tracking transaction theo từng bank account, debit/credit card, ví điện tử. VN market (SePay + email). Single `funding_sources` entity với canonical identity `(user_id, kind, bank, last4)`, status enum `(active/hidden/archived)`, auto-discovery embed-in-picker UX, `/accounts` command (list / rename / hide / manual-add), `/reports account=<display_id>` filter (Option A: explicit lookup match cả active + hidden, ambiguity → disambiguation prompt, power-syntax `kind:display_id` bypass). FK chain: `users→fs` CASCADE, `tx.fs_id→fs` SET NULL (retention của tx do TDD §6.3 quyết).
- `docs/features/BE/feature-funding-sources-tech.md` v1.0.0 — BE tech doc: Postgres DDL với check constraints, transitional Sheets schema (worksheet + col Q FK mirror), UPSERT_SQL canonical (CTE-based `was_resurrected` detection, `COALESCE(..., FALSE)` strict bool), TOUCH_SQL cho cache-hit path xử lý multi-process resurrect race, inference rules cho credit_card / e_wallet, backfill script với `kind='bank_account'` constraint, 30 test cases với subcases (cross-kind race, hidden vs archived, ambiguity, resolve failure, embed/delayed notification, last4 validation).

### Changed
- `docs/features/feature-transaction-capture.md` v1.0.1 → **v1.1.0** — F08 integration: pipeline diagram + acceptance criteria require fs resolve trước tx INSERT, FK `funding_source_id` populated, fallback NULL khi resolve fail. §4 schema bổ sung column `funding_source_id INTEGER REFERENCES funding_sources(id) ON DELETE SET NULL` (F08 extension) + ownership note. Discovery message embed làm header trong category picker (1 message).
- `docs/features/BE/feature-transaction-capture-tech.md` v1.0.0 → **v1.1.0** — `process_transaction()` rewrite (resolve trước INSERT, try/except fallback NULL, discovery header prepend vào picker, delayed resurrect notif). §2.1 INSERT query thêm column `funding_source_id` ($9). Test plan +3 cases.

### Notes
- F08 xây trên F02 — không breaking change column P (`bank_account` string) hiện tại; thêm 1 entity registry bên trên.
- TDD-vi §2.1 chưa update — schema `funding_sources` sẽ promote vào TDD khi bump version kế tiếp.
- Spec locked sau nhiều round in-session tech review (canonical identity, status enum, FK chain, cache resurrect race, COALESCE bool); chi tiết technical decisions xem changelog trong từng spec file.

---

## 2026-05-10 (afternoon) — Repo cleanup pass 2

### Added
- `__pycache__/` explicit entry in `.gitignore` (was caught by `*.py[cod]` glob but folder name now ignored explicitly)
- `docs/strategy/` — pricing + cost projection docs grouped
- `docs/operations/` — production ops docs grouped
- `docs/marketing/` — landing page + marketing assets grouped
- `docs/adr/0002-onboarding-ui-strategy.md` — promoted from `decision-onboarding-ui-strategy.md`
- `docs/research/2026-05-07-competitive-round1/` — consolidated from `plans/reports/`
- `docs/research/2026-05-08-feature-landscape-round3/` — consolidated from `assets/research/`

### Changed
- 📝 **Naming convention standardized to kebab-case** across all docs:
  - 16 `feature_*.md` → `feature-*.md` in `docs/features/`
  - 15 `feature_*_tech.md` → `feature-*-tech.md` in `docs/features/BE/`
  - 2 `implementation_plan_*.md` → `implementation-plan-*.md` in `docs/implementation-plans/`
  - All cross-refs across the repo bulk-updated
- 📂 **Implementation plans consolidated** — 4 files all now in `docs/implementation-plans/` (was split between `docs/` and `docs/implementation-plans/`)
- 📂 **Research consolidated** — 3 locations (`docs/research/`, `plans/reports/`, `assets/research/`) merged into single `docs/research/` with date-based subfolders
- 📂 **docs/ root categorized** — 12 loose files grouped into `strategy/`, `operations/`, `marketing/`, `adr/`, `research/` subfolders. Only canonical specs (BRD/PRD/TDD x 2 markets + market-strategy-overview + strategic-pivot-global) remain at `docs/` root

### Moved
- `docs/cost-projection.md` → `docs/strategy/cost-projection.md`
- `docs/pricing-redesign.md` → `docs/strategy/pricing-redesign.md`
- `docs/observability-plan.md` → `docs/operations/observability-plan.md`
- `docs/landing-page-handoff-{en,vi}.md` → `docs/marketing/landing-page-handoff-{en,vi}.md`
- `docs/persona-business-deep-dive.md` → `docs/research/persona-business-deep-dive.md`
- `docs/decision-onboarding-ui-strategy.md` → `docs/adr/0002-onboarding-ui-strategy.md` (promoted to ADR)
- `docs/competitive-pricing-research.md` → `docs/research/competitive-pricing-research.md`
- `docs/implementation-plan-500-users-and-more.md` → `docs/implementation-plans/implementation-plan-500-users-and-more.md`
- `docs/implementation-plan-payment-vietqr-email.md` → `docs/implementation-plans/implementation-plan-payment-vietqr-email.md`
- `updates/2026-04-05.md` → `docs/archive/updates/2026-04-05.md`
- `plans/reports/*` → `docs/research/2026-05-07-competitive-round1/`
- `assets/research/2026-05-08-feature-landscape-round3/` → `docs/research/2026-05-08-feature-landscape-round3/`

### Removed (empty folders left behind by mv — user can `rm -rf` on Mac)
- `plans/reports/` (empty — now in research/)
- `assets/research/` (empty — now in research/)
- `updates/` (empty — file moved to archive)

### Fixed
- 26 docs had broken refs to `docs/prd.md` / `docs/tdd.md` after split → bulk-updated to `docs/prd-vi.md` / `docs/tdd-vi.md`
- Updated cross-refs for all moved files (~100 cross-refs across 30+ docs)

---

## 2026-05-10 — Repo hygiene + dual-market structure

### Added

- 📄 **CHANGELOG.md** — this file (per founder rules: bắt buộc có README + CHANGELOG)
- 📄 **[docs/market-strategy-overview.md](docs/market-strategy-overview.md)** v1.0 → v1.1.0 — entry-point doc explaining VN vs Global track coexistence; updated channel comparison (shared platforms + Zalo VN-only)
- 📄 **[docs/brd-en.md](docs/brd-en.md) v4.0.0** — formal Global market BRD (My Money Went). Promoted from `strategic-pivot-global.md`. ICP: e-commerce solopreneur. Capture stack: Plaid/TrueLayer/Tink + Stripe/PayPal/Shopify/Etsy/Amazon SP-API + payout email parsing. Pricing: $6 Pro / $12 Solopreneur + annual plans. Channels: Telegram + Discord + Messenger MVP + read-only web dashboard.
- 📄 **[docs/adr/0001-monorepo-not-split-repos.md](docs/adr/0001-monorepo-not-split-repos.md)** — Architecture Decision Record locking monorepo + `core/ + markets/vn/ + markets/global/` adapter pattern. 7 explicit re-evaluation triggers. Q3 2026 default review.
- 📁 **`docs/adr/`** — new folder for Architecture Decision Records
- 📁 **`docs/research/`** entries — moved 9 strategy/research docs from root to organize repo

### Changed

- 📝 **[docs/brd-vi.md](docs/brd-vi.md) v3.1.0** — added 🌐 SCOPE NOTE clarifying this is canonical VN spec (Tiền Về Nơi Đâu); added 🏗️ CODE STRUCTURE note locking VN code path at `markets/vn/` per ADR-0001; channel architecture clarified
- 📝 **[README.md](README.md)** — markets section reframed as dual-market (VN primary + Global parallel); quick links restructured (BRD-VI + BRD-EN canonical, brd.md archived); architecture decisions section added; repo structure tree split into "current pre-refactor" + "target Phase 1 goal"; decision log entry for 2026-05-10
- 📝 **[strategic-pivot-global.md](docs/strategic-pivot-global.md)** v1.0 → v1.2 — title changed from "Strategic Pivot Analysis" to "Global Market Strategy"; reframed as parallel global track (NOT replacement of VN); status updated to "Promoted into formal BRD" pointing to brd-en.md; moved from repo root to `docs/`
- 📂 **Doc structure** — `docs/brd.md` (FinTrack v2.9.0) archived → `docs/archive/brd-fintrack-v2.9.0-archived.md`; replaced by canonical pair brd-vi.md (VN) + brd-en.md (Global)
- 📂 **Path fix** — bulk replaced 20 doc cross-refs from `docs/brd.md` → `docs/brd-vi.md` to keep links resolving after archive
- 📂 **`strategic-pivot-global.md` location** — moved from repo root to `docs/`; all cross-refs updated (`../strategic-pivot-global.md` → `./strategic-pivot-global.md` for docs/, `strategic-pivot-global.md` → `docs/strategic-pivot-global.md` for README)

### Removed (moved to archive)

- 🗑️ **40 root-level duplicate files** moved to `docs/archive/root-duplicates-2026-05-10/`:
  - Stale BRDs/PRDs at root (older versions than docs/): `brd-en.md` v2.8.0, `brd-vi.md` v3.1.0/2026-05-07, `prd-en.md` v1.5.0, `prd-vi.md` v1.5.0
  - 30 duplicate feature_*.md (identical to docs/features/ + docs/features/BE/)
  - 4 duplicate implementation plans (root vs docs/ + docs/implementation-plans/)
  - 2 identical duplicates: `persona-business-deep-dive.md`, `pricing-redesign.md`
  - 2 Office lock files (`~$c1-...docx`, `~$c2-...docx`)
- 🗑️ **`docs/brd.md` (FinTrack v2.9.0)** — archived to `docs/archive/brd-fintrack-v2.9.0-archived.md` (legacy FinTrack BRD; superseded by brd-vi.md + brd-en.md split)

### Moved (to better location)

- 📦 **9 research/strategy docs** from root → `docs/research/`:
  - `competitive-analysis-solopreneur-lite-tools-may2026.md`
  - `competitive-intelligence-report.md`
  - `insights-from-competitive-research.md`
  - `research-prompt-competitor-analysis.md`
  - `research-prompt-features-deep-dive.md`
  - `research-prompt-round-2.md`
  - `Doc1-Market-Analysis-Vendor-Strategy.{md,docx}`
  - `Doc2-User-Research-Findings-Plan.{md,docx}`
- 📦 **`strategic-pivot-global.md`** from root → `docs/` (cleaner repo root, all docs together)

### Fixed

- 🔧 **Broken `docs/brd.md` cross-refs** — 20 docs updated from `docs/brd.md` → `docs/brd-vi.md` after BRD archive

### Decision log (key product decisions, not just structural)

- ✅ **Dual-market structure locked:** brd-vi.md (VN, Tiền Về Nơi Đâu) + brd-en.md (Global, My Money Went) as canonical sibling BRDs. Channel architecture confirmed shared (Telegram + Discord + Messenger), Zalo VN-exclusive Phase 3+, WhatsApp Global-only Phase 2.
- ✅ **Monorepo over split repos:** per ADR-0001, single repo with `core/ + markets/vn/ + markets/global/` adapter pattern. Re-evaluate Q3 2026 or sooner if any of 7 triggers fires.
- ✅ **brd-en.md content rewritten:** discarded VN-derived content (SePay, VN banks, Hùng+ persona). Promoted strategic-pivot-global.md into formal BRD form with Plaid + e-commerce APIs + solopreneur ICP + $6/$12 pricing.

---

## 2026-05-07 — Pre-restructure baseline

### Background

Before 2026-05-10 restructure, the project had:

- Single BRD (`docs/brd.md` v2.9.0, FinTrack branding) for VN market
- Strategic exploration doc (`strategic-pivot-global.md`) at repo root proposing pivot to Global market
- Multiple duplicate copies of docs at repo root + `docs/`
- 30 feature_*.md files duplicated at root + docs/features/
- Office lock files committed accidentally

State as of 2026-05-07:

- **BRD-vi.md v3.1.0** existed as Vietnamese branding ("Tiền Về Nơi Đâu") with v3.x version drift from FinTrack BRD v2.9.0
- **strategic-pivot-global.md** v1.0 framing was "pivot from VN to Global" — superseded 2026-05-10 with parallel-track framing

---

## Reference: Per-doc changelogs

For doc-level changes (BRD/PRD/TDD/feature specs), see the changelog table at the bottom of each doc:

- [BRD-VI changelog](docs/brd-vi.md#changelog)
- [BRD-EN changelog](docs/brd-en.md#changelog)
- [Strategic-pivot-global changelog](docs/strategic-pivot-global.md#changelog)
- [Market-strategy-overview changelog](docs/market-strategy-overview.md#changelog)
- [ADR-0001 changelog](docs/adr/0001-monorepo-not-split-repos.md#changelog)
