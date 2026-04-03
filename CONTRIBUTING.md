# Contributing to REVERSE-OS

Thank you for your interest in contributing. This document covers everything you need to get up and running as a contributor.

## Development setup

```bash
git clone https://github.com/your-org/reverse-os
cd reverse-os
poetry install
cp .env.example .env    # fill in DATABASE_URL and required secrets
createdb reverseos
psql reverseos < migrations/001_initial_schema.sql
psql reverseos < migrations/002_seed_rules.sql
uvicorn main:app --reload
```

## Three non-negotiable rules

These apply to all contributions:

1. **Idempotency** — every write must be safe to retry. Use `UNIQUE idempotency_key` constraints and pre-creation checks.
2. **State machine** — use `return_obj.transition_to(new_status)`. Never set `.status` directly.
3. **Immutable logs** — never update or delete from `audit_log` or `rule_execution_log`. These tables have DB-level triggers blocking mutations.

## Security checklist

- Never log raw PII. Use `anonymize_payload()` from `core/security/pii.py` before logging.
- New admin endpoints must have a role guard: `Depends(require_role("admin"))` or `Depends(require_min_role("warehouse"))`.
- New admin write operations must add an `AuditLog` entry.
- Incoming webhooks must verify signatures before processing payload.

## Adding an integration

### New eCommerce platform

1. Create `integrators/ecommerce/yourplatform.py`
2. Implement the `EcommerceIntegrator` ABC (`platform`, `fetch_order`, `update_order_status`, `verify_order_token`)
3. Register conditionally in `main.py` `_register_integrators()`
4. Add the required env vars to `core/config.py` and `.env.example`

### New logistics provider

1. Create `integrators/logistics/yourprovider.py`
2. Implement `LogisticsIntegrator` ABC (`provider`, `create_return_label`, `get_tracking_status`, `cancel_label`)
3. Register in `main.py`

### New payment provider

1. Create `integrators/payments/yourprovider.py`
2. Implement `PaymentIntegrator` ABC (`provider`, `create_refund`, `get_refund_status`)
3. Add Celery retry logic for 5xx errors only (not 4xx — those are not retryable)

## Adding a rule condition field

1. Open `modules/rule_engine/engine.py`
2. Add your field to `build_facts()` — facts are plain dicts
3. No changes needed elsewhere — the operator evaluation is generic

## Testing

```bash
# Run all tests
pytest

# With coverage
pytest --cov --cov-report=term-missing

# Single file
pytest tests/unit/test_rule_engine.py -v
```

Tests use SQLite in-memory (configured in `pytest.ini` + `tests/conftest.py`). Do not mock the database — use the real test DB.

## Pull request checklist

- [ ] Tests pass (`pytest`)
- [ ] Linter clean (`ruff check .`)
- [ ] No raw PII in logs
- [ ] New endpoints have role guards
- [ ] New admin writes have audit log entries
- [ ] `.env.example` updated if new env vars added
- [ ] `CHANGELOG.md` entry added (if significant change)

## Commit style

```
feat: add DPD logistics integrator
fix: prevent double-refund on Celery retry
docs: add rule engine field reference
```

Types: `feat`, `fix`, `refactor`, `docs`, `test`, `chore`

## Questions?

Open a GitHub issue or start a discussion. Tag it with the appropriate label (`integration`, `rule-engine`, `security`, `frontend`).
