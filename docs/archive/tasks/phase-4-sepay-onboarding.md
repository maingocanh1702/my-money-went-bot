# Phase 4: SePay Onboarding — Task List

> **Status:** ⬜ Not Started
> **Tuần:** 6
> **Depends on:** Phase 2 (`/start` handler), Phase 1 (webhook_tokens)

---

## Tasks

- [ ] **T4.01** Path A: SePay Quick Connect — show webhook URL, copy button
- [ ] **T4.02** Path B: SePay Wizard — 3-step guide with ✅/❓ per step
- [ ] **T4.03** SePay webhook route — `POST /hook/{token}` → `handle_sepay_webhook()` (W0.6) → category picker
- [ ] **T4.04** First tx celebration — "🎉 Setup hoàn tất!" + `user_onboard_completed` event
- [ ] **T4.05** Onboarding analytics — `user_signup_success`, `user_onboard_path_selected`, `user_onboard_completed`

## Definition of Done

- [ ] All 5 tasks ✅
- [ ] E2E: `/start` → Path A → webhook → first tx → picker → ✅
- [ ] E2E: `/start` → Path B → 3 steps → first tx → ✅
- [ ] `pytest` ≥ 255 tests
