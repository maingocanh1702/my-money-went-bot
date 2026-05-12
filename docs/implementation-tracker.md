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
3. **Execution prompt** (`operations/execution-prompt-<id>.md`) — autopilot prompt generate fresh **ngay trước** khi chạy wave (Mode 3 chained). KHÔNG sinh upfront để tránh stale.

**PR ID convention:**
- Infra wave: `W<phase>.<seq>` — vd `W1.1` (Phase 1 wave 1), `W6.2` (Phase 6 wave 2)
- Business feature: `F##` — vd `F03`, `F08` (match feature spec numbering)

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
| W0.7 | Wave 0 follow-up | Public `request_id` helpers + F02 xfail contract pin | 🟢 | `chore/W0.7-tenant-context-public-api` | 🔒T 🔒X | Code done 2026-05-12 (uncommitted in working tree). `core/tenant_context.set_request_id/reset_request_id` + middleware refactor + xfail strict pin on `funding_source_id` contract. Branch + commit per `wave0-retrospective.md` post-W0 section. |
| W0.8 | Wave 0 follow-up | Webhook `display_suffix VARCHAR(8)` migration (G3 option b) | ⬜ | `feat/webhook-display-suffix-migration` | 🔒T 🔒X | Schema P1 — additive nullable column on `webhook_tokens`. Migration 0002 + `mint_token` populates `raw[-6:]` + `get_display_suffix` read helper. Auth path (`resolve_token`) untouched. **Blocks F07 pilot.** Requires inline Codex review with 2× clean rounds per plan §6.5. See `.autopilot/prompts/webhook-display-suffix-migration-autopilot.md`. |
| W1.1 | Wave 0 extras | Docker Compose dev + prod | ⬜ | `infra/W1.1-docker-compose` | 🔒X | Postgres + bot service compose, env wiring |
| W1.2 | Wave 6 (early) | Discord adapter (`core/messenger/discord.py`) | ⬜ | `feat/W1.2-discord-adapter` | 🔒I 🔒X | Contract test reuse từ W0.4; impl `BaseSender` ABC |
| W1.3 | n/a | Phase 1 integration smoke | ⬜ | `chore/W1.3-phase1-smoke` | 🔒T 🔒X | E2E test: 2 channels (TG+Discord) → 2 users → tenant isolated |

**Phase 1 exit criteria:** Docker compose lên 1 lệnh, Discord adapter + Telegram cùng pass contract test, smoke E2E xanh.

### Phase 2: Handlers Refactor (5 features + 1 chore)

| PR | Wave | Feature | Status | Branch | Gates | Notes |
|----|------|---------|:------:|--------|:-----:|-------|
| F-onboarding | Wave 1 | F01 — `/start` + user create + trial assign | ⬜ | `feat/F01-onboarding-start` | 🔒T 🔒M 🔒X | Path A/B/C onboarding logic in Phase 4; chỉ ship `/start` here |
| F08 | Wave 2 | F08 — Funding sources resolver + handlers | ⬜ | `feat/F08-funding-sources` | 🔒T 🔒I 🔒X | DDL landed W0.2 → only service + handler logic |
| F02 | Wave 2 | F02 — Transaction capture EXPANDED (inherit W0.6 legacy cutover) | ⬜ | `feat/F02-tx-capture-cutover` | 🔒T 🔒I 🔒M 🔒X | Strangler: rewrite legacy handlers/, delete sheets.py, refactor main.py, run migrate_sheets.py. **MUST remove `xfail` marker on `test_persisted_tx_has_resolved_funding_source_id`** (W0.7 contract pin). Decide legacy formatter drift (revert vs `style:` commit) per phase-2 lockdown. |
| F04 | Wave 3 | F04 — Category management (`/manage`) | ⬜ | `feat/F04-category-mgmt` | 🔒T 🔒X | CRUD + parent/sub tree |
| F03 | Wave 3 | F03 — Categorization auto-rules + manual | ⬜ | `feat/F03-categorization` | 🔒T 🔒X | After F04 (needs categories) |
| F05 | Wave 4 | F05 — Reports `/status`, `/today`, `/weekly` | ⬜ | `feat/F05-reports` | 🔒T 🔒X | Pure read; no writes |
| F07 | Wave 1 | F07 — Settings `/settings` | ⬜ | `feat/F07-settings` | 🔒T 🔒X | Locale + TZ + daily recap toggle. **Blocked on W0.8** (`display_suffix` migration) — G3 closed to option (b), suffix display rule depends on column landing first. |
| F11a | Wave 1 | F11 — Admin auth framework only (commands defer Phase 6) | ⬜ | `feat/F11a-admin-auth` | 🔒T 🔒X | `ADMIN_IDS` env + decorator; actual `/admin_*` commands ship Phase 6 |
| F-i18n | Wave 1 | F-i18n — VI/EN locale switcher | ❌ | `feat/F-i18n` | 🔒X | Stub đã land W0.4; expand to all user-facing strings |

**Phase 2 parallel rule:** Max 2 branch active. Recommend pair: `F01+F07` (independent), then `F08+F-i18n`, then `F04→F03` (sequential), then `F05+F11a`.

**Phase 2 exit criteria:** Legacy `handlers/*.py` + `sheets.py` deleted, all CRUD multi-tenant, founder data migrated, 9 features green.

### Phase 3: Pricing Logic (1 feature)

| PR | Wave | Feature | Status | Branch | Gates | Notes |
|----|------|---------|:------:|--------|:-----:|-------|
| F06 | Wave 5 | F06 — Tier limits + 14d trial + gating middleware | ⬜ | `feat/F06-pricing-tiers` | 🔒T 🔒M 🔒X | Free 45tx/1bank/30d; auto-downgrade; max 1 upgrade prompt/week |

**Phase 3 exit criteria:** Free user hit 45 tx → blocked with upgrade CTA; trial expiry → auto-downgrade; tier checks on F04/F05/F08.

### Phase 4: SePay Onboarding (1 feature, 2 sub-PRs)

| PR | Wave | Feature | Status | Branch | Gates | Notes |
|----|------|---------|:------:|--------|:-----:|-------|
| F01b | Wave 1+ | Path A (Quick connect) + Path B (Wizard) | ⬜ | `feat/F01b-sepay-paths` | 🔒T 🔒X | Webhook URL gen, SePay 3-step wizard, ✅/❓ progress markers |
| F01c | Wave 1+ | First-tx celebration flow | ⬜ | `feat/F01c-first-tx-flow` | 🔒T 🔒X | Detect first inbound tx → "🎉 Setup hoàn tất!" + suggest category |

**Phase 4 exit criteria:** New user can complete Path A in <2 min; Path B handles SePay edge cases (wrong webhook, account mismatch).

### Phase 5: Email Parsing (1 wave + 3 MVP parsers + 1 dedup + 1 onboarding; 3 parsers deferred to Phase 5b)

| PR | Wave | Feature | Status | Branch | Gates | Notes |
|----|------|---------|:------:|--------|:-----:|-------|
| W5.1 | Wave 2+ | Postmark inbound + `/inbound/{token}` route | ⬜ | `infra/W5.1-postmark-inbound` | 🔒T 🔒I 🔒X | Webhook auth, parser dispatch, unparsed fallback notify |
| F01d | Wave 1+ | Path C onboarding (email forwarding guides) | ⬜ | `feat/F01d-email-forwarding` | 🔒T 🔒X | Gmail + Outlook instruction screens |
| P-TCB | Wave 2+ | Parser: Techcombank full extraction | ⬜ | `feat/parser-tcb` | 🔒I 🔒X | Shell exists W0.6; complete HTML parsing |
| P-Cake | Wave 2+ | Parser: Cake (VPBank) | ⬜ | `feat/parser-cake` | 🔒I 🔒X | Shell exists W0.6 |
| P-MB | Wave 2+ | Parser: MB Bank | ⬜ | `feat/parser-mb` | 🔒I 🔒X | Shell exists W0.6 |
| P-ACB | Phase 5b | Parser: ACB (deferred to Phase 5b) | ⏸️ | `feat/parser-acb` | 🔒I 🔒X | Shell exists W0.6. Unlock: ≥3 beta requests OR ≥5 ACB-primary signups/wk |
| P-STB | Phase 5b | Parser: Sacombank (deferred to Phase 5b) | ⏸️ | `feat/parser-stb` | 🔒I 🔒X | Shell exists W0.6. Same unlock criteria |
| P-BIDV | Phase 5b | Parser: BIDV (deferred to Phase 5b) | ⏸️ | `feat/parser-bidv` | 🔒I 🔒X | Shell exists W0.6. Same unlock criteria |
| F02-dedup | Wave 2+ | Cross-source dedup (SePay + Email) | ⬜ | `feat/F02-dedup` | 🔒T 🔒X | Fuzzy: same amount + type within 3 min window |

**Phase 5 MVP scope (LOCKED 2026-05-12):** TCB + Cake + MB (3 banks). P-ACB/STB/BIDV → Phase 5b post-soft-launch, demand-gated. Mỗi parser PR có golden fixture (≥10 sample emails).

**Phase 5 exit criteria:** ≥85% parser accuracy on TCB/Cake/MB samples; unparsed emails surface to user; SePay+Email cross-dedup prevents double-count.

### Phase 6: Polish + Deploy (waves)

| PR | Wave | Feature | Status | Branch | Gates | Notes |
|----|------|---------|:------:|--------|:-----:|-------|
| F09 | Wave 4 | F09 — Scheduled jobs (APScheduler, TZ jitter ±5min) | ⬜ | `feat/F09-scheduled-jobs` | 🔒T 🔒X | Daily recap, monthly digest, trial expiry sweep |
| F10a | Wave 5 | F10 — Payment VietQR + SePay auto-detect (4-layer fuzzy) | ⬜ | `feat/F10a-payment-vietqr-sepay` | 🔒T 🔒X | Per `implementation-plan-payment-vietqr-email.md` |
| F10b | Wave 5 | F10 — Email backup detect (TCB email path) | ⬜ | `feat/F10b-payment-email-backup` | 🔒T 🔒X | Postmark inbound for TCB secondary |
| F10c | Wave 5 | F10 — Manual review fallback + recurring billing | ⬜ | `feat/F10c-payment-recurring` | 🔒T 🔒X | `/admin_resolve`, monthly 3d reminder + 7d grace |
| F11b | Wave 1+ | F11 — Admin commands (`/admin_stats`, `/admin_cost`, `/admin_user`, `/admin_resolve`) | ⬜ | `feat/F11b-admin-commands` | 🔒T 🔒X | Auth framework already in F11a |
| W6.1 | n/a | Sentry alerts — 7 critical (per observability-plan.md) | ⬜ | `infra/W6.1-sentry-alerts` | 🔒X | Tenant leak, parser failure, payment match miss, cost spike, etc. |
| F13 | Wave 6 | F13 — Messenger adapter (feature-flagged `ENABLE_MESSENGER_CHANNEL=false`) | ⬜ | `feat/F13-messenger-channel` | 🔒I 🔒X | Code ships dark; flip ON post Meta App Review |
| W6.2 | n/a | Railway deploy + custom domain (tienvenoidau.com) | ⬜ | `infra/W6.2-railway-deploy` | 🔒X | DNS, SSL, prod env vars |
| W6.3 | n/a | Backup automation (B2 + pg_dump daily, SSE-B2) | ⬜ | `infra/W6.3-backup-b2` | 🔒X | Daily cron, retention 30d |
| W6.4 | n/a | DR runbook full validation (test restore) | ⬜ | `chore/W6.4-dr-restore-test` | — | Per `runbooks/disaster-recovery.md` §11 |

**Phase 6 parallel rule:** F09/F11b/W6.1 chạy được parallel (independent). F10a→F10b→F10c sequential. F13 parallel với F09. W6.2 sau khi F10c xong (cần payment flow để demo). W6.3+W6.4 sau W6.2.

**Phase 6 exit criteria:** Production deployed at tienvenoidau.com, 7 alerts wired, backup tested restore, all admin commands work, payment auto-detect demo with founder's TCB account.

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
| Email parser slip | P-TCB, P-Cake, P-MB | 🟢 Mitigated (shells exist, plugin framework ready) | Founder |
| Legacy handler migration drag | F02 | 🟡 Active — strangler fig, each handler atomic PR |  Founder |
| Railway cost > $50/mo | W6.2 onwards | 🟢 Monitor only (cost low pre-launch) | Founder |
| F06 addendum doc merge | (Family Plan blocker) | 🟡 Decisions locked, doc merge pending | Founder |
| Meta App Review pages_messaging | F13 flip ON | 🔲 Pending external | Meta |
| Hộ kinh doanh registration | F10c (recurring) | 🔲 Pending — start 1-2 tuần before Phase 6 | Founder |

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
| 1 | 5 | 0 | 1 (W0.7) | 1 (W0.8 blocks F07) | 0 | 0% |
| 2 | 9 | 0 | 0 | 1 (F07 on W0.8) | 0 | 0% |
| 3 | 1 | 0 | 0 | 0 | 0 | 0% |
| 4 | 2 | 0 | 0 | 0 | 0 | 0% |
| 5 (MVP) | 6 | 0 | 0 | 0 | 0 | 0% |
| 5b (post-launch) | — | — | — | — | 3 (P-ACB, P-STB, P-BIDV) | n/a |
| 6 | 10 | 0 | 0 | 0 | 0 | 0% |
| **MVP total** | **33** | **0** | **1** | **2** | **0** | **0%** |

(Wave 0 = 6 PRs đã merged, không count vào MVP remaining. W0.7 = post-W0 cleanup, code done 2026-05-12, awaiting commit. W0.8 = webhook `display_suffix` migration, ships before F07 pilot per G3 option b. Phase 5b = 3 parsers deferred, unlock per demand signal.)

---

## Changelog

| Version | Ngày | Thay đổi |
|---------|------|----------|
| v1.0.0 | 2026-05-12 | Initial tracker. 34 PRs MVP remaining across Phase 1-6. Hybrid granularity (wave for infra/deploy, feature for biz logic). Per-phase detail docs linked. Phase 7-11 deferred. |
| v1.0.1 | 2026-05-12 | Added W0.7 (post-W0 follow-up): public `request_id` helpers + F02 xfail contract pin. F02 row + Phase 1 totals updated. See `wave0-retrospective.md` § Post-W0 follow-ups. |
| v1.0.2 | 2026-05-12 | Added W0.8 (Wave 0 follow-up): webhook `display_suffix VARCHAR(8)` migration per G3 option (b). F07 marked Blocked-on-W0.8. Phase 1 total 4→5; MVP total 32→33; Blocked column reflects F07+W0.8 chain. See `.autopilot/prompts/webhook-display-suffix-migration-autopilot.md`. |
