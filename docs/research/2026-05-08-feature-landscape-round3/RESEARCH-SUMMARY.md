# RESEARCH SUMMARY: Feature Landscape Round 3 (May 2026)

**Research Date:** May 8, 2026  
**Apps Analyzed:** Money Lover, Spendee, Toshl Finance  
**Focus:** 12-category feature analysis (Transaction Capture, Categorization, Reports, Budgeting, Multi-currency, Multi-account, P/B, Collaboration, Notifications, Integrations, Platform, Security)  
**Deliverables:** 3 detailed feature cards + this summary

---

## 🎯 EXECUTIVE SUMMARY

### Market Position (by feature strength)

| App | Strongest Features | Weakest Features | Pricing | Users | Rating |
|-----|---|---|---|---|---|
| **Money Lover** | Shared wallets, Goal wallets, Southeast Asia bank sync | No OCR, no API, no collaboration granularity | $0-$19.99 | 10M | 4.6★ |
| **Spendee** | AI receipt scanner, Shared wallets, Bank sync (2.5K providers), Crypto tracking | No recurring setup, no net worth, no API | $0-$119.99 | 3M | 4.6★ |
| **Toshl** | River Flow analytics, 200+ currencies, Flexible recurring, Historical rates | No OCR, no shared wallets, single-user only | $0-$4.99/mo | 3M | 4.7★ |

---

## 📊 12-CATEGORY FEATURE MATRIX

### 1. TRANSACTION CAPTURE
| App | Score | Details |
|-----|:-----:|---------|
| Money Lover | 🟡 | Bank sync (SE Asia only) + manual; no OCR |
| Spendee | ⭐ | AI receipt scanner + 2.5K bank providers + manual + e-wallet + crypto wallet |
| Toshl | ✅ | 3K bank providers (Plaid/Salt Edge) + manual + CSV/OFX import; no OCR |

**Winner:** Spendee (AI receipt scanner is differentiator)

### 2. CATEGORIZATION
| App | Score | Details |
|-----|:-----:|---------|
| Money Lover | 🟡 | Default + custom; limited sub-cat depth |
| Spendee | ✅ | Default + custom + auto-cat from sync + icons |
| Toshl | ✅ | Default + custom tags + location tagging |

**Winner:** Tie (Spendee & Toshl)

### 3. REPORTS & ANALYTICS
| App | Score | Details |
|-----|:-----:|---------|
| Money Lover | 🟡 | Basic (pie/bar charts, category breakdown) |
| Spendee | ✅ | Visual charts + location-based + cash flow tracking |
| Toshl | ⭐ | River Flow (signature) + net worth + historical comparisons |

**Winner:** Toshl (River Flow is unique visualization)

### 4. BUDGETING
| App | Score | Details |
|-----|:-----:|---------|
| Money Lover | ✅ | Multi-category + goal wallets + alerts |
| Spendee | ✅ | Smart budgets + daily limits + goals + shared budget |
| Toshl | ⭐ | Flexible periods (bi-weekly, custom) + category-specific + rollover |

**Winner:** Toshl (flexible periods beat fixed monthly)

### 5. MULTI-CURRENCY
| App | Score | Details |
|-----|:-----:|---------|
| Money Lover | ✅ | All currencies + live rates |
| Spendee | ✅ | Multi-curr + rates + nomad-friendly |
| Toshl | ⭐ | 200+ currencies + 30 crypto + historical rates (back to 1999) + hourly updates |

**Winner:** Toshl (deepest support)

### 6. MULTI-ACCOUNT
| App | Score | Details |
|-----|:-----:|---------|
| Money Lover | ✅ | Multiple wallets (tier-dependent); cash/bank/CC/loan/savings |
| Spendee | ✅ | Multiple wallets (bank, cash, e-wallet, crypto); organize by trip/event |
| Toshl | ✅ | Unlimited (Pro+); credit cards, bank, cash, investments, crypto |

**Winner:** Tie (all support well)

### 7. PERSONAL vs BUSINESS
| App | Score | Details |
|-----|:-----:|---------|
| Money Lover | ❌ | No P/B tagging, tax flags, mileage |
| Spendee | ❌ | No P/B support |
| Toshl | 🟡 | Location tagging can proxy; no formal P/B |

**Winner:** None (all lack P/B features — **opportunity for MMW**)

### 8. COLLABORATION
| App | Score | Details |
|-----|:-----:|---------|
| Money Lover | 🟡 | Shared wallet (new); no granular permissions; basic |
| Spendee | ⭐ | Shared wallets (signature); shared budgets; transparent ("who paid what") |
| Toshl | ❌ | Single-user only; no sharing |

**Winner:** Spendee (**MMW should match this**)

### 9. NOTIFICATIONS
| App | Score | Details |
|-----|:-----:|---------|
| Money Lover | 🟡 | Bill reminders, budget alerts; no weekly recap |
| Spendee | ✅ | Budget alerts (custom), bill reminders, real-time updates |
| Toshl | ✅ | Budget alerts, bill reminders, real-time sync alerts |

**Winner:** Tie (Spendee & Toshl)

### 10. INTEGRATIONS
| App | Score | Details |
|-----|:-----:|---------|
| Money Lover | ❌ | No public API, Zapier, Sheets; bank sync only |
| Spendee | 🟡 | Bank (2.5K) + e-wallet (PayPal) + crypto; no API/Zapier |
| Toshl | 🟡 | Bank (3K) + CSV/OFX import; no API/Zapier |

**Winner:** Spendee (PayPal + crypto explicit; Money Lover narrowest)

### 11. PLATFORM & UX
| App | Score | Details |
|-----|:-----:|---------|
| Money Lover | ✅ | iOS + Android + Web + Desktop (WebCatalog); dark mode |
| Spendee | ⭐ | iOS + Android + Web + Desktop; no ads; clean design; Editors' Choice |
| Toshl | ✅ | iOS + Android + Web; sync across devices; 10+ languages |

**Winner:** Spendee (Editors' Choice award + explicit "no ads" + design recognition)

### 12. SECURITY & PRIVACY
| App | Score | Details |
|-----|:-----:|---------|
| Money Lover | 🟡 | Bank credentials not stored; unclear on 2FA/biometric/E2EE |
| Spendee | ✅ | Bank-level encryption + E2EE channels + GDPR compliant; [unverified]: 2FA/biometric |
| Toshl | ✅ | SSL encryption + encrypted transfer + encrypted DB + 2FA available |

**Winner:** Tie (Spendee & Toshl; both have strong baseline)

---

## 🔍 TOP 3 SURPRISING FINDINGS

### 1. **Spendee = Shared Wallet Champion**
Spendee's shared wallets are the most mature & transparent. "Who paid what" tracking is automatic & visualization-heavy. Money Lover added recently but basic. Toshl has zero collaboration → **MMW's killer advantage should be here**.

### 2. **Toshl's River Flow = Unique Narrative UX**
River Flow is not a gimmick; it's a storytelling device that helps users **intuitively understand cash flow**. No competitor has this. It's a visual metaphor that works. → **MMW could adapt for Telegram: "River card" showing income → account → expenses flow.**

### 3. **OCR/Receipt Scanner = Spendee Only**
Money Lover (10M users, 4.6★) and Toshl (3M users, 4.7★) both lack receipt OCR. Spendee's AI scanner is the only mature solution ← **major feature gap that MMW could own with voice input on Telegram** (even cheaper than OCR).

---

## 💡 KEY LESSONS FOR MMW (Ranked by Impact)

### 🥇 TIER 1: MMW's Competitive Advantages
1. **Shared finances are killer**. Spendee proved this. MMW should go deeper: split expenses, settlement tracking, joint goal management.
2. **Telegram platform is different**. Apps are feature-heavy; Telegram bot can be conversational. "Spent $50 for dinner?" (quick capture) beats app-and-search.
3. **No P/B feature exists**. All three apps ignore this. If MMW supports freelancer tax reporting or mileage tracking, it wins SMB segment.

### 🥈 TIER 2: What to Steal
1. **Goal wallets** (Money Lover's motivational framing).
2. **Flexible recurring** (Toshl's bi-weekly, custom intervals).
3. **AI-assisted input** (Spendee's OCR → MMW's voice for Telegram).

### 🥉 TIER 3: What to Avoid
1. **Complexity creep**. Toshl's 200+ currencies is powerful but confusing for beginner. MMW should surface relevant currencies only (user's home currency + active currencies).
2. **No API/Zapier**. All three have integration gaps. MMW should prioritize: Telegram API (native), Google Sheets (common for SMB).
3. **Single-user model** (Toshl's trap). Collaboration is future.

---

## 🚩 UNRESOLVED QUESTIONS

1. **Money Lover's exact bank sync coverage in 2026**: Listed 8 countries (PH, MY, SG, HK, VN, TH, ID, +?); not all sources consistent.
2. **Spendee's 2FA implementation**: Marketing says "secure" but no detail on SMS vs TOTP vs passkey.
3. **Toshl's offline support**: Web app documented; mobile offline capability unclear.
4. **Crypto wallet auto-tracking beyond Ethereum** (Spendee): Bitcoin planned; timeline unknown.
5. **All three: Data sale or third-party access**: Privacy policies mention data collection for "analytics/ads"; deeper audit needed.

---

## 📈 VERIFICATION STATS

- **Sources consulted:** 45+ (official websites, App Store/Play Store, help centers, blogs, Reddit, SaaS review sites)
- **Screenshots reviewed:** 8+ (app store listings)
- **Direct website fetches:** 5 (feature pages, help centers, blog posts)
- **Unverified claims marked:** ~15 flagged in cards
- **Data currency:** May 2026 (latest available)

---

## 📂 OUTPUT STRUCTURE

```
/assets/research/2026-05-08-feature-landscape-round3/
├── cards/
│   ├── money-lover.md          (detailed 12-category analysis)
│   ├── spendee.md              (detailed 12-category analysis)
│   └── toshl.md                (detailed 12-category analysis)
└── RESEARCH-SUMMARY.md         (this file)
```

Each card includes:
- Positioning + pricing + user metrics
- 3 signature features (with evidence links)
- 12-category scorecard (❌/🟡/✅/⭐)
- Unique interactions
- Feature gaps
- User voice quotes
- Lessons for MMW
- Full source links

---

## 🎯 NEXT STEPS FOR MMW

1. **Prioritize shared wallets** over single-user. Spendee proved market demand.
2. **Research Telegram UX for financial apps**. Conversational capture beats app-and-search.
3. **Validate P/B segment** (freelancer/SMB). Uncontested at this tier.
4. **Prototype voice input** for expense capture. Cheaper than OCR; better UX for Telegram.
5. **Build bill tracking** with flexible recurring. Gap across Money Lover (basic) and Toshl (complex).

---

**Report compiled:** May 8, 2026  
**Analyst:** Claude Research Team  
**Confidence:** High (45+ sources, official docs prioritized)
