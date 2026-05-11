# Phase 4: SePay Onboarding — 2 PRs

> **Version:** v1.0.0
> **Ngày tạo:** 2026-05-12
> **Trạng thái:** Active
> **Owner:** Founder (dev)
> **Mục đích:** Complete F01 onboarding paths A (quick connect) + B (wizard) + first-tx celebration. Path C (email) defer to Phase 5.
> **Tham chiếu:**
> - [Implementation Tracker](../implementation-tracker.md)
> - [Feature Spec F01](../features/feature-onboarding.md)
> - [ADR-0002 Onboarding UI](../adr/0002-onboarding-ui-strategy.md)
> - [Roadmap §Phase 4](../mymoneywent-roadmap.md)

---

## Overview

| PR | Scope | Tests | Est. days |
|----|-------|:-----:|:---------:|
| F01b | Path A (Quick connect) + Path B (Wizard) | 18 | 2.0 |
| F01c | First-tx celebration flow | 8 | 1.0 |
| **Total** | | **26** | **~3 days** |

**Dependencies:**
- Phase 1 (Discord adapter) — Path A/B should work on both channels
- Phase 2 (F-onboarding `/start`) — Phase 4 extends `/start` flow
- Phase 2 (F08 funding sources) — first detected bank → auto-create funding source

---

## F01b — Path A + Path B

### Scope

**Path A (Quick connect, ~30 sec):**
- After `/start`: bot offers 3 options inline (Path A / B / C)
- User picks A → bot generates webhook URL: `https://api.tienvenoidau.com/hook/{user_token}`
- Display URL + 1-screen instruction: "Paste this into SePay dashboard → Save"
- Wait state: detect first webhook hit → trigger F01c celebration

**Path B (SePay wizard, ~3 min):**
- User picks B → bot enters 3-step guided flow:
  - Step 1: "Tạo account SePay tại sepay.vn → enter email khi xong"
  - Step 2: "Connect VCB/TCB/MB → enter bank name khi xong"
  - Step 3: "Trong SePay dashboard, set webhook URL: [generated]"
- Each step has ✅/❓ buttons; ❓ shows expanded help
- Track state in `bot_state` table (per user, ephemeral, JSONB)
- Resume capable: user can `/setup` to continue mid-flow

### Files touched

```
+ core/handlers/onboarding.py
+ core/services/onboarding_state.py
+ core/services/webhook_url.py  (generation helper)
+ tests/integration/test_onboarding_paths.py
+ tests/unit/test_onboarding_state_machine.py
M core/handlers/start.py  (extend /start to show path picker)
M migrations/versions/0001_initial_schema.py  ← NO, use existing bot_state table
```

### Test plan (18)

**Path picker (3):**
1. After `/start`, inline keyboard shows A/B/C buttons
2. Callback parses correctly
3. Locale: VI/EN both render

**Path A (4):**
4. User picks A → webhook URL generated, displayed
5. URL token = hashed (SHA256) stored, raw URL one-time display
6. Re-show URL via `/setup` → re-derive from stored hash (NO — can't reverse hash; alternative: store encrypted)
7. URL contains user_token → resolves to correct user_id

**Path B state machine (6):**
8. Picks B → state=`b_step1`, message shown
9. ✅ on step1 → state=`b_step2`
10. ❓ on step2 → expanded help shown, state unchanged
11. Skip/back: callback `back` returns to previous step
12. `/setup` mid-flow → resume from saved state
13. Complete step3 → state=`b_done`, webhook URL provided (same as Path A)

**Edge (3):**
14. User starts Path A then switches to Path B → state replaced
15. Concurrent webhook arrival mid-onboarding → tx queued, F01c triggers after onboard complete
16. Timeout: state >7 days inactive → cleaned by F09 sweep (placeholder, F09 implements)

**Isolation (2):**
17. User A onboarding state never visible to User B
18. Webhook for User A token ONLY creates User A tx

### Acceptance criteria

- New user can complete Path A in <2 minutes (manual test with founder + 1 friend)
- Path B handles all 3 steps, ✅/❓ work
- Resume via `/setup` works
- State stored isolated per user

### Decision lockdown

- [x] **Webhook URL strategy: regenerate on demand** (locked 2026-05-12). One-time display at generation; `/setup → regenerate` invalidates old token + creates new. Preserves Gap 3 hash-only security model. UX cost: 30 sec re-paste into SePay if user loses URL.
- [x] **State storage:** `bot_state` table (already in schema), JSONB column `state_data`, key `onboarding`
- [x] **State machine:** 4 states for Path B (b_step1, b_step2, b_step3, b_done); finite, no transitions outside these
- [x] **Callback timeout:** 30 min — after that, `/setup` to resume

### Risk

- **Webhook URL leak:** If user pastes URL in public Telegram group, attacker can spam transactions. Mitigation: rate limit per token (Phase 5 W5.1 may add); manual revoke via `/setup → regenerate`
- **State drift:** If user completes setup on SePay but never confirms in bot, state stuck. Mitigation: F09 sweep + first-tx celebration auto-resolves

---

## F01c — First-tx celebration

### Scope

After first inbound tx from SePay webhook OR Email parser:
- Detect: `transactions` count was 0 → now 1 for this user
- Send celebration message: "🎉 Setup hoàn tất! Giao dịch đầu tiên đã được ghi nhận."
- Show tx detail + category suggestion (auto via F03 categorizer)
- CTA: "/manage để xem categories | /status để xem báo cáo"

### Files touched

```
+ core/services/first_tx_handler.py
+ tests/integration/test_first_tx_flow.py
M core/handlers/transaction.py  (hook: after insert, check first-tx, dispatch celebration)
```

### Test plan (8)

1. User has 0 tx → webhook arrives → tx inserted → celebration message sent
2. User has 1 tx → 2nd tx arrives → NO celebration (already celebrated)
3. Celebration includes tx amount + bank + suggested category
4. If F03 categorizer confidence <0.7 → celebration shows "❓ Chọn category" inline
5. If user in Path B state=`b_step1`/2 → still trigger celebration + jump state to `b_done`
6. Edge: 2 webhooks arrive simultaneously → only 1 celebration (race-safe via DB unique constraint or advisory lock)
7. Isolation: User A first-tx never triggers message to User B
8. i18n: VI/EN celebration both work

### Acceptance criteria

- First-tx celebration triggers exactly once per user
- Concurrent inserts handled
- Integrates with F03 category suggestion
- Onboarding state auto-completes on first tx

### Decision lockdown

- [ ] **Trigger detection:** Query `COUNT(*) FROM transactions WHERE user_id = $1` after insert. Cheap because of `idx_tx_user`.
- [ ] **Race condition:** Use Postgres advisory lock `pg_try_advisory_xact_lock(hashtext('first_tx:' || user_id))` before insert+celebration block
- [ ] **Path B auto-jump:** First tx during Path B step1/2 → state → `b_done`, skip remaining steps (user clearly figured it out)

---

## Phase 4 exit checklist (gate → Phase 5)

- [ ] F01b + F01c merged
- [ ] Path A demo with founder + 1 friend → <2 min completion
- [ ] Path B all 3 steps tested
- [ ] First-tx celebration verified
- [ ] F03 category suggestion integrated
- [ ] F08 auto-create funding source on first SePay tx
- [ ] Roadmap Phase 4 → 100%

---

## Webhook URL strategy (LOCKED 2026-05-12)

**Decision: Option A — Regenerate on demand.**

Background: W0.6 ships `webhook_tokens` as SHA256-hashed (Gap 3 security invariant). Re-display impossible without raw token.

**Implementation:**
- F01b generates raw token + stores SHA256 hash → displays raw ONCE in chat
- User pastes raw token URL into SePay dashboard
- If user loses URL: `/setup → regenerate` invalidates old hash, creates new token, displays raw ONCE again
- Old token rejected at webhook endpoint (no race window — atomic swap in `webhook_tokens` table)

**Why this over Option B (encrypted-at-rest):** Preserves Gap 3 hash-only security model. No KMS / key rotation complexity. Re-paste 30 sec is acceptable UX cost given recovery is rare.

**Why this over Option C (no regenerate shortcut):** Same security, but `/setup → regenerate` gives users a recovery path without contacting support.

---

## Changelog

| Version | Ngày | Thay đổi |
|---------|------|----------|
| v1.0.0 | 2026-05-12 | Initial plan. 2 PRs (F01b paths, F01c celebration). ~3 days est. Open question: webhook URL re-display strategy (recommend regenerate on demand). |
