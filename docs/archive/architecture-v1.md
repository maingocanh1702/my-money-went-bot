# Bot Finance SaaS — Technical Architecture v1

## 1. Purpose

This document defines the target architecture for pivoting Bot Finance from a self-hosted Telegram bot backed by Google Sheets into a managed, multi-tenant SaaS platform.

The architecture is designed around one core shift:

> Complexity moves from the user to the platform.

Users should no longer own bot provisioning, databases, Google Sheets, service accounts, background jobs, or deployment. The platform will own those concerns while preserving chat as the primary operational UI.

---

## 2. Current State vs Target State

## 2.1 Current State

Current system characteristics:
- Single-user Telegram bot
- User-managed bot token and chat ID
- Google Sheets as runtime source of truth
- Self-hosted FastAPI backend
- Source integrations via SePay webhook and Google Apps Script email bridge
- Single-slot conversation state in sheet row storage
- Reporting and budgeting logic tightly coupled to sheet schema

Current strengths:
- Fast to prototype
- Core value loop already proven
- Strong fit for tracking-first behavior

Current architectural limits:
- User setup is far too technical
- No true tenant model
- Google Sheets is in the runtime-critical path
- State model is fragile under concurrency
- Category taxonomy and monthly budget config are conflated
- Source/channel/business logic boundaries are too loose for scale

## 2.2 Target State

Target system characteristics:
- Managed SaaS platform
- Official platform-operated chat bot(s)
- Multi-tenant Postgres-backed core
- Hosted source connectors
- Chat-first UX with minimal web control plane
- Durable jobs, observability, and support tooling
- Canonical domain model independent of channel and source

---

## 3. Architecture Principles

### P1. Chat-first, not chat-only
Chat is the primary operational UI for recurring workflows. Web is the control plane for onboarding, settings, billing, support, and tasks that are awkward or unsafe in chat.

### P2. Platform-managed infrastructure
Users must never be required to manage runtime credentials, webhooks, storage, deployment, or scheduler infrastructure in the primary flow.

### P3. One canonical transaction model
Every connector must normalize into the same internal financial event model before categorization, reporting, or automation.

### P4. Strong tenant isolation
Every persistent entity and every request path must be workspace-scoped. Support/admin access must be auditable.

### P5. Separate taxonomy from period config
Categories are durable business entities. Budgets are period-scoped allocations. These concepts must not share the same storage abstraction.

### P6. Source adapters and channel adapters are edge concerns
Adapters ingest or deliver. They do not own business logic.

### P7. Event-driven where reliability matters
Capture, normalization, categorization prompts, reminders, and reporting should use durable jobs/events where retries or delayed work are important.

---

## 4. High-Level System Overview

```text
                   ┌──────────────────────────────┐
                   │       Web Control Plane      │
                   │ onboarding / settings / admin│
                   └──────────────┬───────────────┘
                                  │
                                  ▼
                    ┌───────────────────────────┐
                    │      Core API / App       │
                    │ auth / tenants / commands │
                    └───────────┬───────────────┘
                                │
          ┌─────────────────────┼─────────────────────┐
          │                     │                     │
          ▼                     ▼                     ▼
┌─────────────────┐   ┌──────────────────┐   ┌──────────────────┐
│ Channel Adapters│   │ Source Connectors│   │ Job/Worker Layer │
│ Telegram / ...  │   │ SePay/email/CSV  │   │ reports/reminders│
└────────┬────────┘   └────────┬─────────┘   └────────┬─────────┘
         │                     │                      │
         └──────────────┬──────┴──────────────┬──────┘
                        ▼                     ▼
                 ┌────────────────────────────────────┐
                 │          Domain Services           │
                 │ tx / categories / budgets / report │
                 └─────────────────┬──────────────────┘
                                   ▼
                        ┌────────────────────┐
                        │ Postgres + Storage │
                        │ source of truth    │
                        └────────────────────┘
```

---

## 5. Main Subsystems

## 5.1 Web Control Plane

Purpose:
- account creation
- workspace creation
- channel linking
- source connection setup
- advanced settings
- billing
- exports
- support/admin interfaces

Rules:
- Must remain lightweight in V1.
- Must not become a duplicate primary product UI.
- Should deep-link users back into Telegram where possible.

Core pages for V1:
- landing / signup
- onboarding wizard
- source connections
- settings (timezone, currency, report preferences)
- plan/trial page
- CSV import page
- support/admin internal pages

## 5.2 Core API / Application Service

Responsibilities:
- auth/session management
- workspace lifecycle
- user/channel identity management
- command handling from web and channels
- orchestration across domain services

Non-responsibilities:
- direct connector-specific parsing logic
- direct channel rendering beyond adapter contracts
- long-running jobs inline with request paths

Suggested modules:
- identity service
- workspace service
- channel connection service
- source connection service
- transaction orchestration service
- reporting service
- admin service

## 5.3 Channel Adapters

V1 target:
- Telegram only

Future:
- Messenger
- Discord
- potentially other platforms if they are operationally and legally feasible

Adapter responsibilities:
- receive inbound events/webhooks
- validate provider signatures/identity where supported
- map platform identity to internal identity/workspace
- send outbound messages/buttons
- expose channel capability profile

Channel capability abstraction should model:
- inline buttons
- callback actions
- message editing availability
- reply threading/DM semantics
- formatting constraints
- message length constraints

Important boundary:
Business logic must not know Telegram-specific webhook shapes.

## 5.4 Source Connectors

V1 target connectors:
- SePay
- hosted email forwarding/inbox parsing
- CSV import
- manual transaction entry

Connector responsibilities:
- accept external events
- validate/parse source payload
- emit normalized ingestion event
- preserve raw payload for auditing/debugging

Connector non-responsibilities:
- category selection
- budget logic
- reporting
- channel delivery

Connector output contract (conceptual):
```json
{
  "workspace_id": "...",
  "source": "sepay|email|csv|manual",
  "external_ref": "...",
  "occurred_at": "2026-05-05T04:00:00Z",
  "amount": 45000,
  "currency": "VND",
  "direction": "in|out",
  "description": "...",
  "metadata": {},
  "raw_event_id": "..."
}
```

## 5.5 Domain Services

### Transaction Service
Responsibilities:
- ingest normalized events
- deduplicate
- create canonical transaction
- determine categorization state
- emit follow-up actions

### Categorization Service
Responsibilities:
- category selection
- sub-category selection
- recategorization
- optional auto-categorization rules in later phases

### Category Service
Responsibilities:
- manage durable taxonomy
- maintain active/inactive category state
- manage sub-categories
- seed defaults

### Budget Service
Responsibilities:
- manage budget periods
- allocate budget per category per period
- compute spent/remaining on demand or cached view

### Reporting Service
Responsibilities:
- current status summaries
- daily/weekly/monthly reports
- snapshots where needed

### Notification / Scheduling Service
Responsibilities:
- recap schedules
- reminder jobs
- delayed nudges for uncategorized transactions
- retries and backoff

---

## 6. Recommended Data Model

## 6.1 Core Entities

### users
Represents a human account.

Suggested fields:
- id
- email / auth identity
- display_name
- locale
- created_at
- updated_at

### workspaces
Tenant boundary.

Suggested fields:
- id
- name
- owner_user_id
- timezone
- currency
- plan
- status
- created_at
- updated_at

### workspace_members
Memberships and roles.

Suggested fields:
- workspace_id
- user_id
- role
- created_at

### channel_identities
Maps a workspace/user to a provider identity.

Suggested fields:
- id
- workspace_id
- user_id
- provider
- provider_user_id
- provider_chat_id
- metadata
- created_at
- updated_at

### source_connections
Represents configured sources.

Suggested fields:
- id
- workspace_id
- source_type
- status
- config_json
- secret_ref
- created_at
- updated_at

### raw_events
Immutable inbound payload store.

Suggested fields:
- id
- workspace_id
- source_connection_id
- source_type
- external_ref
- received_at
- raw_payload_json
- parse_status
- parse_error

### transactions
Canonical normalized financial events.

Suggested fields:
- id
- workspace_id
- raw_event_id
- source_type
- external_ref
- fingerprint
- occurred_at
- amount_minor
- currency
- direction
- description
- merchant_normalized
- category_id nullable
- subcategory_id nullable
- status (uncategorized/categorized/ignored)
- created_at
- updated_at

### categories
Durable taxonomy.

Suggested fields:
- id
- workspace_id
- key
- name
- type (expense/income/mixed)
- is_default
- is_active
- created_at
- updated_at

### subcategories
Durable sub-taxonomy.

Suggested fields:
- id
- workspace_id
- category_id
- key
- name
- is_active
- created_at
- updated_at

### budget_periods
Represents month or period container.

Suggested fields:
- id
- workspace_id
- period_key (e.g. 2026-05)
- starts_at
- ends_at
- status
- created_at
- updated_at

### budget_allocations
Per-category allocations per period.

Suggested fields:
- id
- budget_period_id
- category_id
- allocated_minor
- daily_cap_minor nullable
- created_at
- updated_at

### conversation_states
Short-lived chat interaction state.

Suggested fields:
- id
- workspace_id
- channel_identity_id
- flow_type
- subject_type
- subject_id
- state_json
- expires_at
- created_at
- updated_at

### outbound_messages
Audit log for channel deliveries.

Suggested fields:
- id
- workspace_id
- channel_identity_id
- provider
- message_type
- payload_json
- delivery_status
- provider_message_id
- sent_at

### scheduled_jobs
Logical scheduled work items.

Suggested fields:
- id
- workspace_id nullable
- job_type
- run_at
- status
- attempts
- payload_json
- created_at
- updated_at

## 6.2 Critical Modeling Decisions

### Decision A: taxonomy separated from budgets
This is non-negotiable.

Wrong model:
- one table stores both categories and monthly budgets

Correct model:
- categories define structure
- budget periods define time windows
- allocations join the two

### Decision B: conversation state must be scoped
Current single-slot state per chat is too fragile.

Target approach:
- state keyed by flow + subject (e.g. transaction_id)
- supports multiple concurrent interactions safely
- can expire automatically

### Decision C: raw events are immutable
Never discard raw inbound payloads for events the platform accepts. They are required for debugging, replay, and auditability.

---

## 7. Ingestion and Processing Flows

## 7.1 SePay Flow

```text
SePay webhook
  → source adapter validates request
  → raw event stored
  → parser normalizes payload
  → transaction service runs idempotency/dedup
  → canonical transaction created
  → category prompt job emitted if needed
  → Telegram adapter sends categorization prompt
```

Notes:
- Source connection to workspace mapping must be explicit and secure.
- Idempotency should use external_ref when reliable, otherwise fingerprint fallback.

## 7.2 Email Forwarding Flow

```text
User forwards bank email or auto-forwards to hosted inbox
  → email ingestion service receives message
  → raw email stored
  → bank-specific parser extracts transaction candidate
  → parser emits normalized event
  → transaction service processes as above
```

Notes:
- Parse confidence should be stored.
- Unknown format should create support/diagnostic signal, not silent failure.

## 7.3 CSV Import Flow

```text
User uploads CSV in control plane
  → file stored temporarily
  → parser maps columns to canonical format
  → preview/confirm step
  → batch ingestion job
  → transactions inserted with source=csv
```

## 7.4 Manual Entry Flow

```text
User invokes manual add in chat or web
  → simple structured input captured
  → canonical transaction inserted directly
  → optional category selection prompt
```

---

## 8. Chat Interaction Model

## 8.1 Telegram V1

Telegram is the recommended first channel because it supports:
- deep-link start
- inline buttons
- callback interactions
- low-friction DM model
- reliable enough bot operations for this use case

### Core chat interactions in V1
- onboarding completion handoff
- categorize transaction
- recategorize transaction
- request status
- request today view
- request weekly/monthly report
- create category quickly
- set/edit budget optionally

### Interactions that should remain in web
- source connection setup beyond simple chat links
- plan/billing management
- CSV import
- advanced settings
- support flows

## 8.2 Channel Adapter Contract

Conceptually, adapters should expose methods like:
- send_text(workspace/channel_identity, content)
- send_choices(...)
- edit_message(...)
- acknowledge_action(...)
- map_inbound_event(...)

Domain services should emit abstract UI intents, not Telegram payloads.

---

## 9. API and Service Boundaries

## 9.1 Public Inbound Endpoints

Examples:
- `/api/channels/telegram/webhook`
- `/api/sources/sepay/{connection_token}`
- `/api/sources/email/inbound`
- `/api/imports/csv`

Rules:
- every inbound edge must authenticate/verify where possible
- workspace resolution must never rely on untrusted user input alone
- raw event persistence should happen before heavy processing

## 9.2 Internal Service Boundaries

Avoid a premature microservices split if the team is small.

Recommended V1 deployment style:
- modular monolith
- shared Postgres
- background worker process
- clear package boundaries inside one codebase

Reason:
The problem right now is foundation and ownership of complexity, not distributed systems theater.

---

## 10. Reliability Model

## 10.1 Idempotency

Need more than in-memory dedup.

Recommended approach:
- raw event uniqueness where provider allows
- canonical transaction fingerprint table
- database-level unique constraints where safe
- replay-safe workers

Suggested uniqueness candidates:
- `(workspace_id, source_type, external_ref)`
- fallback fingerprint on normalized `(direction, amount, occurred_at_bucket, description_hash)`

## 10.2 Durable Job Processing

Use background workers for:
- sending categorization prompts
- delayed reminders
- scheduled reports
- export jobs
- retries

Queue requirements:
- retry support
- dead-letter visibility
- idempotent execution
- observability

## 10.3 Failure Handling

Design rules:
- never silently drop accepted events
- store parse failures with reason
- expose retry tooling for support/admin
- separate ingestion acceptance from downstream delivery success

---

## 11. Security and Trust Model

## 11.1 Authentication and Authorization

- User auth handled through web control plane session/OAuth/email link/etc.
- Channel inbound events must be mapped to a known channel identity.
- Every read/write path must be workspace-scoped.
- Admin/support actions require role checks and audit trails.

## 11.2 Secret Management

Users should not manage runtime secrets in the happy path.

Platform-managed secrets include:
- bot credentials
- source connection secrets
- email ingestion credentials
- encryption keys / secret refs

## 11.3 Data Protection

Recommended baseline:
- TLS everywhere
- encrypted secrets
- encrypted backups
- row-level or application-enforced tenant scoping
- PII minimization where possible
- retention policy for raw inbound data and deleted workspaces

## 11.4 Support Access Model

Support and admins may need access to diagnose issues. That access must be:
- explicit
- logged
- minimal
- reviewable

---

## 12. Observability Requirements

Required telemetry:
- inbound event counts by source
- parse success/failure rates
- dedup hit rate
- prompt send latency
- outbound channel delivery failures
- uncategorized aging bucket
- job queue depth and retry rates
- onboarding funnel metrics

Useful operational dashboards:
- connector health
- per-channel delivery health
- top parse failures by bank/provider
- tenant activation funnel
- support workload by issue category

---

## 13. Deployment Recommendation

## 13.1 V1 Deployment Shape

Recommended:
- one app codebase (modular monolith)
- one API/web process
- one or more background worker processes
- Postgres primary DB
- object/file storage for imports and raw artifacts if needed
- managed scheduler or queue-backed scheduled job system

Why not start with microservices:
- team likely does not need the operational cost
- boundaries should be code-level first
- correctness, speed, and iteration matter more than service count

## 13.2 Environment Separation

At minimum:
- local/dev
- staging
- production

Need:
- isolated credentials
- isolated bot/webhook configs where relevant
- seed/test workspaces
- replay-safe staging connectors

---

## 14. Migration Path from Current Repo

## Phase A — Extract domain truth
From the current codebase, extract and rewrite as domain modules:
- transaction normalization concepts
- categorization flow rules
- reporting formulas
- default category seeding

Do not carry forward directly:
- Google Sheets persistence assumptions
- single-slot bot state design
- Telegram-specific logic inside domain handlers

## Phase B — Introduce proper persistence model
- design Postgres schema
- create repositories/services
- build migration-safe domain tests

## Phase C — Rebuild edges around new core
- Telegram adapter
- SePay connector
- email ingestion service
- web onboarding/control plane

## Phase D — Backfill support tools and exports
- admin visibility
- CSV export/import
- optional Google Sheets export integration

---

## 15. MVP Scope Recommendation

## In scope for architecture V1
- Telegram only
- one workspace per primary user initially
- SePay connector
- email forwarding connector
- CSV/manual fallback
- Postgres-backed canonical transaction system
- reports + tracking-first flows
- optional budgets
- lightweight web onboarding/settings

## Out of scope for architecture V1
- Discord and Messenger launch at the same time
- custom user-owned bots
- Google Sheets as core runtime DB
- accounting-grade ledgering
- advanced collaborative roles beyond owner/member basics
- ML-heavy auto-categorization

---

## 16. Open Questions

These must be resolved before implementation lock:

1. What is the first ICP exactly: personal finance, micro-business operators, or both?
2. Is one workspace always one person in V1, or do we support a “household/team” concept early?
3. What is the billing model: per workspace, per active source, or freemium with usage caps?
4. How much raw email content do we need to retain, and for how long?
5. Do we want a platform-generated forwarding inbox, Gmail connect flow, or both over time?
6. Are inflows first-class reporting entities in V1, or mostly secondary to expense tracking?
7. What export destination matters most after CSV: Google Sheets or something else?

---

## 17. Recommended Next Decisions

1. Lock product scope for V1:
   - Telegram-only
   - SePay + email + CSV/manual
   - tracking-first

2. Lock core domain model:
   - workspaces
   - transactions
   - categories
   - budget periods
   - allocations
   - conversation states

3. Choose infrastructure baseline:
   - Postgres
   - queue/worker approach
   - auth approach
   - storage approach

4. Write implementation plan by milestone, not by component list.

---

## 18. Final Position

The current self-hosted project is a good proof of behavior, but it is the wrong ownership model for a SaaS product.

The real pivot is not “make setup nicer.”
The real pivot is:

> stop making users assemble the machine.
> build the machine as the product.

That means the platform must own:
- identity
- integrations
- persistence
- jobs
- supportability
- security
- delivery

And chat remains the interface users actually live in.
