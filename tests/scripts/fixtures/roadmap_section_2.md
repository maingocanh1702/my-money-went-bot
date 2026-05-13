## 2. Feature Modules

**Feature implementation: 10%** `██░░░░░░░░░░░░░░░░░░` (Foundation infra shipped, no business logic yet)

| Module | Feature | Spec | BE Tech | BE Code | Bot Code | Phase |
|--------|---------|:----:|:-------:|:-------:|:--------:|:-----:|
| F01 | 3-Path Onboarding | ✅ | ✅ | 🟡 W0 infra | ⬜ | 1,4 |
| F02 | Transaction Capture (SePay + Email) | ✅ | ✅ | 🟡 webhook_tokens + parsers shell | ⬜ | 1,5 |
| F03 | Transaction Categorization | ✅ | ✅ | ⬜ | ⬜ | 2 |
| F04 | Category Management (/manage) | ✅ | ✅ | ⬜ | ⬜ | 2 |
| F05 | Reports (/status, /today, /weekly) | ✅ | ✅ | ⬜ | ⬜ | 2 |
| F06 | Pricing, Tier Limits & Trial | ✅ | ✅ | ⬜ | ⬜ | 3 |
| F07 | Settings (/settings) | ✅ | ✅ | ⬜ | ⬜ | 2 |
| F08 | Funding Sources | ✅ | ✅ | 🟡 DDL landed W0.2 | ⬜ | 2 |
| F09 | Scheduled Jobs | ✅ | ✅ | ⬜ | ⬜ | 6 |
| F10 | Payment (Bank Transfer Auto-Detect) | ✅ | ✅ | ⬜ | ⬜ | 6 |
| F11 | Admin Tools & Audit | ✅ | ✅ | 🟡 audit_log table W0.2 | ⬜ | 6 |
| F12 | Multi-User Data Isolation | ✅ (PRD) | — | ✅ tenant_context W0.3 | — | 1 |
| F13 | Messenger Channel | ✅ | ✅ | ⬜ | ⬜ | 6 |
| F14 | Discord Channel | ✅ | ✅ | ⬜ | ⬜ | 1 |
| F15 | Personal vs Business Toggle | ✅ | ✅ | ⬜ | ⬜ | 9 |
| F16 | P&L View | ⬜ | ⬜ | ⬜ | ⬜ | 9 |
| F17 | Income Source Attribution | ⬜ | ⬜ | ⬜ | ⬜ | 9 |
| F-i18n | Internationalization | ✅ | ✅ | 🟡 stub W0.4 | — | 1 |
| F-saas | SaaS Refactor | ✅ | ✅ | 🟡 foundation W0.1-W0.6 | — | 1 |
| FAM | Family Plan | ✅ v1.2.0 | ✅ v1.1.0 | ⬜ | ⬜ | 11 |

> **Numbering note:** F08 = Funding Sources (entity model, DDL landed W0.2). F12 = Multi-User Data Isolation (tenant_context, not a standalone service). Aligned with PRD convention post W0.2.

---

## 3. Timeline
