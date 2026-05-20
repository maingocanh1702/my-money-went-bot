# MVP Build Queue — Pre-Build Verification Snapshot

> **Snapshot date:** 2026-05-14
> **Source:** `docs/implementation-tracker.md` v1.2.4, `docs/mymoneywent-roadmap.md`, `docs/operations/feature-lockdown-decisions.md`, `docs/features/`, `docs/features/BE/`, `docs/implementation-plans/`
> **Purpose:** Single-glance verification trước khi tạo Linear issues + kick autopilot batch. Kết hợp inventory, dependency graph, readiness audit, drift findings.
> **NOTE:** Đây là snapshot tại thời điểm verify. Tracker (`implementation-tracker.md`) vẫn là source-of-truth living doc — rebuild dashboard sau mỗi PR merge.

---

## 0. TL;DR

- **Total MVP PRs:** 36 (Phase 1-6, không tính Phase 5b deferred + Phase W deferred). Phase 2 added `manual-transaction-entry` 2026-05-15.
- **Merged:** 6 (W0.7, W0.8, W0.9, W0.10, settings, onboarding-start)
- **Remaining MVP:** 30 PRs
- **Deferred:** 3 parsers (parser-acb, parser-sacombank, parser-bidv → Phase 5b demand-gated) + Phase W web dashboard
- **Drift findings:** 4 (chi tiết §5) — 1 mechanical (pricing/family spec status pending lock), 3 cosmetic (roadmap stale %, F11 split nomenclature, W0.x naming)
- **Linear MCP:** ❌ chưa available trong MCP registry — output markdown để copy-paste thủ công

---

## 1. Build order (critical path + parallel slots)

Theo `docs/implementation-plans/phase-2-handlers.md` "Parallel slots (max 2 active)" + dependency chain trace:

```mermaid
graph LR
  subgraph "Phase 1 wrap (parallel infra)"
    W11[W1.1 Docker Compose]
    W12[W1.2 Discord adapter]
    W13[W1.3 Phase 1 smoke]
    W12 --> W13
    W11 --> W13
  end

  subgraph "Phase 2 critical path (slot 1)"
    onboardingStart[onboarding-start ✅] --> fundingSources[funding-sources]
    fundingSources --> txCapture[transaction-capture]
    txCapture --> manualEntry[manual-transaction-entry]
    fundingSources --> manualEntry
    txCapture --> catMgmt[category-management]
    catMgmt --> categorization[categorization]
    categorization --> reports[reports]
  end

  subgraph "Phase 2 parallel (slot 2)"
    settings[settings ✅]
    i18n[i18n-locale-switcher]
    adminAuth[admin-auth]
    onboardingStart -.unblocks.-> i18n
    settings -.unblocks.-> i18n
  end

  subgraph "Phase 3"
    txCapture --> pricingTiers[pricing-tiers]
  end

  subgraph "Phase 4 (sepay onboarding)"
    onboardingStart --> sepayPaths[sepay-onboarding-paths]
    sepayPaths --> firstTx[first-tx-celebration]
  end

  subgraph "Phase 5 (email parsing)"
    onboardingStart --> emailFwd[email-forwarding-onboarding]
    onboardingStart --> W51[W5.1 Postmark inbound]
    W51 --> parserTcb[parser-techcombank]
    W51 --> parserCake[parser-cake-vpbank]
    W51 --> parserMb[parser-mbbank]
    parserTcb --> dedup[cross-source-dedup]
    W51 --> dedup
  end

  subgraph "Phase 6 (polish + deploy)"
    fundingSources --> scheduledJobs[scheduled-jobs]
    txCapture --> scheduledJobs
    pricingTiers --> paymentVietqr[payment-vietqr]
    paymentVietqr --> paymentEmailBackup[payment-email-backup]
    paymentEmailBackup --> paymentRecurring[payment-recurring]
    adminAuth --> adminCmds[admin-commands]
    adminCmds --> W61[W6.1 Sentry alerts]
    W12 --> messengerChannel[messenger-channel]
    paymentRecurring --> W62[W6.2 Railway deploy]
    scheduledJobs --> W62
    adminCmds --> W62
    W62 --> W63[W6.3 Backup B2]
    W63 --> W64[W6.4 DR restore test]
  end
```

**Recommended ordering (anh kick autopilot theo thứ tự này):**

| # | PR | Phase | Wave | Parallel với | Lý do |
|:-:|----|:-----:|:----:|--------------|-------|
| 1 | **funding-sources** | 2 | Wave 2 | i18n-locale-switcher hoặc admin-auth | Critical path; transaction-capture blocked-by; lockdown + autopilot prompt sẵn |
| 2 | **i18n-locale-switcher** | 2 | Wave 1 | funding-sources | Slot 2 filler; cần onboarding-start + settings (✅ done); polish EN cho 2 features đã ship |
| 3 | **transaction-capture** | 2 | Wave 2 | admin-auth hoặc W1.2 | Critical path; cần funding-sources resolver; flip xfail W0.7 contract pin |
| 4 | **admin-auth** | 2 | Wave 1 | transaction-capture | Slot 2; auth framework chỉ, commands defer admin-commands |
| 5 | **category-management** | 2 | Wave 3 | W1.1 hoặc W1.2 | Critical path; required-by categorization; CRUD categories |
| 6 | **categorization** | 2 | Wave 3 | W1.2 hoặc sepay-onboarding-paths | Critical path; cần category-management |
| 7 | **reports** | 2 | Wave 4 | sepay-onboarding-paths | Pure read; không block ai trong Phase 2 |
| 8 | **W1.1** | 1 | wrap | parallel anywhere | Docker compose dev/prod; standalone infra |
| 9 | **W1.2** | 1 | wrap | parallel anywhere | Discord adapter; required-by messenger-channel |
| 10 | **W1.3** | 1 | wrap | sau W1.1+W1.2 | Phase 1 integration smoke E2E |
| 11 | **pricing-tiers** | 3 | Wave 5 | W5.1 | Pricing tiers + trial gating; required-by payment-vietqr |
| 12 | **sepay-onboarding-paths** | 4 | Wave 1+ | reports hoặc pricing-tiers | Path A+B SePay onboarding; cần onboarding-start (✅) |
| 13 | **first-tx-celebration** | 4 | Wave 1+ | sau sepay-onboarding-paths | First-tx celebration |
| 14 | **W5.1** | 5 | Wave 2+ | pricing-tiers | Postmark inbound + dispatch; required-by parsers |
| 15 | **email-forwarding-onboarding** | 5 | Wave 1+ | sau W5.1 | Path C email forwarding guides |
| 16 | **parser-techcombank** | 5 | Wave 2+ | parser-cake-vpbank hoặc parser-mbbank | Parser MVP #1; shell exists |
| 17 | **parser-cake-vpbank** | 5 | Wave 2+ | parser-techcombank | Parser MVP #2 |
| 18 | **parser-mbbank** | 5 | Wave 2+ | parser-techcombank | Parser MVP #3 |
| 19 | **cross-source-dedup** | 5 | Wave 2+ | sau ≥1 parser ship | Cross-source dedup SePay+Email |
| 20 | **manual-transaction-entry** | 2 | Wave 2+ | sau transaction-capture+funding-sources | Channel 3 manual entry; 13 decisions locked 2026-05-15; bot `/add` + webapp form |
| 21 | **scheduled-jobs** | 6 | Wave 4 | admin-commands | Scheduled jobs; cần transaction-capture+funding-sources |
| 22 | **payment-vietqr** | 6 | Wave 5 | scheduled-jobs | Payment VietQR + SePay match |
| 23 | **payment-email-backup** | 6 | Wave 5 | sau payment-vietqr | Email backup payment detect |
| 24 | **payment-recurring** | 6 | Wave 5 | sau payment-email-backup | Manual review + recurring billing |
| 25 | **admin-commands** | 6 | Wave 1+ | scheduled-jobs hoặc messenger-channel | Admin commands; cần admin-auth |
| 26 | **W6.1** | 6 | n/a | admin-commands hoặc messenger-channel | Sentry alerts (7 critical) |
| 27 | **messenger-channel** | 6 | Wave 6 | scheduled-jobs hoặc W6.1 | Messenger adapter (flag-OFF dark deploy) |
| 28 | **W6.2** | 6 | n/a | sau payment-recurring+scheduled-jobs+admin-commands | Railway deploy + custom domain |
| 29 | **W6.3** | 6 | n/a | sau W6.2 | Backup automation B2 + pg_dump |
| 30 | **W6.4** | 6 | n/a | sau W6.3 | DR runbook validation (test restore) |

**Deferred (không tạo Linear issue ngay):**

| PR | Phase | Unlock criteria |
|----|:-----:|-----------------|
| parser-acb | 5b | ≥3 beta requests OR ≥5 ACB-primary signups/wk |
| parser-sacombank | 5b | Same criteria |
| parser-bidv | 5b | Same criteria |
| Web Dashboard | W | ≥30% user request OR ≥10 Pro ask OR support burden signal OR conversion signal |

---

## 2. Per-feature readiness matrix

| PR | FE spec | BE tech spec | Lockdown | Autopilot prompt | Worktree | Test plan |
|----|:-------:|:------------:|:--------:|:----------------:|:--------:|:---------:|
| W1.1 | n/a (infra) | n/a | phase-1-foundation §W1.1 | gen khi kick | gen khi kick | 2 tests (smoke) |
| W1.2 | feature-discord-channel | feature-discord-channel-tech | phase-1 §W1.2 | gen khi kick | gen khi kick | 8 tests (contract reuse) |
| W1.3 | n/a | n/a | phase-1 §W1.3 | gen khi kick | gen khi kick | 4 tests (E2E) |
| funding-sources | feature-funding-sources v1.0.0 | feature-funding-sources-tech | feature-lockdown-decisions §2 ✅ | **`funding-sources-autopilot.md` ✅ ready** | `~/Projects/MyMoneyWent-F08` (prunable, cần repair) | 18 tests planned |
| transaction-capture | feature-transaction-capture v1.1.0 | feature-transaction-capture-tech | phase-2-handlers §transaction-capture | gen khi kick | gen khi kick | 25 tests planned |
| category-management | feature-category-management v1.0.0 | feature-category-management-tech | phase-2 §category-management | gen khi kick | gen khi kick | 14 tests |
| categorization | feature-categorization v1.0.0 | feature-categorization-tech | phase-2 §categorization | gen khi kick | gen khi kick | 16 tests |
| reports | feature-reports v1.0.0 | feature-reports-tech | phase-2 §reports | gen khi kick | gen khi kick | 12 tests |
| admin-auth | feature-admin-tools v1.0.0 | feature-admin-tools-tech | phase-2 §admin-auth | gen khi kick | gen khi kick | TBD |
| i18n-locale-switcher | feature-i18n v1.0.0 | feature-i18n-tech | feature-lockdown-decisions §3.1 | gen khi kick | gen khi kick | TBD |
| pricing-tiers | feature-pricing-tiers v1.1.0 ⚠️ | feature-pricing-tiers-tech | phase-3-pricing | gen khi kick | gen khi kick | TBD |
| sepay-onboarding-paths/first-tx-celebration/email-forwarding-onboarding | feature-onboarding v1.1.0 | feature-onboarding-tech | phase-4-sepay-onboarding | gen khi kick | gen khi kick | TBD |
| W5.1 + parsers | feature-transaction-capture v1.1.0 | feature-transaction-capture-tech | phase-5-email-parsing | gen khi kick | gen khi kick | Golden fixture ≥10 sample/parser |
| cross-source-dedup | feature-transaction-capture v1.1.0 | feature-transaction-capture-tech | phase-5 | gen khi kick | gen khi kick | TBD |
| scheduled-jobs | feature-scheduled-jobs v1.0.0 | feature-scheduled-jobs-tech | phase-6-polish-deploy | gen khi kick | gen khi kick | TBD |
| payment-vietqr/payment-email-backup/payment-recurring | feature-payment v1.0.0 | feature-payment-tech | implementation-plan-payment-vietqr-email | gen khi kick | gen khi kick | TBD |
| admin-commands | feature-admin-tools v1.0.0 | feature-admin-tools-tech | phase-6 | gen khi kick | gen khi kick | TBD |
| W6.1 / W6.2 / W6.3 / W6.4 | n/a | observability-plan / runbooks/disaster-recovery | phase-6 | gen khi kick | gen khi kick | n/a |
| messenger-channel | feature-messenger-channel v1.0.0 | feature-messenger-channel-tech | implementation-plan-messenger | gen khi kick | gen khi kick | TBD |

⚠️ = scope locked nhưng spec status doc còn "pending lock" — xem §5 drift #1.

**Per tracker §0 convention:** Autopilot prompts gen fresh ngay trước khi kick wave (KHÔNG sinh upfront để tránh stale). Worktree tạo theo nhu cầu khi có 2+ session parallel (per `feedback_concurrency_one_session`).

---

## 3. Cross-feature gates (mọi PR phải pass)

Theo tracker §2:

| Gate | Mô tả | Enforced by |
|------|-------|-------------|
| 🔒T | Tenant isolation test (2 user → query verify không thấy nhau) | Per-PR mandatory |
| 🔒I | Import-linter contract (`core/` ↛ `markets/`, `vn` ↛ `global_`, parsers ↛ `core.db`/`core.messenger`) | `.importlinter` CI |
| 🔒M | Migration up+down OK | Migration test |
| 🔒X | Codex cross-model review pass | Workflow §1.2 |

5-category test plan (Workflow §2):

1. Positive (happy path)
2. Edge (boundary, NULL, empty, max)
3. Error (DB down, invalid input)
4. Isolation (multi-tenant)
5. Contract (FK, invariant, xfail pins)

---

## 4. Acceptance criteria template (cho mỗi Linear issue)

Mỗi issue copy block dưới + fill cụ thể từ feature spec + lockdown:

```markdown
## Acceptance criteria

- [ ] FE spec §<X> use cases all implemented
- [ ] BE tech spec §<Y> contracts pass test
- [ ] Lockdown decisions §<Z> không violate
- [ ] 5-category test plan: <N tests> green (positive/edge/error/isolation/contract)
- [ ] Gates: 🔒T 🔒I 🔒M (nếu có DDL) 🔒X
- [ ] Codex review 2× consecutive clean (P1) hoặc 1× clean (P2 mature)
- [ ] Tracker row updated (manual post-merge)
- [ ] Dashboard rebuild auto-triggered

## Negative scope (do NOT touch)

<copy từ autopilot prompt khi gen — section "Negative scope">

## Required reading (autopilot prompt sẽ enforce)

1. <feature spec>
2. <BE tech spec>
3. <lockdown doc>
4. <implementation plan section>
```

---

## 5. Drift findings (verify pass kết quả)

### Drift #1 — Pricing/Family spec status `pending lock` ⚠️ (mechanical)

- `feature-pricing-tiers.md` status = "Draft (Family addendum 2026-05-11 — pending lock)"
- `feature-family-plan.md` status = "Draft (pending lock)"
- Memory `project_family_plan_decisions` ghi rõ **decisions LOCKED 2026-05-11** (Pro 99k, Family 169k, Business 299k, 2P+4C, grandfather 6 tháng).
- Risk register row "pricing-tiers addendum doc merge: 🟡 Decisions locked, doc merge pending" xác nhận drift.
- **Action:** Trước khi kick pricing-tiers autopilot, merge addendum vào pricing-tiers spec + bump status → "Locked v1.2.0". Nếu không, pricing-tiers prompt sẽ đọc spec stale.

### Drift #2 — Roadmap Phase 1 % stale (cosmetic)

- `mymoneywent-roadmap.md` ghi Phase 1 = "🟡 In Progress ~75%"
- `implementation-tracker.md` §5 ghi Phase 1 = "57% (4/7)" sau W0.10 merge (v1.2.4)
- **Action:** Optional — sync roadmap % với tracker hoặc remove % khỏi roadmap (tracker là SoT).

### Drift #3 — F11 split nomenclature (cosmetic, intentional)

- Tracker dùng admin-auth (Phase 2 auth framework only) + admin-commands (Phase 6 commands)
- Spec `feature-admin-tools.md` covers F11 unified
- **Action:** Không cần fix — split là intentional shipping strategy. Linear issues nên tag rõ "admin-auth" / "admin-commands" để matches tracker IDs.

### Drift #4 — W0.x prefix dùng cho Phase 1 PRs (cosmetic)

- Tracker §0 convention: `W<phase>.<seq>` → Phase 1 should be W1.x
- Nhưng W0.7-W0.10 lại được dùng cho Phase 1 follow-ups (4 PRs đã merged)
- Lý do thực tế: chúng inherit Wave 0 numbering vì là follow-up của Wave 0 work
- **Action:** Không cần fix — rename gây confusion với historical refs. Linear issues giữ nguyên ID hiện tại trong tracker.

---

## 6. Linear export plan (workaround thủ công)

**Linear MCP status:** ❌ Không tìm thấy connector trong MCP registry tại 2026-05-14.

**Workaround — copy-paste flow:**

1. Tạo Linear team `MyMoneyWent` (nếu chưa có)
2. Tạo 6 epics: Phase 1, Phase 2, Phase 3, Phase 4, Phase 5, Phase 6
3. Mỗi PR trong §1 = 1 issue dưới epic tương ứng:
   - Title: `<PR ID> — <feature name>` (vd `funding-sources — Funding sources resolver + handlers`)
   - Priority: theo Risk tier (P1 = High, P2 = Medium per `project_autopilot_risk_tier_policy`)
   - Order/sort: dùng số thứ tự trong cột "#" của bảng §1 làm sort key
   - Labels: `phase-N`, `wave-N`, `risk-tier-Px`, `merge-policy-<auto|manual>`, `autopilot-<mature|pilot>`
   - Description: copy template §4 + paste relevant FE/BE spec links + acceptance criteria
   - Dependencies (Linear "blocked by"): theo dependency graph §1
4. Mark 6 issues đã merged thành **Done** (W0.7, W0.8, W0.9, W0.10, settings, onboarding-start)
5. Mark 3 deferred parsers + Web Dashboard thành **Backlog** với label `deferred-phase-5b` / `deferred-phase-w`

**Suggested Linear states mapping:**

| Tracker status | Linear state |
|----------------|--------------|
| ⬜ not started | Backlog |
| 🟡 in progress | In Progress |
| 🟠 in review | In Review |
| 🟢 ready to merge | Ready |
| ✅ merged | Done |
| ❌ blocked | Blocked (custom state) |
| ⏸️ deferred | Backlog + label |

---

## 7. Pre-kick checklist (per feature trước khi run autopilot)

```markdown
- [ ] FE spec status = Locked (hoặc cập nhật trước nếu drift)
- [ ] BE tech spec exists trong docs/features/BE/
- [ ] Lockdown decisions written (hoặc lock trước nếu chưa)
- [ ] Files-touched estimate (avoid scope creep)
- [ ] 5-category test plan written (concrete count per category)
- [ ] Risk tier classified (P0/P1/P2) → merge policy chosen
- [ ] Worktree created: `git worktree add ~/Projects/MyMoneyWent-<PR-ID> -b feat/<branch-name>`
- [ ] Pre-flight clean: `ls .git/worktrees/<PR-ID>/index.lock` empty
- [ ] STRICT: chỉ 1 Claude Code session per .git/ (per `feedback_concurrency_one_session`)
- [ ] Autopilot prompt gen fresh + paste vào fresh session
```

---

## Changelog

| Version | Ngày | Thay đổi |
|---------|------|----------|
| v1.0.0 | 2026-05-14 | Initial pre-build verification snapshot. 35 PRs MVP cataloged, 4 drift findings, dependency graph + 29-PR ordered build queue, Linear export workaround (no MCP connector). |
