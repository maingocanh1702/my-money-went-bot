# Tiền Về Nơi Đâu — Technical Design Document (TDD)

> **Version:** v1.8.1
> **Ngày tạo:** 2026-05-05
> **Cập nhật lần cuối:** 2026-05-10
> **Trạng thái:** Draft
> **Tham chiếu:** [BRD-vi v3.1.0](file:///Users/maingocanh/Projects/MyMoneyWent/docs/brd-vi.md) · [PRD-vi v1.7.1](file:///Users/maingocanh/Projects/MyMoneyWent/docs/prd-vi.md) · [Feature: SaaS Refactor](file:///Users/maingocanh/Projects/MyMoneyWent/docs/features/feature-saas-refactor.md) · [Feature: Payment](file:///Users/maingocanh/Projects/MyMoneyWent/docs/features/feature-payment.md) · [Feature: Messenger](file:///Users/maingocanh/Projects/MyMoneyWent/docs/features/feature-messenger-channel.md) · [Impl Plan VietQR+Email](file:///Users/maingocanh/Projects/MyMoneyWent/docs/implementation-plans/implementation-plan-payment-vietqr-email.md) · [Feature: Admin Tools](file:///Users/maingocanh/Projects/MyMoneyWent/docs/features/feature-admin-tools.md) · [DR Runbook](file:///Users/maingocanh/Projects/MyMoneyWent/docs/runbooks/disaster-recovery.md) · [Observability](file:///Users/maingocanh/Projects/MyMoneyWent/docs/operations/observability-plan.md)
>
> **🌐 SCOPE NOTE:** TDD này cover **shared technical foundation** (DB schema, FastAPI architecture, messenger interface, auth) + **VN-specific implementations** (SePay webhook, VN bank email parsers, VietQR payment). **Global market** có TDD riêng — [tdd-en.md](file:///Users/maingocanh/Projects/MyMoneyWent/docs/tdd-en.md) — với capture stack riêng (Plaid/TrueLayer/Tink + e-com OAuth + Stripe Checkout payment). Shared foundation sections (§1-2 architecture, §2 DB schema core tables, §5 deployment) apply cho cả 2 markets. Per [ADR-0001](file:///Users/maingocanh/Projects/MyMoneyWent/docs/adr/0001-monorepo-not-split-repos.md), VN code lives at `markets/vn/`, shared foundation at `core/`.
>
