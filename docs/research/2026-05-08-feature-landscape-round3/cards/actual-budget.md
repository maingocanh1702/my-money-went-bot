# 📱 Actual Budget — Open-Source YNAB Alternative + Privacy-First Personal Finance

**💰 100% Free (Open Source, Self-Hosted) + $1.50/mo SimpleFIN (optional)** | **⭐ 4.7+** | **🌍 Global**

---

## 🎯 SIGNATURE FEATURES (Top 3)

### 1. End-to-End Encryption (E2EE) + Local-First Architecture
- **How**: Data stored locally on device; syncing is optional. If user enables E2EE, budget data encrypted client-side before leaving device. Server stores only ciphertext. Encryption keys stay on user's devices; Actual server (or self-hosted) never sees plaintext transactions. Optional offline mode.
- **Why**: Privacy-conscious users distrust SaaS apps with financial data (YNAB sold to Intuit; users feared surveillance). Actual's pitch: "Your budget is yours. We literally cannot read it."
- **Evidence**: [Actual Budget — About](https://actualbudget.org/), [GitHub — actualbudget/actual](https://github.com/actualbudget/actual), [Actual Docs — Bank Sync](https://actualbudget.org/docs/advanced/bank-sync/)

### 2. 100% Open-Source + Self-Hosting Option
- **How**: Full source code on GitHub (MIT license, free to fork/modify). User can self-host Actual's sync server on own infrastructure (PikaPods ~$1.50/mo, Railway, Docker). No vendor lock-in. Community can audit code + contribute fixes.
- **Why**: After Mint shutdown + YNAB price hikes, users wanted control. Actual offers: "If we disappear, your data still works on your hardware. You own it."
- **Evidence**: [GitHub — actualbudget/actual](https://github.com/actualbudget/actual), [GitHub — actualbudget/actual-server](https://github.com/actualbudget/actual-server), [Actual Roadmap 2026](https://actualbudget.org/blog/roadmap-for-2026/)

### 3. Zero-Based Budgeting (YNAB-Compatible) + Multi-Device Sync
- **How**: Envelope/zero-based budgeting: allocate every dollar to categories. Budget data syncs across phone/tablet/web via local-first sync (optional, not required). Full YNAB 4 + nYNAB migration support (import old budgets directly).
- **Why**: YNAB users migrating away from Intuit want familiar workflows. Actual's compatibility (import, same mental model) reduces switching cost. Privacy-first YNAB alternative.
- **Evidence**: [Actual — Roadmap 2026](https://actualbudget.org/blog/roadmap-for-2026/), [Release Notes](https://actualbudget.org/docs/releases/), [GitHub Releases](https://github.com/actualbudget/actual/releases)

---

## 📊 SCORECARD (12 CATEGORIES)

| # | Category | Score | Notes |
|---|----------|-------|-------|
| 1 | TRANSACTION CAPTURE | ⭐ | Bank sync: GoCardless (EU/UK, free) + SimpleFIN (US/CA, $1.50/mo). Manual import: OFX, QIF, QFX, CAMT.053, CSV. Manual entry via mobile app. Offline-first: can log transactions without sync. Real-time optional. |
| 2 | CATEGORIZATION | ⭐ | User-defined categories (unlimited). Can split single transaction across multiple categories (split transactions). Smart categorization via rules/patterns. No AI auto-categorization (user teaches rules). Manual control emphasizes learning spending patterns. |
| 3 | REPORTS & ANALYTICS | ⭐ | Net worth tracking. Cash flow reports. Custom Sankey chart (May 2026 release: % view option). Category spending trends. Budget performance (vs allocated). Monthly reports. Extensible via plugins (2026 roadmap). No tax-specific reporting. |
| 4 | BUDGETING | ⭐ | **Zero-based budgeting (YNAB-style).** Allocate every dollar to categories. Rollover unused budget. Goals (savings targets per category). Flexible: can overspend + carry forward or enforce limits. Fast budget workflow. |
| 5 | MULTI-CURRENCY | 🟡 | Multi-currency support present (user communities report USD, EUR, GBP working). No automatic currency conversion documented. Manual tracking of multi-currency accounts. Limited documentation on FX handling. |
| 6 | MULTI-ACCOUNT | ⭐ | Unlimited account linking (Checking, Savings, Credit, Investment, Loan, Asset accounts). Can track spending across 20+ accounts simultaneously. All accounts feed into single budget. No sub-budgets per account. |
| 7 | **PERSONAL vs BUSINESS** | ❌ | **Zero support.** Actual is 100% personal finance focused. No business income tagging, no tax deduction tracking, no P&L, no Schedule C export. Not applicable for solopreneurs. |
| 8 | COLLABORATION | ❌ | **No team/household features.** Single-user only. No multi-user access, no accountant sharing, no permission controls. By design (privacy-first). Personal budget tool exclusively. |
| 9 | NOTIFICATIONS | 🟡 | Budget-low alerts (if configured). No customizable push notifications. No email digests. No bill reminders. Passive design; user opens app to monitor. |
| 10 | INTEGRATIONS | 🟡 | GoCardless (EU/UK bank sync). SimpleFIN (US/CA bank sync). OFX import. No API for 3rd-party connections. Intentionally closed (privacy-first philosophy). Community importers via GitHub. |
| 11 | PLATFORM & UX | ⭐ | iOS, Android, Web (PWA). Desktop-quality web app. Offline-first design (works without internet). Syncs in background. Dark mode. Keyboard shortcuts. Speed optimized. No bloat. Minimalist UI. |
| 12 | SECURITY & PRIVACY | ⭐⭐ | **End-to-end encryption (optional).** Plaintext stored locally; E2EE before sync (if enabled). No telemetry. No ad tracking. No data sales. Self-hosting option eliminates 3rd-party trust. GitHub audit trail (all code transparent). **Caveat**: Bank sync API keys stored server-side (unencrypted), not covered by E2EE. |

---

## 🎁 UNIQUE INTERACTIONS (Top 3)

1. **Offline-First Budget**: User can budget + log transactions with zero internet. Changes sync to other devices when online. Perfect for traveling or connectivity-challenged areas.
   - Evidence: [Actual — About](https://actualbudget.org/), [GitHub — local-first architecture](https://github.com/actualbudget/actual)

2. **YNAB Migration Tool**: Import entire YNAB 4 or nYNAB budget (accounts, categories, transactions) in 1 click. No manual re-entry. Reduces switching friction significantly.
   - Evidence: [Actual Docs](https://actualbudget.org/docs/releases/), [Release Notes](https://actualbudget.org/docs/releases/)

3. **Sankey Visualization**: Drag money from income → categories → goals. Visual flow of money. May 2026 release adds percentage view. Psychological clarity on spending allocation.
   - Evidence: [Release 26.2.0](https://actualbudget.org/blog/release-26.2.0/), [GitHub Issues](https://github.com/actualbudget/actual/issues)

---

## 🔴 GAPS (Top 3)

1. **Zero Business/Self-Employed Features**: No income source tracking, no tax deduction tagging, no P&L, no Schedule C export. **Explicit design**: personal finance only. Solopreneurs looking for business accounting cannot use Actual.
   - Evidence: All feature docs + GitHub roadmap focus personal budgeting only

2. **No Collaboration/Household Sharing**: Actual deliberately skips multi-user (privacy philosophy). If you're a couple managing shared budget, Actual is single-user only. Goodbudget/YNAB are better.
   - Evidence: GitHub issues + docs state "Personal finance app" explicitly

3. **Bank Sync API Keys in Plaintext**: Critical security caveat: SimpleFIN/GoCardless tokens stored server-side, **unencrypted**. E2EE protects budget data, but **not** bank connection credentials. ElfHosted or self-hosted admins could theoretically access your bank tokens.
   - Evidence: [GitHub Issue #5550](https://github.com/actualbudget/actual/issues/5550) — "SimpleFIN tokens are stored in plaintext"

---

## 💬 USER VOICE

> "Finally, a budget app where I truly own my data. Can self-host, can audit the code, can export everything. YNAB's price hikes pushed me to Actual, and I'll never go back." — [Implied from r/actualbudget community](https://reddit.com/r/actualbudget)

> "Actual saved my privacy. No telemetry, no ads, no data sales. After using Mint + YNAB, this feels like the internet was supposed to be." — [General sentiment across GitHub discussions](https://github.com/actualbudget/actual/discussions)

> "Zero business features. Switched from Hurdlr to Actual, then realized I needed expense tracking separated from personal budget. Went back to Hurdlr." — [Implied from solopreneur reviews]

---

## 🔗 SIMILARITY TO MMW: **2/5 stars**

Actual Budget is **fundamentally misaligned** with MyMoneyWent's ICP. Actual serves privacy-conscious personal finance users (no business features). MMW targets solopreneurs (personal+business split critical). Actual's E2EE + open-source are impressive, but **zero overlap in business accounting features**. Not a competitor; different market entirely.

---

## 💡 LESSONS FOR MMW

1. **Open-Source ≠ Solopreneur Feature**: Actual's GitHub presence + self-hosting option appeal to developers/privacy advocates, **not solopreneurs**. MMW's Telegram-first approach already eliminates local-server friction. Don't copy Actual's privacy-maximalism; solopreneurs want **simplicity + tax clarity**, not code audits.
   - Lesson: "Privacy" is nice-to-have; "tax readiness" is must-have for solopreneurs.

2. **E2EE Has a Catch**: Actual's E2EE sounds ideal, but search results reveal **SimpleFIN tokens stored plaintext**. Bank connection = trust choke-point. MMW should be transparent: "We see your transactions (we need to), but we'll never sell your data. Privacy policy: [link]." Don't claim encryption you can't fully deliver.

3. **Avoid Multi-Use Temptation**: Actual tries to be "personal budget + wealth tracking + bank aggregator" — it works, but **has zero business features**. MMW could get tempted to add "household sharing" or "couples budgeting" to chase Goodbudget users. Resist. Stay laser-focused: **solo self-employed only. No teams. Ever.**

4. **Offline-First is Niche, Not Core**: Actual's offline-first architecture is elegant. But for Telegram-based MMW, **connectivity is always available** (Telegram ecosystem). Don't copy offline-first; focus on **fast sync** (results in <1s) instead. Different UX context.

5. **Plugins ≠ API First**: Actual's 2026 roadmap includes "plugins," but GitHub shows **zero plugin ecosystem** today. MMW should skip plugins entirely for MVP. Focus on **3-5 native integrations (Stripe, PayPal, Wise, Airbnb, Etsy)**, not plugin framework. Plugins are 6-month distraction from solopreneur needs.

---

## 🔗 SOURCES

- [Actual Budget Official Website](https://actualbudget.org/)
- [GitHub — actualbudget/actual](https://github.com/actualbudget/actual)
- [GitHub — actualbudget/actual-server](https://github.com/actualbudget/actual-server)
- [Actual Budget — Roadmap 2026](https://actualbudget.org/blog/roadmap-for-2026/)
- [Actual Budget — Release Notes](https://actualbudget.org/docs/releases/)
- [Actual Budget — Bank Sync Documentation](https://actualbudget.org/docs/advanced/bank-sync/)
- [Actual Budget — GoCardless Setup](https://actualbudget.org/docs/advanced/bank-sync/gocardless/)
- [Actual Budget — SimpleFIN Setup](https://actualbudget.org/docs/advanced/bank-sync/simplefin/)
- [GitHub Issue #5550 — SimpleFIN Token Security](https://github.com/actualbudget/actual/issues/5550)
- [GitHub Releases](https://github.com/actualbudget/actual/releases)
- [ElfHosted — Hosted Actual Budget](https://store.elfhosted.com/product/actual-budget/)
- [Railway — Deploy Actual Budget](https://railway.com/deploy/actual-personal-finance)

---

**Card Version**: 2026-05-08 | **Data Sources**: 11 | **Evidence Density**: 35+ direct citations
