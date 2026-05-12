# BE Tech Doc Template

> **Use này** khi tạo `docs/features/BE/feature-<name>-tech.md`.
> **Pair với** FE spec trong `docs/features/feature-<name>.md`.
> **Linter:** kiểm tra cả 2 file cùng exist + sections required.

---

# BE Tech Doc: <Tên> (<F##>)

> **Version:** v1.0.0
> **Ngày tạo:** YYYY-MM-DD
> **Trạng thái:** Draft | Ready | Locked | Implemented
> **Tham chiếu FE spec:** [feature-<name>.md](../feature-<name>.md)

---

## 1. Implementation Overview

<1 đoạn high-level: modules touched, data flow, integration points. Nhắm developer onboarding nhanh.>

**Files touched (estimate):**
- `core/<module>.py` — <what>
- `markets/vn/<module>.py` — <what>
- `tests/...` — <what>

---

## 2. Database Schema

<DDL changes hoặc "N/A — không thay đổi schema". Nếu có:>

```sql
-- Migration: <description>
ALTER TABLE ... ;
CREATE TABLE ... ;
```

**Migration risk:**
- Up: <safe / requires downtime / requires backfill>
- Down: <reversible / one-way>
- Backfill: <yes/no — nếu yes, ETA>

---

## 3. API Contract

<Function signatures, payload schemas, error types. Code blocks Python.>

```python
# core/<module>.py
async def function_name(arg: Type) -> ReturnType:
    """Docstring with invariants."""
```

---

## 4. Implementation Details

<Code-level decisions: algorithm choice, library use, perf considerations. BEFORE/AFTER blocks hữu ích cho refactor.>

---

## 5. Testing Plan

<Test files, fixture strategy. Map về 5 categories ở FE spec autopilot:test_plan block.>

| Test file | Layer | Categories covered |
|-----------|-------|--------------------|
| `tests/unit/test_X.py` | unit | happy, missing-optional |
| `tests/integration/test_X.py` | integration | retry, pathological |
| `tests/integration/test_X_isolation.py` | integration | concurrent (tenant) |

**Fixtures:**
- Real: `tests/fixtures/real/<feature>/...`
- Synthetic: `tests/fixtures/synthetic/<feature>/...`

---

<!-- autopilot:invariants
# HARD invariants được codify static (import-linter, mypy, alembic CHECK).
# Linter cảnh báo nếu invariant không có enforcement mechanism.
- name: <invariant name>
  enforcement: import-linter | mypy | alembic CHECK | runtime assert | test only
  contract_file: <path nếu enforcement = static>
-->

---

## Changelog

| Version | Ngày | Thay đổi |
|---------|------|----------|
| v1.0.0 | YYYY-MM-DD | Initial. |
