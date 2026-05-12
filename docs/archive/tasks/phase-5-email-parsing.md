# Phase 5: Email Parsing — Task List

> **Status:** ⬜ Not Started
> **Tuần:** 7-9
> **Depends on:** Phase 1 (parser plugin framework W0.6)

---

## Tasks

- [ ] **T5.01** Postmark inbound service setup — `POST /inbound/{user_token}` endpoint
- [ ] **T5.02** Path C: Email forwarding onboarding — Gmail + Outlook step-by-step guides
- [ ] **T5.03** Parser: TCB full extraction — HTML table parsing, all fields → CanonicalTx
- [ ] **T5.04** Parser: Cake full extraction
- [ ] **T5.05** Parser: ACB full extraction
- [ ] **T5.06** Parser: STB (Sacombank) full extraction
- [ ] **T5.07** Parser: BIDV full extraction
- [ ] **T5.08** Parser: MB Bank full extraction
- [ ] **T5.09** Unparsed fallback — "Email đến nhưng không parse được, manual entry?"
- [ ] **T5.10** Cross-source dedup — SePay + Email same amount/type within 3 min = skip
- [ ] **T5.11** Stale protection — SePay >10min = skip, Email >24h = skip
- [ ] **T5.12** Email source tier limits — Free 1, Pro 3, Business unlimited
- [ ] **T5.13** Parser accuracy monitoring — log success/fail per bank, alert if <85%

## Definition of Done

- [ ] All 13 tasks ✅
- [ ] E2E: Forward bank email → parse → category picker → tx saved
- [ ] 6 parsers ≥85% accuracy (50+ email samples per bank)
- [ ] `pytest` ≥ 300 tests
