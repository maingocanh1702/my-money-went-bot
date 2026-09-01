# Autopilot Invariant Catalog — My Money Went Bot

> This catalog serializes changes that share a financial, identity, transport, or delivery invariant
> in My Money Went Bot. The operational global tokens below are shared with the canonical kit.

Manifest and registry use exact tokens to serialize file-disjoint changes that share a domain.
Unknown token ⇒ `INVARIANT_UNKNOWN`.

Rules:

- one token = one behavior/domain invariant, not one file;
- shared token means sequential execution;
- add a real new token before using it; do not invent synonyms per task;
- consumer may add stricter tokens, never silently rename a token used by an active task;
- machine tokens are the first whitespace-delimited field between the markers.

## Canonical tokens

<!-- catalog:start -->
workflow-authority — task-contract and Level-3 operating-policy changes
kit-integrity — shared scripts, templates, versions and consumer rollout
risk-policy — action/surface risk derivation and autonomy lane
terminal-lifecycle — READY/AWAIT/HALT, recovery and cleanup
review-integrity — independent review, breaker and readiness evidence
delegation-safety — worktree, writer ownership and child-agent boundaries
audit-integrity — task evidence, provenance and learning history
merge-authority — landing and optional separately-authorized automation
storage-schema — Google Sheet tab schemas, canonical field mappings, and backward-compatible data evolution
transaction-ledger — transaction identity, financial direction, amount, balance, voiding, and idempotency
cashback-ledger — cashback rules, qualification, cycle caps, accrued rewards, and cashback audit entries
sheet-projection — Google Sheet layout, row mappings, synchronization boundaries, and reconciliation markers
external-webhooks — SePay, email, and other inbound webhook authentication, parsing, and replay protection
account-identity — accounts, cards, source keys, owner mappings, and identity resolution
bot-state — Telegram and Zalo interaction state, callbacks, pending choices, and expiry handling
reporting — reports, allocation views, summaries, and derived display totals
telegram-transport — Telegram commands, handlers, messages, and callback adapters
zalo-transport — Zalo commands, menus, messages, and adapter-specific routing
shared-finance-core — transport-agnostic categorization, account, transaction, cashback, and reporting decisions
test-chain — Python test runners, fixtures, backing-store isolation, and CI registration
build-config — dependency manifests, runtime packaging, deployment configuration, and tooling
<!-- catalog:end -->

Projects that implement optional machine-global admission/certification may add dedicated tokens.
Those optional tokens are not prerequisites for the operational workflow.
