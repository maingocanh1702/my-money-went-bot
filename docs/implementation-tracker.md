# Implementation Tracker — MyMoneyWent

> **Version:** v1.0.0
> **Ngày tạo:** 2026-05-12
> **Trạng thái:** Active
> **Owner:** Founder (dev)
> **Mục đích:** Master status board cho mọi PR còn lại từ Phase 1 → Phase 6 (MVP). Tie roadmap timeline ↔ dev-workflow waves ↔ feature specs. Cập nhật status mỗi khi PR merge.
> **Tham chiếu:**
> - [Roadmap](mymoneywent-roadmap.md) — phase timeline + overall progress
> - [Development Workflow](operations/development-workflow.md) — 10-step per-feature process + Wave dependency graph
> - [Implementation Plans](implementation-plans/) — per-phase detail docs

---

## 0. How to use this tracker

**3 levels of detail:**

1. **This tracker** — single page status board. Mỗi PR = 1 row với (Phase, Wave, Feature, Status, Branch, Gates).
2. **Per-phase plan** (`implementation-plans/phase-N-*.md`) — detail mỗi PR: scope, test plan, file diff estimate, acceptance criteria, decision lockdown checklist.
3. **Execution prompt** (`autopilot/prompts/<id>.md`) — autopilot prompt generate fresh **ngay trước** khi chạy wave (Mode 3 chained). KHÔNG sinh upfront để tránh stale.

**PR ID convention:**
- Infra wave: `W<phase>.<seq>` — vd `W1.1` (Phase 1 wave 1), `W6.2` (Phase 6 wave 2)
- Business feature: kebab-case feature name — vd `transaction-capture`, `funding-sources` (match feature spec filename). Convention switched 2026-05-15 from legacy F-codes (F01/F02/F08…) — see Changelog v1.3.0.

**Status legend:**
- `⬜` not started
- `🟡` in progress (branch open, code WIP)
- `🟠` code done, in review (Codex)
- `🟢` review pass, ready to merge
- `✅` merged to main
- `❌` blocked (see Notes)
- `⏸️` deferred post-MVP (unlock criteria in Notes)

**Gate flags** (mandatory before merge):
- `🔒T` Tenant isolation test pass
- `🔒I` Import-linter contract pass
- `🔒M` Migration up+down OK
- `🔒X` Codex review pass

---

## 1. Status board — Phase 1 → 6

### Phase 1: Foundation (Wave 0 done — 3 PRs remaining + W0 follow-ups)

| PR | Wave | Feature | Status | Branch | Gates | Notes |
|----|------|---------|:------:|--------|:-----:|-------|
| W0.7 | Wave 0 follow-up | Public `request_id` helpers + F02 xfail contract pin | ✅ | `chore/W0.7-tenant-context-public-api` | 🔒T 🔒X | Merged. `core/tenant_context.set_request_id/reset_request_id` + middleware refactor + xfail strict pin on `funding_source_id` contract. |
| W0.8 | Wave 0 follow-up | Webhook `display_suffix VARCHAR(8)` migration (G3 option b) | ✅ | `feat/webhook-display-suffix-migration` | 🔒T 🔒X | Merged (7105e86). Schema P1 — additive nullable column on `webhook_tokens`. Migration 0002 + `mint_token` populates `raw[-6:]` + `get_display_suffix` read helper. F07 unblocked. See `docs/autopilot/prompts/webhook-display-suffix-migration-autopilot.md`. |
| W0.9 | Wave 0 follow-up | Dashboard realtime — auto-rebuild + git-state detect + reconcile | ✅ | `feat/dashboard-realtime` | 🔒X | Merged via 4 commits on main (`9e561d3` feat, `a5ea4c4` CI, `3f3cdf8` pre-commit, `1edc7a5` ruff/mypy fix). `scripts/build-dashboard.py` gained `detect_git_state` + `reconcile_status` + drift report. Pre-commit hook auto-rebuilds dashboard.{html,md} khi tracker.md or build-dashboard.py staged. GH Action `.github/workflows/dashboard.yml` rebuilds + commits back on push to main/feat/**/infra/**/chore/**/fix/** + hourly schedule + workflow_dispatch. 21 unit tests pass (3× scope của prompt gốc — `tests/unit/test_build_dashboard.py`). Remote branch `origin/feat/dashboard-realtime` còn dấu vết (0 commits ahead) — có thể prune. Prompt: `docs/autopilot/prompts/dashboard-realtime-autopilot.md`. |
| W0.10 | Wave 0 follow-up | Dashboard v3 rich UI + click-through + Chart.js | ✅ | `feat/dashboard-v3-rich-v2` | 🔒X | **Merged `8f29af2` (2026-05-13).** Autopilot rebase pilot — cherry-pick `4e59b64` (Chart.js MVP burndown + filter toolbar + search input + click-through PR/issue + animations) onto fresh main; skipped `c5721be` redundant (FastAPI route đã ship qua `b6b711b`). Manual conflict resolve trong `scripts/build-dashboard.py` (page-head + closing scripts blocks) preserved 3 layers side-by-side: W0.9 detect_git_state + Phase 3 HTML_LIVE_JS + Chart.js UI. Codex 1× clean (P2 pilot). +311/-10 LOC. Stale branch `feat/dashboard-v3-rich` deprecated, deleted post-merge. Tooling debt: 6 pre-existing scripts/ mypy errors deferred to separate cleanup PR (not introduced by W0.10). |
| W1.1 | Wave 0 extras | Docker Compose dev + prod | ⬜ | `infra/W1.1-docker-compose` | 🔒X | Postgres + bot service compose, env wiring |
| W1.2 | Wave 6 (early) | Discord adapter (`core/messenger/discord.py`) | ⬜ | `feat/W1.2-discord-adapter` | 🔒I 🔒X | Contract test reuse từ W0.4; impl `BaseSender` ABC |
| W1.3 | n/a | Phase 1 integration smoke | ⬜ | `chore/W1.3-phase1-smoke` | 🔒T 🔒X | E2E test: 2 channels (TG+Discord) → 2 users → tenant isolated |

**Phase 1 exit criteria:** Docker compose lên 1 lệnh, Discord adapter + Telegram cùng pass contract test, smoke E2E xanh.

### Phase 2: Handlers Refactor (5 features + 1 chore)

| PR | Wave | Feature | Status | Branch | Gates | Notes |
|----|------|---------|:------:|--------|:-----:|-------|
| onboarding-start | Wave 1 | `/start` + user create + trial assign | ✅ | `feat/F01-onboarding-start` | 🔒T 🔒M 🔒X | **Merged `9f07c57` (2026-05-13)** (previously F01). 8-round Codex saga (P1 manual_only). Multi-channel `/start` (TG wired, Discord handler-ready). Idempotent user create + mint_token (sepay) + 3 default categories + 14d trial. 17 new tests (12 integration + 5 unit), baseline 376→393. Defensive guards added during rounds 01-06: `/start@bot` suffix strip, deep-link payload, missing from.id reject (tenant isolation), non-private chat drop (DM routability), chat_id self-heal, mint_token graceful degrade, `_safe_send` wrapper for missing adapter. 5 founder-review decisions: (1) inbound_email domain `in.mymoneywent.com` codebase invariant wins vs lockdown's `tienvenoidau.com` drift; (2) .importlinter exemption for core.handlers.start→mint_token bridge; (3) welcome_back no `{name}` placeholder (cross-channel display_name unreliable); (4) DB-down test via capsys not caplog (structlog→stdout); (5) /start non-private dropped. Path A/B/C still Phase 4. Unblocks funding-sources (FK chain) + transaction-capture (user_id INSERT). |
| funding-sources | Wave 2 | Funding sources resolver + handlers | ⬜ | `feat/funding-sources` | 🔒T 🔒I 🔒X | DDL landed W0.2 → only service + handler logic |
| transaction-capture | Wave 2 | Transaction capture EXPANDED (inherit W0.6 legacy cutover) | ⬜ | `feat/transaction-capture` | 🔒T 🔒I 🔒M 🔒X | Strangler: rewrite legacy handlers/, delete sheets.py, refactor main.py, run migrate_sheets.py. **MUST remove `xfail` marker on `test_persisted_tx_has_resolved_funding_source_id`** (W0.7 contract pin). Decide legacy formatter drift (revert vs `style:` commit) per phase-2 lockdown. |
| manual-transaction-entry | Wave 2+ | Manual transaction entry — Channel 3 of transaction-capture | ⬜ | `feat/manual-transaction-entry` | 🔒T 🔒X | Depends on transaction-capture + funding-sources merged. 13 decisions locked 2026-05-15 (see memory). Bot `/add` hybrid parser+form + Webapp form. Backdate 90d, edit window 30d, unlimited all tiers. |
| category-management | Wave 3 | Category management (`/manage`) | ⬜ | `feat/category-management` | 🔒T 🔒X | CRUD + parent/sub tree |
| categorization | Wave 3 | Categorization auto-rules + manual | ⬜ | `feat/categorization` | 🔒T 🔒X | After category-management (needs categories) |
| reports | Wave 4 | Reports `/status`, `/today`, `/weekly` | ⬜ | `feat/reports` | 🔒T 🔒X | Pure read; no writes |
| settings | Wave 1 | Settings `/settings` | ✅ | `feat/F07-settings` | 🔒T 🔒X | Merged `f232b63` (2026-05-13) (previously F07). 6-session pilot validated v0.2.0→v0.2.3 orchestrator end-to-end. Locale + TZ + daily recap toggle, regen webhook, `get_overview` pure-read refactor, `ensure_inbound_email` helper, migration 0003 backfill_inbound_email. 376 tests pass. Pilot also surfaced 9 cumulative orchestrator hardening items, 3 shipped (v0.2.1+v0.2.2+v0.2.3), 6 deferred to v0.2.4 backlog. See memory `project_f07_pilot_saga.md`. |
| admin-auth | Wave 1 | Admin auth framework only (commands defer Phase 6) | ⬜ | `feat/admin-auth` | 🔒T 🔒X | `ADMIN_IDS` env + decorator; actual `/admin_*` commands ship Phase 6 |
| i18n-locale-switcher | Wave 1 | VI/EN locale switcher | ⬜ | `feat/i18n-locale-switcher` | 🔒X | **Unblocked 2026-05-13** (post-onboarding-start + settings). Stub `i18n/vi.py` + `i18n/en.py` đã land W0.4. settings + onboarding-start ship với keys ở vi.py + en.py literal (parity test enforced). i18n-locale-switcher PR sẽ: (1) polish EN wording cho keys hiện tại từ literal placeholders, (2) add language confirm UI (FE spec feature-onboarding.md v1.2.0 §3 Language Selection), (3) expand stub → full `t(locale, key)` module với fallback rules, (4) update onboarding-start/settings handlers chuyển sang `t(user.locale, ...)`. Lockdown decision 2026-05-13 trong docs/operations/feature-lockdown-decisions.md §3.1: i18n-locale-switcher owns full EN parity. Trước đây mark ❌ là legacy status — không có blocker mechanical thực sự. |

**Phase 2 parallel rule:** Max 2 branch active. Recommend pair: `onboarding-start+settings` (independent), then `funding-sources+i18n-locale-switcher`, then `category-management→categorization` (sequential), then `reports+admin-auth`.

**Phase 2 exit criteria:** Legacy `handlers/*.py` + `sheets.py` deleted, all CRUD multi-tenant, founder data migrated, 10 features green.

### Phase 3: Pricing Logic (1 feature)

| PR | Wave | Feature | Status | Branch | Gates | Notes |
|----|------|---------|:------:|--------|:-----:|-------|
| pricing-tiers | Wave 5 | Tier limits + 14d trial + gating middleware | ⬜ | `feat/pricing-tiers` | 🔒T 🔒M 🔒X | Free 45tx/1bank/30d; auto-downgrade; max 1 upgrade prompt/week |

**Phase 3 exit criteria:** Free user hit 45 tx → blocked with upgrade CTA; trial expiry → auto-downgrade; tier checks on category-management/reports/funding-sources.

### Phase 4: SePay Onboarding (1 feature, 2 sub-PRs)

| PR | Wave | Feature | Status | Branch | Gates | Notes |
|----|------|---------|:------:|--------|:-----:|-------|
| sepay-onboarding-paths | Wave 1+ | Path A (Quick connect) + Path B (Wizard) | ⬜ | `feat/sepay-onboarding-paths` | 🔒T 🔒X | Webhook URL gen, SePay 3-step wizard, ✅/❓ progress markers |
| first-tx-celebration | Wave 1+ | First-tx celebration flow | ⬜ | `feat/first-tx-celebration` | 🔒T 🔒X | Detect first inbound tx → "🎉 Setup hoàn tất!" + suggest category |

**Phase 4 exit criteria:** New user can complete Path A in <2 min; Path B handles SePay edge cases (wrong webhook, account mismatch).

### Phase 5: Email Parsing (1 wave + 3 MVP parsers + 1 dedup + 1 onboarding; 3 parsers deferred to Phase 5b)

| PR | Wave | Feature | Status | Branch | Gates | Notes |
|----|------|---------|:------:|--------|:-----:|-------|
| W5.1 | Wave 2+ | Postmark inbound + `/inbound/{token}` route | ⬜ | `infra/W5.1-postmark-inbound` | 🔒T 🔒I 🔒X | Webhook auth, parser dispatch, unparsed fallback notify |
| email-forwarding-onboarding | Wave 1+ | Path C onboarding (email forwarding guides) | ⬜ | `feat/email-forwarding-onboarding` | 🔒T 🔒X | Gmail + Outlook instruction screens |
| parser-techcombank | Wave 2+ | Parser: Techcombank full extraction | ⬜ | `feat/parser-techcombank` | 🔒I 🔒X | Shell exists W0.6; complete HTML parsing |
| parser-cake-vpbank | Wave 2+ | Parser: Cake (VPBank) | ⬜ | `feat/parser-cake-vpbank` | 🔒I 🔒X | Shell exists W0.6 |
| parser-mbbank | Wave 2+ | Parser: MB Bank | ⬜ | `feat/parser-mbbank` | 🔒I 🔒X | Shell exists W0.6 |
| parser-acb | Phase 5b | Parser: ACB (deferred to Phase 5b) | ⏸️ | `feat/parser-acb` | 🔒I 🔒X | Shell exists W0.6. Unlock: ≥3 beta requests OR ≥5 ACB-primary signups/wk |
| parser-sacombank | Phase 5b | Parser: Sacombank (deferred to Phase 5b) | ⏸️ | `feat/parser-sacombank` | 🔒I 🔒X | Shell exists W0.6. Same unlock criteria |
| parser-bidv | Phase 5b | Parser: BIDV (deferred to Phase 5b) | ⏸️ | `feat/parser-bidv` | 🔒I 🔒X | Shell exists W0.6. Same unlock criteria |
| cross-source-dedup | Wave 2+ | Cross-source dedup (SePay + Email) | ⬜ | `feat/cross-source-dedup` | 🔒T 🔒X | Fuzzy: same amount + type within 3 min window |

**Phase 5 MVP scope (LOCKED 2026-05-12):** Techcombank + Cake (VPBank) + MB Bank (3 banks). parser-acb/sacombank/bidv → Phase 5b post-soft-launch, demand-gated. Mỗi parser PR có golden fixture (≥10 sample emails).

**Phase 5 exit criteria:** ≥85% parser accuracy on Techcombank/Cake/MB samples; unparsed emails surface to user; SePay+Email cross-dedup prevents double-count.

### Phase 6: Polish + Deploy (waves)

| PR | Wave | Feature | Status | Branch | Gates | Notes |
|----|------|---------|:------:|--------|:-----:|-------|
| scheduled-jobs | Wave 4 | Scheduled jobs (APScheduler, TZ jitter ±5min) | ⬜ | `feat/scheduled-jobs` | 🔒T 🔒X | Daily recap, monthly digest, trial expiry sweep |
| payment-vietqr | Wave 5 | Payment VietQR + SePay auto-detect (4-layer fuzzy) | ⬜ | `feat/payment-vietqr` | 🔒T 🔒X | Per `implementation-plan-payment-vietqr-email.md` |
| payment-email-backup | Wave 5 | Email backup detect (Techcombank email path) | ⬜ | `feat/payment-email-backup` | 🔒T 🔒X | Postmark inbound for Techcombank secondary |
| payment-recurring | Wave 5 | Manual review fallback + recurring billing | ⬜ | `feat/payment-recurring` | 🔒T 🔒X | `/admin_resolve`, monthly 3d reminder + 7d grace |
| admin-commands | Wave 1+ | Admin commands (`/admin_stats`, `/admin_cost`, `/admin_user`, `/admin_resolve`) | ⬜ | `feat/admin-commands` | 🔒T 🔒X | Auth framework already in admin-auth |
| W6.1 | n/a | Sentry alerts — 7 critical (per observability-plan.md) | ⬜ | `infra/W6.1-sentry-alerts` | 🔒X | Tenant leak, parser failure, payment match miss, cost spike, etc. |
| messenger-channel | Wave 6 | Messenger adapter (feature-flagged `ENABLE_MESSENGER_CHANNEL=false`) | ⬜ | `feat/messenger-channel` | 🔒I 🔒X | Code ships dark; flip ON post Meta App Review |
| W6.2 | n/a | Railway deploy + custom domain (tienvenoidau.com) | ⬜ | `infra/W6.2-railway-deploy` | 🔒X | DNS, SSL, prod env vars |
| W6.3 | n/a | Backup automation (B2 + pg_dump daily, SSE-B2) | ⬜ | `infra/W6.3-backup-b2` | 🔒X | Daily cron, retention 30d |
| W6.4 | n/a | DR runbook full validation (test restore) | ⬜ | `chore/W6.4-dr-restore-test` | — | Per `runbooks/disaster-recovery.md` §11 |

**Phase 6 parallel rule:** scheduled-jobs/admin-commands/W6.1 chạy được parallel (independent). payment-vietqr→payment-email-backup→payment-recurring sequential. messenger-channel parallel với scheduled-jobs. W6.2 sau khi payment-recurring xong (cần payment flow để demo). W6.3+W6.4 sau W6.2.

**Phase 6 exit criteria:** Production deployed at tienvenoidau.com, 7 alerts wired, backup tested restore, all admin commands work, payment auto-detect demo with founder's TCB account.

### Phase W: Web Dashboard (deferred — trigger-based post-launch)

> **Status:** ⏸️ Deferred. Trigger criteria and scope: [webapp-resource-assessment.md](research/webapp-resource-assessment.md)
>
> Implementation planning starts only when trigger criteria met (≥30% user request, ≥10 Pro ask, support burden, conversion signal). When triggered:
> - Promote/update `features/feature-web-dashboard.md` to implementation-ready spec
> - Create `features/BE/feature-web-dashboard-tech.md` (BE spec)
> - Create `implementation-plans/phase-w-web-dashboard.md`

| PR | Wave | Feature | Status | Branch | Gates | Notes |
|----|------|---------|:------:|--------|:-----:|-------|
| (to be created when Phase W enters implementation planning) | — | — | ⏸️ | — | — | Estimate: 19–29 days |

**Architecture prep (do during Phase 2):** Ensure `transactions_query.py` + `reports_query.py` are reusable service layers — bot formats text, future API returns JSON.

---

## 2. Cross-phase invariants (always-on gates)

Mọi PR phải pass trước merge:

| Invariant | Check method | Enforced by |
|-----------|--------------|-------------|
| Tenant isolation | Integration test: 2 user, query verify không thấy nhau | Per-PR test (mandatory) |
| Import boundary | `core/` ↛ `markets/`; `vn` ↛ `global_`; parsers ↛ `core.db`/`core.messenger` | `.importlinter` CI |
| Spec-first | FE spec + BE tech doc đọc xong, gap closed trước Step 4 | Workflow §2.1 |
| In-session no version bump | Iterations trong cùng phiên KHÔNG bump spec version | Workflow §2 Step 9 + memory |
| Codex cross-model review | Claude code → Codex review (logic+perf+security) | Workflow §1.2 |
| Atomic commits in branch | Cho phép squash on merge nhưng branch atomic | Workflow §2 Step 6 |

---

## 3. Risk burn-down (link → roadmap §7 Risk Register)

Sync khi đóng/mới risk:

| Risk | Affects PRs | Current state | Owner |
|------|-------------|---------------|-------|
| Email parser slip | parser-techcombank, parser-cake-vpbank, parser-mbbank | 🟢 Mitigated (shells exist, plugin framework ready) | Founder |
| Legacy handler migration drag | transaction-capture | 🟡 Active — strangler fig, each handler atomic PR |  Founder |
| Railway cost > $50/mo | W6.2 onwards | 🟢 Monitor only (cost low pre-launch) | Founder |
| pricing-tiers addendum doc merge | (Family Plan blocker) | 🟡 Decisions locked, doc merge pending | Founder |
| Meta App Review pages_messaging | messenger-channel flip ON | 🔲 Pending external | Meta |
| Hộ kinh doanh registration | payment-recurring | 🔲 Pending — start 1-2 tuần before Phase 6 | Founder |

---

## 4. Decision lockdown protocol (per wave)

Memory rule: **lock decisions before autopilot.** Trước khi generate execution prompt cho 1 wave, lockdown checklist:

1. **Spec gaps closed** — Đọc FE+BE tech spec, no ambiguous contract. Nếu gap → update spec trước.
2. **Test plan locked** — 5 categories (positive, edge, error, isolation, contract). Skill: `engineering:testing-strategy`.
3. **Migration risk reviewed** — Nếu DDL change: up+down both tested, no destructive ops without backup.
4. **Files-touched estimate** — Liệt kê file diff trước (avoid surprise scope creep mid-PR).
5. **Acceptance criteria written** — Concrete, testable, không "implementation works".

Nếu 1 trong 5 fail → KHÔNG generate autopilot prompt. Manual mode (founder hand-holds Claude) acceptable.

---

## 5. Progress summary (auto-updated)

> Cập nhật table này mỗi lần PR merge. Source of truth cho roadmap progress %.

| Phase | Total PRs | Merged | In progress | Blocked | Deferred | % |
|-------|:---------:|:------:|:-----------:|:-------:|:--------:|:-:|
| 1 | 7 | 4 (W0.7, W0.8, W0.9, W0.10) | 0 | 0 | 0 | 57% |
| 2 | 10 | 2 (settings, onboarding-start) | 0 | 0 | 0 | 20% |
| 3 | 1 | 0 | 0 | 0 | 0 | 0% |
| 4 | 2 | 0 | 0 | 0 | 0 | 0% |
| 5 (MVP) | 6 | 0 | 0 | 0 | 0 | 0% |
| 5b (post-launch) | — | — | — | — | 3 (parser-acb, parser-sacombank, parser-bidv) | n/a |
| 6 | 10 | 0 | 0 | 0 | 0 | 0% |
| **MVP total** | **36** | **6** | **0** | **0** | **0** | **17%** |

(Wave 0 = 6 PRs đã merged, không count vào MVP remaining. W0.7 merged 2026-05-12. W0.8 merged 2026-05-12 (7105e86). W0.9 dashboard-realtime merged 2026-05-13 via 4 commits on main. settings (F07) merged 2026-05-13 (f232b63) — 6-session pilot. onboarding-start (F01) merged 2026-05-13 (9f07c57) — 8-round Codex saga, 17 new tests, baseline 376→393. W0.10 dashboard-v3-rich rebased + merged 2026-05-13 (8f29af2) — Codex 1× clean P2 pilot, Chart.js UI + filter + search + click-through layered on top of W0.9 + Phase 3. Phase 5b = 3 parsers deferred, unlock per demand signal. Phase 2 total 9→10 với manual-transaction-entry row added 2026-05-15 (Channel 3 of transaction-capture, 13 decisions locked).)

---

## Changelog

| Version | Ngày | Thay đổi |
|---------|------|----------|
| v1.0.0 | 2026-05-12 | Initial tracker. 34 PRs MVP remaining across Phase 1-6. Hybrid granularity (wave for infra/deploy, feature for biz logic). Per-phase detail docs linked. Phase 7-11 deferred. |
| v1.0.1 | 2026-05-12 | Added W0.7 (post-W0 follow-up): public `request_id` helpers + F02 xfail contract pin. F02 row + Phase 1 totals updated. See `wave0-retrospective.md` § Post-W0 follow-ups. |
| v1.0.2 | 2026-05-12 | Added W0.8 (Wave 0 follow-up): webhook `display_suffix VARCHAR(8)` migration per G3 option (b). F07 marked Blocked-on-W0.8. Phase 1 total 4→5; MVP total 32→33; Blocked column reflects F07+W0.8 chain. |
| v1.1.0 | 2026-05-13 | W0.7 + W0.8 → ✅ merged. F07 unblocked (❌→⬜). Phase 1: 40% (2/5 merged). MVP: 6% (2/33). All `.autopilot/` refs → `docs/autopilot/` (tracked). |
| v1.1.1 | 2026-05-13 | Autopilot v0.2.2 (tooling hardening) shipped to main (`533e9fd`). F07 Phase B resume attempted on `feat/F07-settings`@`17f039b` post-merge; halted Codex R2 [P2] CONCURRENCY_FINDING false-positive (substring "lock" in "block"). F07 row ⬜→❌ pending founder Path A/B/C. v0.2.3 backlog: word-boundary match for non-SEVERE keyword categories. |
| v1.2.0 | 2026-05-13 | **F07 ✅ merged (`f232b63`).** 6-session pilot complete. Autopilot v0.2.3 (`9a00be6`) shipped to unblock F07 (keyword word-boundary fix mirrored from v0.2.2 R4 to CONCURRENCY/ARCH/SOFT). F07 row ❌→✅. Phase 2: 11% (1/9). MVP: 9% (3/33). F02 unblocked next. Pilot saga lessons in memory `project_f07_pilot_saga.md`. |
| v1.2.1 | 2026-05-13 | **Dashboard tooling backfill.** Added W0.9 (dashboard-realtime ✅ merged via 4 commits — `9e561d3` feat, `a5ea4c4` CI, `3f3cdf8` pre-commit, `1edc7a5` ruff/mypy) + W0.10 (dashboard-v3-rich 🟡 stale, 2 unmerged commits trên base trước F07 → cần rebase). Phase 1: 5→7 PRs, 43% (3/7). MVP: 33→35, 11% (4/35). Tracker rows backfill, không có code change. |
| v1.2.2 | 2026-05-13 | **F01 ✅ merged (`9f07c57`).** 8-round Codex autopilot saga (P1 manual_only, vượt MAX_ROUNDS=5 nhưng mỗi round fresh finding, không RECURRING). 17 tests new (12 integration + 5 unit), baseline 376→393. Multi-channel `/start` minimal (Path A/B/C still Phase 4). Codex catches valuable: P1 tenant isolation (missing from.id), P1 non-private chat drop, P1 unregistered adapter (Discord), P2 Telegram routing edge cases. F01 row ⬜→✅. Phase 2: 11%→22% (2/9 merged). MVP: 11%→14% (5/35). Unblocks F08 + F02. Saga lessons appended to memory `project_f07_pilot_saga.md`. |
| v1.2.3 | 2026-05-13 | **F-i18n status fix + dashboard accuracy cleanup.** F-i18n ❌→⬜ (unblocked post-F01+F07; trước đây mark blocked là legacy status, không có mechanical blocker). Dashboard "1 BLOCKED" KPI giờ → 0. F-i18n PR scope clarified: polish EN literal placeholders + language confirm UI + expand `t()` stub + migrate F01/F07 handlers. Phase 2 counts unchanged (9 PRs, 2 merged, 22%). |
| v1.2.4 | 2026-05-13 | **W0.10 ✅ merged (`8f29af2`)** via autopilot rebase pilot. Cherry-pick `4e59b64` Chart.js MVP burndown + filter toolbar + search input + click-through PR/issue navigation + animations onto fresh main. Skipped `c5721be` redundant. Manual conflict resolve trong `scripts/build-dashboard.py` preserved 3-layer dashboard pipeline (W0.9 + Phase 3 + Chart.js UI side-by-side). Codex 1× clean (P2 pilot). +311/-10 LOC. Phase 1: 43%→**57%** (4/7 merged). MVP: 14%→**17%** (6/35). In flight: 1→0. Old stale branch `feat/dashboard-v3-rich` deleted. Pre-existing scripts/ mypy errors (6) deferred to separate cleanup PR — not introduced by W0.10. |
| v1.3.0 | 2026-05-15 | **Feature naming convention shift** — PR ID column từ F-codes (F02, F03, F08…) sang kebab-case feature names (transaction-capture, categorization, funding-sources…). onboarding-start (F01) + settings (F07) rows preserve "(previously F01/F07)" trong Notes column cho traceability. Autopilot prompt files renamed: F01-onboarding-autopilot.md → onboarding-start-autopilot.md, F08-funding-sources-autopilot.md → funding-sources-autopilot.md. Lockdown doc renamed: F01-F08-lockdown.md → feature-lockdown-decisions.md. Added new row `manual-transaction-entry` Phase 2 (Channel 3 of transaction-capture, 13 decisions locked 2026-05-15). Phase 2 totals 9→10 (22%→20%), MVP totals 35→36 (17%→17%). Branches not physically renamed — founder per-branch decision. Git history immutable. |
