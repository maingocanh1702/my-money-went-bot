# Bot Finance SaaS Pivot PRD v1

## 1. Document Control

- Product: Bot Finance SaaS
- Version: v1.0
- Date: 2026-05-05
- Author: Richard
- Status: Draft
- Stakeholders: Ngoc-Anh, Product, Engineering, Growth, Support

---

## 2. Executive Summary

- Problem statement: Current product delivers value only after users complete a long, fragile self-hosted setup: create Telegram bot, copy bot token, fetch chat ID, create Google Sheet, create Google Cloud project, create service account, deploy backend, configure webhook, and maintain infra. This kills activation.
- Proposed solution: Pivot from a self-hosted automation kit to a managed SaaS platform where chat remains the primary UI, while the platform owns backend, database, connectors, scheduling, secrets, and infra.
- Business value: Setup friction drops from expert-only to consumer-grade. Faster activation should improve conversion, retention, and support efficiency while creating a defensible platform instead of a template repo.
- Scope summary (V1/V2):
  - V1: Hosted Telegram-first SaaS with SePay + email forwarding ingestion, platform-managed backend, tracking-first default, optional budgets.
  - V2: Additional channels, richer connectors, teams/workspaces, exports, advanced automation.

---

## 3. Goals & Non-Goals

### 3.1 Goals

- Reduce first-time setup to under 5 minutes for the primary onboarding path.
- Remove all user-facing infrastructure/config steps from the happy path.
- Preserve the core value loop: transaction arrives → user categorizes in chat → report/update is visible immediately.
- Establish a multi-tenant foundation suitable for SaaS operations.
- Keep budget optional; tracking-only must work out of the box.

### 3.2 Non-Goals

- Building a full standalone consumer finance app UI to replace chat.
- Supporting every messaging platform in V1.
- Becoming a full accounting/ERP system.
- Covering every bank/provider integration in V1.
- Solving enterprise-grade reconciliation or bookkeeping workflows in V1.

---

## 4. Users & Use Cases

### 4.1 Target Users / Personas

| Persona | Needs | Pain Points | Priority |
| ------- | ----- | ----------- | -------- |
| VN individual user who already uses Telegram | Track spend with minimal setup; categorize fast inside chat | Current setup is too technical; budgeting apps feel heavy | High |
| Small operator / founder managing personal or business cashflow informally | Quick visibility into spending and inflows without learning accounting software | Existing tools require too much setup and context switching | High |
| Existing self-hosted bot user | Wants same core utility without owning infra | Maintenance burden, secret/config sprawl, fragility | Medium |

### 4.2 Core Use Cases

| ID | Use case | Actor | Expected outcome | Priority |
| ---- | -------- | ----- | ---------------- | -------- |
| UC-1 | Start using Bot Finance on Telegram | New user | User connects chat and completes onboarding in minutes | High |
| UC-2 | Connect a transaction source | New user | Transactions begin flowing into the platform without self-hosting | High |
| UC-3 | Categorize an incoming transaction | Active user | User assigns transaction to a category/sub-category in chat | High |
| UC-4 | View current month status | Active user | User sees up-to-date spend/income summary in chat | High |
| UC-5 | Use tracking-only mode | New user | User gets value without configuring budgets | High |
| UC-6 | Optionally set monthly budgets | Active user | User receives budget-aware reporting and alerts | Medium |
| UC-7 | Recover when no connector is available | New user | User can still use CSV/manual/email forwarding fallback | Medium |
| UC-8 | Support/admin investigate issues | Internal team | Team can inspect tenant, events, failures, and state safely | High |

---

## 5. Functional Requirements (V1)

### 5.1 Feature List

| ID | Requirement | Description | Priority |
| ------ | ----------- | ----------- | -------- |
| FR1-V1 | Hosted official Telegram bot | Platform provides and operates the bot; users never create their own bot token | High |
| FR2-V1 | Lightweight web onboarding | Web flow for account creation, channel linking, source connection, and settings | High |
| FR3-V1 | Multi-tenant account model | Platform supports isolated users/workspaces and channel identities | High |
| FR4-V1 | Transaction ingestion via SePay | Hosted webhook endpoint for SePay with tenant-scoped routing | High |
| FR5-V1 | Transaction ingestion via email forwarding | Platform provides per-tenant forwarding address or equivalent hosted inbox | High |
| FR6-V1 | Canonical transaction pipeline | All sources normalize into one transaction schema and processing flow | High |
| FR7-V1 | In-chat categorization | User can categorize transactions from Telegram using buttons and quick replies | High |
| FR8-V1 | Default categories | New users receive sensible default categories automatically | High |
| FR9-V1 | Tracking-only mode by default | Product works without budget configuration | High |
| FR10-V1 | Optional budget setup | User can add/update budgets later, from chat or control plane | Medium |
| FR11-V1 | Reports and recaps | Daily/today, weekly, monthly, and status summaries delivered in chat | High |
| FR12-V1 | Manual fallback / CSV import | User can still start without supported live connectors | Medium |
| FR13-V1 | Admin/support tooling | Internal console for tenant lookup, raw events, errors, state, retries | High |
| FR14-V1 | Export capability | User can export data to CSV; Google Sheets export is optional integration, not runtime dependency | Medium |
| FR15-V1 | Basic billing readiness | Track tenant plan/trial status even if monetization starts manually | Medium |

### 5.2 User Stories — V1

#### US-V1-01: Start on Telegram without technical setup

Acceptance Criteria:

- [ ] User can begin by clicking a Telegram deep link or Start button.
- [ ] User is never asked for bot token, chat ID, webhook URL, or server setup.
- [ ] User reaches a usable state in under 5 minutes on the happy path.

Priority: High | ID: FR1-V1, FR2-V1

#### US-V1-02: Connect a transaction source with minimal input

Acceptance Criteria:

- [ ] User can choose SePay, email forwarding, CSV import, or manual fallback.
- [ ] For SePay, platform provides the connection information the user needs without exposing internal infra.
- [ ] For email forwarding, user receives a tenant-specific address or hosted connection flow.

Priority: High | ID: FR4-V1, FR5-V1, FR12-V1

#### US-V1-03: Receive and categorize transactions in chat

Acceptance Criteria:

- [ ] Incoming transactions create a message in Telegram within target SLA.
- [ ] User can categorize using inline buttons.
- [ ] User can recategorize after the fact.

Priority: High | ID: FR6-V1, FR7-V1

#### US-V1-04: Use the product without budgets

Acceptance Criteria:

- [ ] New users are seeded with default categories.
- [ ] Reports work even when all categories are tracking-only.
- [ ] Budget prompts are optional and can be postponed.

Priority: High | ID: FR8-V1, FR9-V1

#### US-V1-05: Optionally add budget limits later

Acceptance Criteria:

- [ ] User can set or edit budget amounts after onboarding.
- [ ] Reports reflect budget status where configured.
- [ ] Categories without budget remain valid and visible.

Priority: Medium | ID: FR10-V1

#### US-V1-06: Get periodic summaries in chat

Acceptance Criteria:

- [ ] User can request current status, today view, weekly summary, and monthly report.
- [ ] Scheduled recaps run from platform-managed jobs.
- [ ] Timezone is configurable per tenant/user.

Priority: High | ID: FR11-V1

#### US-V1-07: Recover from connector gaps

Acceptance Criteria:

- [ ] User can upload CSV to backfill history.
- [ ] User can manually record transactions if needed.
- [ ] Lack of a live connector does not fully block activation.

Priority: Medium | ID: FR12-V1

#### US-V1-08: Internal team can debug safely

Acceptance Criteria:

- [ ] Support/admin can inspect tenant state, recent events, and delivery failures.
- [ ] Sensitive data access is auditable.
- [ ] Failed events can be retried without mutating unrelated tenants.

Priority: High | ID: FR13-V1

---

## 6. User Stories — V2

### US-V2-01: Use the same workspace across multiple chat platforms

Acceptance Criteria:

- [ ] A workspace can link more than one channel identity.
- [ ] Core business logic remains consistent across channels.
- [ ] Channel-specific capability differences are handled by adapters.

Priority: Medium | ID: FRx-V2

### US-V2-02: Invite collaborator(s) into a workspace

Acceptance Criteria:

- [ ] Workspace owner can invite another member.
- [ ] Permissions are role-based.
- [ ] Reports and actions are scoped correctly by workspace membership.

Priority: Medium | ID: FRx-V2

### US-V2-03: Use richer automation and rules

Acceptance Criteria:

- [ ] User can define auto-categorization rules.
- [ ] Rules can be reviewed, edited, and disabled.
- [ ] Rule application is auditable.

Priority: Medium | ID: FRx-V2

### US-V2-04: Export to external destinations

Acceptance Criteria:

- [ ] User can export to Google Sheets or other destinations on demand.
- [ ] Export failures do not affect runtime transaction capture.
- [ ] Export jobs are replayable.

Priority: Medium | ID: FRx-V2

---

## 7. Non-Functional Requirements

### 7.1 Performance

| ID | Yêu cầu | Target | Priority |
| ---- | -------- | -------- | -------- |
| NFR1 | Transaction notification latency | P95 < 15s from accepted webhook/email parse to outbound Telegram message | High |
| NFR2 | Chat command response time | P95 < 2s for cached/simple status calls | High |
| NFR3 | Onboarding page load | < 3s on broadband/mobile | Medium |

### 7.2 Scalability

| ID | Yêu cầu | Target | Priority |
| ---- | ------------- | -------- | -------- |
| NFR4 | Multi-tenant growth | Support at least 10k active workspaces without architecture rewrite | High |
| NFR5 | Connector extensibility | Add a new source connector without changing core domain contracts | High |

### 7.3 Reliability

| ID | Yêu cầu | Target | Priority |
| ---- | ------------- | -------- | -------- |
| NFR6 | Event delivery durability | No acknowledged inbound event is silently dropped | High |
| NFR7 | Scheduled jobs | Daily/weekly/monthly jobs succeed at >99% | High |
| NFR8 | Idempotency | Duplicate source events must not create duplicate canonical transactions | High |

### 7.4 Security

| ID | Yêu cầu | Target | Priority |
| ---- | ------------- | -------- | -------- |
| NFR9 | Tenant isolation | Hard tenant scoping on all reads/writes | High |
| NFR10 | Secrets management | No user-managed runtime secrets required for the happy path | High |
| NFR11 | Access auditing | Admin/support access to sensitive data is logged | High |
| NFR12 | Data protection | Encrypt sensitive data at rest and in transit | High |

### 7.5 Usability

| ID | Yêu cầu | Target | Priority |
| ---- | ------------- | -------- | -------- |
| NFR13 | Setup friction | Happy-path setup completed in <5 minutes | High |
| NFR14 | Input burden | User provides no more than channel + source + timezone/currency on first setup | High |
| NFR15 | Progressive disclosure | Optional budget/advanced settings deferred until after activation | High |

### 7.6 Maintainability

| ID | Yêu cầu | Target | Priority |
| ---- | ------------- | -------- | -------- |
| NFR16 | Domain separation | Channel adapters and source connectors are isolated from core business logic | High |
| NFR17 | Schema evolution | Category taxonomy and monthly budget config are modeled separately | High |

### 7.7 Observability

| ID | Yêu cầu | Target | Priority |
| ---- | ------------- | -------- | -------- |
| NFR18 | End-to-end tracing | Trace inbound source event → canonical transaction → chat delivery | High |
| NFR19 | Alerting | Actionable alerts for ingestion failure, queue buildup, and outbound channel errors | High |

---

## 8. Success Metrics

### 8.1 V1 Success Metrics

| Metric | Target | Đo lường |
| -------- | -------- | -------- |
| Onboarding completion rate | >60% from signup to connected channel + source | Funnel analytics |
| Time-to-first-value | <10 minutes median to first categorized transaction | Event timestamps |
| 7-day retention | >35% of activated users still sending/receiving interactions | Product analytics |
| Setup support rate | <15% of new users require human setup help | Support tagging |
| Tracking-only activation | >50% of activated users use tracking-only before adding any budget | Product analytics |

### 8.2 V2 Success Metrics

| Metric | Target | Đo lường |
| -------- | -------- | -------- |
| Multi-channel linked workspace rate | >20% among mature users | Product analytics |
| Paid conversion | Target defined after V1 retention baseline | Billing analytics |
| Auto-categorization rate | >40% of transactions categorized automatically where rules exist | Domain metrics |

### 8.3 Leading Indicators

| Indicator | Target | Hành động nếu dưới target |
| ----------- | -------- | ------------------------- |
| Step-off after source connection | <25% | Simplify connector UX, add fallback/manual path |
| First transaction delivery failures | <2% | Investigate connector + queue + channel issues |
| Support tickets mentioning setup confusion | <10% of new-user tickets | Rewrite onboarding copy and reduce required choices |

---

## 9. Assumptions, Constraints & Risks

### 9.1 Assumptions

| ID | Giả định | Rủi ro nếu sai | Biện pháp |
| -- | ------------ | -------------- | ------------ |
| A1 | Telegram is the fastest path to PMF for the first target segment | Building for the wrong channel slows learning | Launch Telegram first, validate before expanding |
| A2 | Users accept a lightweight web step for onboarding/control plane | Pure chat onboarding may not be enough for source setup | Keep web minimal and measure drop-off |
| A3 | SePay + email forwarding cover enough initial transaction volume | Activation may stall for users without these sources | Provide CSV/manual fallback |
| A4 | Tracking-first default improves activation | Some users may expect budget-first setup | Keep budget optional but discoverable |

### 9.2 Constraints

| ID | Ràng buộc | Loại | Ảnh hưởng |
| -- | ------------ | ----------------------------------- | --------- |
| C1 | Messaging platform capabilities differ | Technical | UX abstraction cannot be perfectly uniform |
| C2 | Financial data sensitivity raises trust/compliance needs | Technical/Operational | Requires stronger security, support process, and retention controls |
| C3 | Small team bandwidth | Resource | Must sequence channel and connector scope tightly |

### 9.3 Dependencies

| ID | Dependency | Owner | Rủi ro | Biện pháp |
| -- | ------------ | ------- | ----------------- | ------------ |
| D1 | Telegram bot approval/operability | Engineering/Product | Medium | Validate platform constraints early |
| D2 | SePay integration path | Engineering/Partnership | Medium | Keep email/CSV fallback |
| D3 | Hosted email ingestion | Engineering | High | Scope early and instrument heavily |
| D4 | Billing/provider selection | Business/Product | Medium | Keep plan state abstract in V1 |

### 9.4 Risks

| ID | Rủi ro | Xác suất | Mức độ | Biện pháp |
| -- | ------ | ----------------- | ----------------- | ------------ |
| R1 | Multi-channel support added too early causes architecture/product sprawl | High | High | Telegram-only V1; define adapter contracts first |
| R2 | Product keeps self-hosted assumptions and leaks complexity into onboarding | High | High | Ban user-facing infra/config in PRD acceptance criteria |
| R3 | Email parsing is brittle across banks | Medium | Medium | Treat as connector, not foundation; monitor parse confidence |
| R4 | Weak tenant isolation or auth design harms trust | Medium | High | Enforce workspace scoping and audit access from day one |
| R5 | Chat-only UX becomes limiting | Medium | Medium | Use web as control plane for advanced tasks |

---

## Appendix

### A. Glossary

| Term | Definition |
| ------ | ------------ |
| Workspace | Tenant boundary containing data, settings, and channel/source connections |
| Channel Identity | A user/workspace identity on a chat platform such as Telegram |
| Source Connector | Integration that ingests transaction-like events into the platform |
| Canonical Transaction | Normalized internal representation of a financial event |
| Tracking-only | Mode where spending is categorized and reported without any budget limit |

### B. References

| Tài liệu | Link |
| ---------- | ------ |
| Current self-hosted repo | /Users/maingocanh/Projects/Bot Finance |
| README | /Users/maingocanh/Projects/Bot Finance/README.md |

---

**End of Document**
