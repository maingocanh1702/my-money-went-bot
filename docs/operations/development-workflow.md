# Development Workflow — MyMoneyWent

> **Version:** v1.0.0
> **Ngày tạo:** 2026-05-11
> **Trạng thái:** Active
> **Owner:** Founder (dev)
> **Mục đích:** Quy trình code-review-test cho từng feature, từ spec đến merge. Áp dụng cho toàn bộ 16 feature spec hiện có trong `docs/features/`.
> **Tham chiếu:**
> - [ADR-0001 Monorepo](../adr/0001-monorepo-not-split-repos.md)
> - [Implementation Plan 500 Users](../implementation-plans/implementation-plan-500-users-and-more.md)
> - [Feature SaaS Refactor](../features/feature-saas-refactor.md)

---

## 1. Nguyên tắc

1. **Spec-first:** không code khi chưa đọc xong `feature-X.md` (FE) + `BE/feature-X-tech.md`. Đây là source of truth.
2. **Cross-model review:** Claude Code viết → Codex review. 2 model bắt lỗi khác nhau; layered defense.
3. **Test cùng phiên:** unit + integration test viết trong cùng session với code, không để Codex catch missing test.
4. **1 feature = 1 branch = 1 PR**, kể cả solo dev — tạo audit trail, attach point cho Codex review, rollback boundary.
5. **Tenant isolation test là mandatory** mỗi feature có truy cập DB. Không có test này → không merge.
6. **Refactor trước, build features sau** (theo ADR-0001 + Wave 0 dưới đây).

---

## 2. Per-feature workflow (10 steps)

```
1. Đọc spec (FE + BE tech doc)
2. Skill: engineering:testing-strategy → draft test plan
3. Plan ngắn 10 dòng (files, tests, contracts, migration risk)
4. Tạo branch  feat/F##-name
5. Code + write tests trong cùng session
   ├─ Unit tests (parsers, rules, formatters)
   ├─ Integration tests (real Postgres)
   └─ Tenant isolation test (BẮT BUỘC nếu chạm DB)
6. Chạy test local pass → commit atomic
7. /codex:review trên branch (logic + perf + security)
8. Nếu bug → fix → /codex:review trên diff fix (mini-review) → test lại
9. CHANGELOG entry + bump spec version nếu cần
   └─ Reminder: in-session iteration KHÔNG bump version
10. PR → squash-merge vào main → tag v0.X.0-F##
```

### 2.1. Step 1 — Đọc spec

- FE spec: `docs/features/feature-<name>.md`
- BE tech spec: `docs/features/BE/feature-<name>-tech.md`
- Nếu spec reference TDD/PRD section → đọc luôn section đó.
- Nếu phát hiện spec gap (missing edge case, ambiguous contract) → **dừng**, update spec trước. Không code dựa trên giả định.

### 2.2. Step 2 — Test plan via skill

Gọi skill `engineering:testing-strategy` với feature spec làm input. Output: list test cases (positive, edge, error, isolation). Save vào working notes (không cần commit).

### 2.3. Step 3 — Plan ngắn

Format 10 dòng tối đa, không hơn:

```
Feature: F## <name>
Files thay đổi: <list>
Migration: <yes/no, script path>
New tables/columns: <list>
Test files: <list>
Integration points: <module nào sẽ call>
Risks: <2-3 dòng>
```

Không cần file riêng — paste vào PR description sau.

### 2.4. Step 4-6 — Code + test

**Code structure target (theo ADR-0001):**
```
core/                  # Market-agnostic
markets/vn/            # SePay, VN bank, VietQR
markets/global/        # Plaid/TrueLayer, Stripe (future)
handlers/              # Channel-agnostic command handlers
tests/
├── unit/              # No DB, no network
├── integration/       # Real Postgres
└── fixtures/          # Sample webhooks, .eml files
```

**Test layer rules:**
- **Unit:** parsers (SePay payload, bank email regex), categorization rules, F08 canonical identity matcher, amount/currency formatter. Fast, no DB.
- **Integration:** real Postgres. **Default: `testcontainers-python`** cho cả CI và local. **Fallback: `pytest-postgresql`** chỉ khi Docker không available trên môi trường local. Không hybrid — chọn 1 default cho consistency, foundation cần deterministic. F02 → F08 resolve → INSERT → query back.
- **Contract tests** cho 2 plugin interface:
  - `messenger.send(user_id, payload)` — Telegram/Discord/Messenger phải pass cùng test suite (bảo vệ adapter pattern).
  - `bank_email_parser` plugin — TCB/MB/Cake/ACB/Sacom/BIDV phải pass cùng schema.
- **Tenant isolation:** 2 user A/B fixture; mọi query A không được thấy data B. Mandatory.

**Fixture strategy:**
- **Real captured fixtures** cho parser realism: SePay webhook payload thật, bank email `.eml` thật mỗi bank (TCB/MB/Cake/ACB/Sacom/BIDV). Đặt vào `tests/fixtures/real/<bank>/`.
- **Synthetic fixtures** cho controlled edge/error cases: missing field, invalid amount, weird date format, duplicate ref, malformed encoding, attacker payload. Đặt vào `tests/fixtures/synthetic/<feature>/`.
- 2 loại song song, không cấm synthetic. Ưu tiên real cho happy path; synthetic cho deterministic edge case không reproduce được bằng real data.

**Atomic commits:** mỗi commit 1 logical change. Ví dụ F-saas-refactor:
- `commit 1`: DDL migration
- `commit 2`: `core/` skeleton + tenant_context.py
- `commit 3`: `markets/vn/` move legacy code
- `commit 4`: channel adapter `BaseSender` ABC
- `commit 5`: `messenger.send()` direct-send impl
- `commit 6`: tests

Per-commit review dễ hơn 1 PR 30 file.

**Atomic commits is for review during PR, not for main history.** Main history dùng squash merge (xem §2.7) — commit-level detail còn lại trong PR (GitHub giữ branch commits sau squash). Atomic giúp Codex review từng logical change; squash giữ main lịch sử sạch + CHANGELOG generation đơn giản. 2 mục tiêu khác nhau, không mâu thuẫn.

### 2.5. Step 7-8 — Codex review

**Scope review:** logic + performance + security (mặc định cả 3).

**Review checklist (Codex apply):**
- Logic: edge cases có cover? Off-by-one? Null handling?
- Performance: N+1 query? Index missing? Pool exhaustion risk?
- Security: SQL injection? Tenant leak (query thiếu `WHERE user_id`)? Secret in code?
- Adapter pattern: `core/` có import từ `markets/`? (cấm theo ADR-0001)
- Tests: tenant isolation có không?

**Bug fix loop:**
- Nếu Codex báo bug → fix → `/codex:review` trên diff fix (mini-review, chỉ review thay đổi mới)
- Bug fix hay tạo bug mới — mini-review là safety net.
- Khi 2 round liên tiếp pass → tiếp Step 9.

### 2.6. Step 9 — CHANGELOG + spec version

**CHANGELOG location (2 nơi, đừng nhầm):**
- **Repo-level: `CHANGELOG.md`** ở repo root — structural moves, repo hygiene, feature merge entries. Format Keep a Changelog.
- **Feature spec changelog:** bảng "Changelog" cuối mỗi `docs/features/feature-X.md` (và `BE/feature-X-tech.md`) — spec content version history.
- Khi merge feature: update repo-level CHANGELOG bắt buộc. Update feature spec changelog NẾU spec có sửa cùng PR.

**Repo-level CHANGELOG entry template:**

```markdown
## YYYY-MM-DD — F##: <feature name>

### Added
- <files mới, modules mới>

### Changed
- <files/specs sửa>

### Notes
- <migration notes, deprecation, rollback steps nếu có>
```

**Spec version bump rule:**
- **During same review session, trước merge:** edit spec content tự do, KHÔNG bump version (theo feedback memory — bump là noise khi chưa ai consume version cũ).
- **Trước khi merge PR:** spec và code PHẢI match. KHÔNG normalize "code lệch spec" như chuyện bình thường.
- **Nếu giữa code phát hiện cần đổi contract:** update spec TRƯỚC, code theo spec mới, cùng 1 PR.
- **Sau merge:** nếu behavior thay đổi sau này → update spec + bump version trong cùng PR sửa code, không tách 2 PR.

### 2.7. Step 10 — PR + merge + tag

**Branch:** `feat/F##-short-name` (vd `feat/F01-saas-refactor`, `feat/F02-transaction-capture`).
**Bug fix branch (rebase vào feature):** `fix/F##-short-issue`.

**PR template:**

```markdown
## Feature
Link spec: docs/features/feature-X.md
Link BE tech: docs/features/BE/feature-X-tech.md

## Plan
<paste 10-line plan from Step 3>

## Test coverage
- Unit: N tests
- Integration: N tests
- Tenant isolation: ✅ / N/A (lý do)

## Codex review
- Round 1: <N issues found>
- Round 2 (fix diff): ✅ clean

## Migration
- <DDL script path> / N/A
- Rollback: <plan>

## CHANGELOG
- ✅ entry added
```

**Merge rule:** squash-merge với commit message `F##: <feature name>` để CHANGELOG generation + `git log --grep=F##` dễ trace. Atomic commits trong branch giúp Codex review (xem §2.4); squash giữ main lịch sử sạch.

**Tagging:**
- **Feature merge: KHÔNG tag mặc định.** Trace bằng PR + CHANGELOG entry là đủ.
- **Milestone deploy** (vd Wave 0 complete, MVP soft launch, MVP GA): tag semantic `v0.X.0` theo SemVer.
- **Optional feature tag** chỉ cho major irreversible migrations: `feature/F08-funding-sources`. Đừng gọi đây là release version — đây là markers, không phải releases.
- Solo dev đừng tag spam. Mỗi tag phải có nghĩa.

---

## 3. Pre-commit hooks (setup Wave 0)

Setup ngay từ F-saas-refactor để Codex không review style. Là 1 trong 5 infrastructure foundations (xem Wave 0 §4):

```yaml
# .pre-commit-config.yaml
- ruff (lint)
- black (format)
- mypy --strict (type check)
- detect-secrets (no secret leaks)
- import-linter (enforce: core/ MUST NOT import from markets/ — bảo vệ ADR-0001)
```

Code phải pass hooks trước khi commit. Codex tập trung logic/perf/security.

---

## 4. Feature dependency graph + parallel slots

### Wave 0 — Foundation (BẮT BUỘC sequential, blocker tất cả)

**Foundation-first KHÔNG có nghĩa là one giant diff.** Wave 0 split thành **6 PR sequential**, mỗi PR reviewable độc lập:

| PR | Scope | Acceptance |
|---|---|---|
| **W0.1 Repo skeleton + lint boundary** | `core/`, `markets/`, `markets/vn/` empty stubs (chỉ `__init__.py`). `pyproject.toml` + `requirements-dev.txt` deps. `.pre-commit-config.yaml` (ruff/black/mypy/import-linter/detect-secrets). `.importlinter` rule "core ↛ markets". `.github/workflows/ci.yml` chạy pre-commit. README setup section. | pre-commit pass; import-linter block sample test PR vi phạm boundary; CI xanh |
| **W0.2 Migration framework + initial schema** | `alembic.ini` + `migrations/env.py` (sqlalchemy[asyncio] env). Migration `0001_initial_schema` với 9-10 tables từ TDD §2.1 (users, categories, transactions, bot_state, bank_connections, scheduled_jobs, monthly_reports, analytics_events, admin_audit_log, +funding_sources nếu Gap 1 = YES). `tests/conftest.py` testcontainers Postgres fixture + tenant isolation helper. | `alembic upgrade head` + `downgrade base` cả 2 OK; testcontainers spin <30s; sample integration test pass |
| **W0.3 DB access layer + tenant_context** | `core/db.py` asyncpg pool factory (min=2, max=10). `core/tenant_context.py` user_id+request_id propagation (contextvar). Sample CRUD ops + cross-tenant assertion helpers. | Sample query `WHERE user_id=$1` pass; cross-tenant test verify 2 user không thấy nhau |
| **W0.4 Messenger adapter interface** | `core/messenger/__init__.py` `send()` entry point. `core/messenger/base.py` `BaseSender` ABC. `core/messenger/telegram.py` TelegramSender impl. Payload schema (TypedDict). Contract test suite (parametrize qua adapter). | Contract test pass với TelegramSender; mock adapter dispatch verify; locale resolution test |
| **W0.5 Logging + health + Sentry** | `core/logging.py` structlog với `user_id`+`request_id` context binding. `core/observability.py` Sentry init + `AsyncioIntegration` + `/health` + `/health/detailed` + request ID middleware. | Structured log có user_id field; sample Sentry event captured với context; `/health` pass; `/health/detailed` report pool state |
| **W0.6 Legacy code move + data migration** | `sheets.py` đập bỏ. `handlers/*` move vào `core/handlers/*` + VN-specific phần (SePay handler, VN email parsers, VietQR) move vào `markets/vn/`. `email_parser.py` refactor thành plugin pattern dưới `markets/vn/email_parsers/`. `telegram_api.py` logic merge vào `core/messenger/telegram.py` (đã có từ W0.4). SePay handler token-based user lookup. `scripts/migrate_sheets.py` chạy 1 lần migrate founder data. | Legacy tests pass với cấu trúc mới; founder existing data migrated 100% (row count verify); import-linter still pass; smoke test end-to-end (webhook → DB → query back) |

**Sequential rule:** W0.1 → W0.2 → W0.3 → W0.4 → W0.5 → W0.6. W0.3/W0.4/W0.5 về lý thuyết có thể parallel sau W0.2, nhưng solo dev recommend serial — context-switch nặng + Codex review queue.

**Gap dependency per PR:**
- W0.1, W0.3, W0.5: không depend gap nào → start ngay.
- W0.2: depend **Gap 1** (F08 column từ Wave 0?).
- W0.4: depend **Gap 4** (messenger payload schema).
- W0.6: depend **Gap 2** (email parser plugin), **Gap 3** (webhook token), **Gap 5** (migration data mapping).

**Tổng estimate:** 7-10 ngày code cho 6 PR.

**Wave 0 acceptance criteria (tổng hợp):**
- pre-commit hook + import-linter block `core/` → `markets/` import vi phạm
- `alembic upgrade head` + `downgrade base` OK; founder data migrated 100%
- 1 sample integration test pass (tenant isolation: User A query không thấy data User B)
- `messenger.send()` contract test pass cho TelegramSender (Discord/Messenger ship Wave 6)
- 1 sample Sentry event capture với `user_id`+`request_id` context
- `/health` + `/health/detailed` endpoint responsive
- Legacy `handlers/*` + `sheets.py` + `email_parser.py` đã move xong; old paths không còn tồn tại trên main

### Wave 1 — User entry (parallel, sau Wave 0)

| Feature | Depend | Parallel với |
|---|---|---|
| F-onboarding | user model | all in wave |
| F-admin-tools | admin schema (đã có ở W0) | all in wave |
| F-i18n | locale storage | all in wave |
| F-settings | user prefs storage | all in wave |

4 cái này độc lập — có thể mở 4 branch song song. Solo dev recommend max 2 branch active để Codex review không queue.

### Wave 2 — Core capture (F08 → F02 sequential)

| Feature | Order | Lý do |
|---|---|---|
| F-funding-sources (F08) | First | F02 phải call `resolve_funding_source()` trước INSERT (theo memory locked) |
| F-transaction-capture (F02) | After F08 | Wire-in F08 resolve function |

**Wave 2 migration rule (F08 owns schema):**
- F08 PR có thể land **service + schema trước**, contract test dùng **fake tx payload** (không cần F02 active). F02 wire-in sau.
- Migration thêm column `transactions.funding_source_id` thuộc **F08 PR**, không phải F02. F02 chỉ thêm logic call resolver.
- **Nếu W0.2 (Wave 0) đã add column** (per Gap 1 = YES): F08 PR chỉ ship `funding_sources` table + logic, KHÔNG migration thêm cho `transactions`. Cleaner.
- **Nếu W0.2 không add column** (per Gap 1 = NO): F08 PR add cả `funding_sources` table + `ALTER TABLE transactions ADD COLUMN funding_source_id` cùng migration.

### Wave 3 — Money management (parallel, sau Wave 2)

| Feature | Depend |
|---|---|
| F-category-management | user model |
| F-categorization | categories + transactions |
| F-personal-business-toggle | settings + user model |

3 cái này có thể song song. Categorization cần categories table có sẵn nhưng giao thoa chỉ ở DDL.

### Wave 4 — Outputs (sequential)

| Feature | Order |
|---|---|
| F-reports | First |
| F-scheduled-jobs | After (monthly digest dùng reports query) |

### Wave 5 — Monetization (sequential)

| Feature | Order |
|---|---|
| F-pricing-tiers | First |
| F-payment | After (cần biết tier price) |

### Wave 6 — Extra channels (parallel với Wave ≥3)

| Feature | Notes |
|---|---|
| F-discord-channel | Dùng adapter pattern từ W0 |
| F-messenger-channel | Dùng adapter pattern từ W0 |

Có thể code parallel với bất kỳ feature Wave 3+ nào vì adapter đã sẵn.

### Parallel rule (solo dev)

- **Max 2 branch active cùng lúc** để Codex review không bị queue và memory context không lẫn.
- **Pattern recommend:** 1 branch "chính" (feature lớn) + 1 branch "filler" (i18n, settings) khi block chính.
- Trong cùng Wave: chọn 2 cái ít overlap nhất (vd Wave 1 chọn onboarding + i18n, không chọn settings + admin-tools vì cả 2 chạm user model).

---

## 5. Skills sử dụng

| Bước | Skill | Khi nào |
|---|---|---|
| Step 2 | `engineering:testing-strategy` | Draft test plan từ spec |
| Step 8 (bug fix) | `engineering:debug` | Khi Codex báo bug khó reproduce |
| Cross-cutting | `engineering:code-review` | Self-review trước khi Codex |
| Refactor | `engineering:architecture` | Khi cần ADR mới (vd ADR-0003+) |
| Pre-deploy | `engineering:deploy-checklist` | Trước khi merge feature lớn |
| Documentation | `engineering:documentation` | Khi viết README per-module |

---

## 6. Anti-patterns (ĐỪNG)

- ❌ Code trước, đọc spec sau. Spec gap discovery giữa session làm scope creep.
- ❌ Mock Postgres trong integration test. Real DB ngay từ đầu — đỡ rework.
- ❌ 1 PR 30 file, chưa atomic. Codex review noise; rollback impossible.
- ❌ Skip tenant isolation test "vì feature nhỏ". Tenant leak là sự cố nghiêm trọng nhất với multi-tenant SaaS.
- ❌ Bump spec version sau mỗi round in-session review. Bump là noise — chỉ bump khi consumer đã pin version cũ.
- ❌ Merge mà chưa có CHANGELOG entry. Convention §9 bắt buộc.
- ❌ Code feature vào structure legacy "rồi refactor sau". Phải refactor `core/+markets/` trước (Wave 0).
- ❌ `if market == "vn"` trong `core/`. Adapter pattern only (theo ADR-0001).
- ❌ `core/` import từ `markets/`. Strict invariant.
- ❌ Mở >2 branch song song khi solo. Context switch quá nặng.

---

## 7. Triệu chứng quy trình hỏng — khi nào revise

| Triệu chứng | Cause khả nghi | Action |
|---|---|---|
| Codex review tìm bug mà unit test phải catch | Test plan Step 2 yếu | Strengthen testing-strategy invocation |
| Spec gap discovered giữa code | Spec chưa lock | Round in-session spec review trước Step 4 |
| PR review queue > 2 ngày | Solo dev mà mở quá nhiều branch | Giảm parallel slot xuống 1 |
| Bug fix loop > 3 round | Spec ambiguous hoặc code lệch spec | Revisit spec, có thể cần ADR mới |
| CHANGELOG sót entry | Step 9 bị skip | Add pre-merge check trong PR template |
| `core/` accidentally import `markets/` | Adapter boundary bị vi phạm | Add lint rule (import-linter) trong Wave 0 |

---

## 8. Cross-reference

- **Doc conventions:** §3 follow `docs/operations/` placement, §9 CHANGELOG required, §1 kebab-case filename.
- **ADR-0001 (Monorepo):** target structure `core/ + markets/vn/ + markets/global/` áp dụng từ Wave 0.
- **F08 memory:** F02 phải call `resolve_funding_source()` trước INSERT — wire-in rule giữ ở Wave 2.
- **Feedback memory (spec versioning):** in-session iteration không bump — áp dụng ở Step 9.
- **Implementation Plan 500 users §1.3:** foundation specs (admin tools, DR, observability) viết trước Wave 0 nếu chưa có.

---

## Changelog

### v1.0.0 — 2026-05-11
- Initial draft. Workflow 10-step, 7 Wave dependency graph, anti-patterns list, skill mapping.
