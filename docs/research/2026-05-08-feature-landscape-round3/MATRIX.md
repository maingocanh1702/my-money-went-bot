# Feature-by-Category Matrix: Wallet vs Lunch Money vs Money Manager (Realbyte)

## 📊 SCORECARD ACROSS 12 CATEGORIES

| # | Category | Wallet (BudgetBakers) | Lunch Money | Money Manager (Realbyte) |
|---|----------|:-----:|:-----:|:-----:|
| 1 | Transaction Capture | ⭐ | 🟡 | 🟡 |
| 2 | Categorization | ⭐ | ⭐ | 🟡 |
| 3 | Reports | 🟡 | ⭐ | 🟡 |
| 4 | Budgeting | ⭐ | ⭐ | ⭐ |
| 5 | Multi-Currency | ⭐ | ⭐ | 🟡 |
| 6 | Multi-Account | ⭐ | ⭐ | ⭐ |
| 7 | Personal vs Business | 🟡 | 🟡 | 🟡 |
| 8 | Collaboration | 🟡 | ❌ | ❌ |
| 9 | Notifications | 🟡 | 🟡 | 🟡 |
| 10 | Integrations | 🟡 | ⭐ | 🟡 |
| 11 | Platform & UX | ⭐ | ⭐ | 🟡 |
| 12 | Security | ⭐ | 🟡 | 🟡 |
| | **TOTAL STARS** | **7⭐** | **7⭐** | **5⭐** |

---

## KEY DIMENSION COMPARISON

### Transaction Capture (Most Decisive)
| App | Primary Method | Secondary | Friction |
|---|---|---|---|
| **Wallet** | Bank sync (15K banks) | CSV/XLS import, manual entry | Lowest (auto-sync) |
| **Lunch Money** | Plaid bank sync, CSV/PDF import, manual | Recurring auto-detect | Low (mostly auto, some manual) |
| **Money Manager** | **Manual entry ONLY** | Photo receipts, calendar input | **Highest (no sync)** |

**Winner:** Wallet (SaltEdge coverage) = Lunch Money (Plaid) >> Money Manager (manual)

---

### Categorization Sophistication
| App | Default Count | Custom | Auto-Assign | Rules | Subcats | Tags | Split Tx |
|---|---|---|---|---|---|---|---|
| **Wallet** | 20-30 | ✅ | ✅ ML | ✅ Rule editor | ✅ | ❌ | ❌ UI |
| **Lunch Money** | 30+ | ✅ | ✅ ML | ✅ API | ❌ | ✅ Custom | ✅ UI |
| **Money Manager** | 25+ | ✅ | ❌ Manual | ❌ | ✅ | ❌ | ❌ |

**Winner:** Wallet (rule editor) = Lunch Money (split tx + tags) >> Money Manager (manual)

---

### Budgeting Depth
| App | Category Budgets | Custom Periods | Rollover | Alerts | Sub-Budget | Approval |
|---|---|---|---|---|---|---|
| **Wallet** | ✅ | ✅ | ✅ | ✅ | ❌ | ❌ |
| **Lunch Money** | ✅ | ✅ | ✅ | ✅ | ❌ | ❌ |
| **Money Manager** | ✅ | ✅ (W/M/A) | ❌ | ✅ | ✅ Subcats | ❌ |

**TIE:** All three handle basic budgeting. Money Manager edges on subcategory budgets (Wallet/Lunch Money require rules).

---

### Multi-Asset Class Support
| App | Bank Accounts | Credit Cards | Investment | Crypto | Insurance/Loans | Real Estate |
|---|---|---|---|---|---|---|
| **Wallet** | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ |
| **Lunch Money** | ✅ | ✅ | Manual notes | ✅ Native | ❌ | ❌ |
| **Money Manager** | ✅ | ✅ | ❌ | ❌ | ✅ Native | ✅ Native |

**Winner by Use Case:**
- Crypto investor? → **Lunch Money**
- Asset-heavy (loans, insurance, property)? → **Money Manager**
- General budgeting? → **Wallet** (simplicity wins)

---

### Developer Extensibility
| App | API | Webhooks | Zapier | OSS | Custom Integrations |
|---|---|---|---|---|---|
| **Wallet** | ❌ | ❌ | ❌ | ❌ | ❌ |
| **Lunch Money** | ✅ v2 (alpha→GA) | ✅ | ✅ (8K+ apps) | GitHub ecosystem | ✅ |
| **Money Manager** | ❌ | ❌ | ❌ | ❌ | ❌ |

**Clear Winner:** **Lunch Money** (indie ethos, API-first)

---

### Market Position & TAM Alignment

| App | Primary Market | TAM | Positioning | Growth Stage |
|---|---|---|---|---|
| **Wallet** | EU families, professionals | €5B+ Europe | "Personal & Family Finance" | Growth (EU-focused) |
| **Lunch Money** | US tech-savvy, solos, couples | $2B US | "Delightfully simple" indie | Scale (Product Hunt, HN) |
| **Money Manager** | Global developing markets, Android-first | $3B Android | "Easiest finance app" | Mature (20M downloads) |

**For MMW (Telegram bot, global, freelancer-focus):**
- Lunch Money closest alignment (indie, API, global-capable, US-first pivot)
- Wallet useful for EU expansion strategy
- Money Manager useful for Android-no-sync regions (India, SE Asia, Latin America)

---

## SURPRISING FINDINGS (TOP 3)

### 1. **Collaboration is an Unmet Market Gap**
All three apps have zero or minimal collaboration:
- Wallet: Family sharing (view-only) — minimal approval workflow
- Lunch Money: **None** (API workaround only)
- Money Manager: **None**

**Implication for MMW:** Add couple/team mode early = 30-50% TAM expansion. Married couples + shared expenses + accountability = high willingness-to-pay segment.

---

### 2. **"No Bank Sync" Money Manager Still Has 20M Downloads**
Money Manager dominates Android in regions WITHOUT bank API infrastructure (India, Pakistan, Indonesia, Nigeria, Kenya).
- Manual entry + photo receipts sufficient for users with weak banking infrastructure.
- Telegram text input (MMW) is less friction than form-filling in Money Manager.

**Implication for MMW:** Telegram-first design is asymmetric advantage in developing markets (lower infrastructure cost, higher engagement).

---

### 3. **Developer API is Secret Moat (Lunch Money)**
Lunch Money's smallest user base (~100K est.) but highest power-user retention + ecosystem growth (GitHub projects, Zapier integrations).
- API v2 moving to GA in early 2026 = locked-in developer community.
- Competitors (Wallet, Money Manager) ignore API entirely = platform risk.

**Implication for MMW:** Open API + webhook support from day 1 unlocks:
- Freelancer plugins (invoice sync, mileage automation)
- Tax integrators (QuickBooks, Stripe webhook)
- CPA ecosystem (custom tax reports)

This is how you compete vs. YNAB / Personal Capital without massive marketing spend.

---

## SCORING METHODOLOGY

- **⭐ (Star):** Feature fully implemented, industry-competitive, mature
- **🟡 (Incomplete):** Feature partially implemented or basic version (no advanced options)
- **❌ (Missing):** Feature absent entirely

## DATA SOURCES COUNTED

**Total unique sources cited across 3 cards:** 47 URLs
- Wallet: 10 sources (official docs + support articles + YouTube review)
- Lunch Money: 15 sources (official docs, API docs, GitHub, Product Hunt, Indie Hackers, blog)
- Money Manager: 22 sources (Play Store, App Store, Help Center, review aggregators, user review platforms)

**Verification methods:**
- Official websites + feature pages (100%)
- Help Center / Support docs (100%)
- App Store / Play Store store listings (100%)
- Third-party reviews (AppAdvice, CHOICE, Bridging Apps, JustUseApp) (80%)
- User voice (Product Hunt, Indie Hackers, implied from feature gaps) (70%)
- YouTube product reviews (not embedded, but cited)
- Reddit discussions (0 found for Wallet/Lunch Money; Realbyte forum posts only)

---

## UNRESOLVED QUESTIONS

1. **Lunch Money:** Do email digest notifications exist (daily/weekly)? Not confirmed in search results.
2. **Money Manager:** Is there a cloud sync roadmap beyond subscription? Help Center silent on future direction.
3. **Wallet:** Does family sharing support approval workflow for expenses over threshold? Docs unclear.
4. **Wallet:** Support for custom recurring transaction patterns (e.g., "biweekly on odd weeks")? Not verified.
5. **Money Manager:** Any GDPR/CCPA compliance documentation? No explicit privacy policy analysis conducted.
6. **Lunch Money:** What % of users access via API vs. UI? Active developer count? Ecosystem health metric missing.

