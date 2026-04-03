# REVERSE-OS

**Open-source returns management system for eCommerce.**

REVERSE-OS handles the full lifecycle of a product return — from a customer requesting a return through a secure deep-link portal, through automated rule evaluation and warehouse inspection, to refund processing and KSeF correction invoice generation.

```
Customer portal  →  Rule engine  →  Warehouse app  →  Refund (Stripe / PayU)  →  KSeF export
```

MIT licensed. Built with FastAPI, PostgreSQL, Redis, Celery, Next.js.

---

## Table of Contents

- [Features](#features)
- [Architecture](#architecture)
- [Quick Start](#quick-start)
- [Configuration](#configuration)
- [Database](#database)
- [API Reference](#api-reference)
- [Rule Engine](#rule-engine)
- [Integrations](#integrations)
- [Frontend](#frontend)
- [Security](#security)
- [License Keys (Enterprise)](#license-keys-enterprise)
- [RBAC](#rbac)
- [KSeF Export](#ksef-export)
- [Contributing](#contributing)

---

## Features

**Core (MIT)**
- Secure customer return portal — one-time deep-link tokens, HttpOnly cookie sessions
- Automated rule engine — configurable conditions/actions with full audit trail
- State machine for return lifecycle with enforced valid transitions
- Warehouse inspection workflow
- Privacy-by-design — PII in a separate AES-256-GCM encrypted vault
- Idempotent operations throughout — safe to retry at every layer
- Immutable audit log and rule execution log

**Integrations included**
- eCommerce: Shopify, Magento 2, WooCommerce
- Logistics: InPost (ShipX API) — return label generation and tracking
- Payments: Stripe, PayU — async refund processing via Celery

**Enterprise (license key required)**
- Automated refunds
- KSeF FA(2) correction invoice export (JSON + XML) — Polish mandatory e-invoicing
- RBAC with role hierarchy
- Monthly return limit override (free tier: 100/month)

---

## Architecture

```
┌─────────────────────┐     ┌──────────────────────────────┐
│  Next.js (port 3000) │     │  FastAPI (port 8000)          │
│                      │     │                              │
│  Customer Portal     │────▶│  /api/v1/returns             │
│  Admin Panel         │────▶│  /api/v1/admin/*             │
│  BFF API routes      │     │  /api/v1/auth                │
└─────────────────────┘     │  /api/v1/webhooks            │
                             └──────────┬───────────────────┘
                                        │
              ┌─────────────────────────┼──────────────────────┐
              │                         │                      │
       ┌──────▼──────┐         ┌────────▼──────┐    ┌─────────▼──────┐
       │ PostgreSQL 16│         │  Redis 7       │    │ Celery Worker  │
       │              │         │  Sessions      │    │                │
       │  returns     │         │  Task broker   │    │  Refunds       │
       │  pii_vault   │         └───────────────┘    │  Tracking poll │
       │  audit_log   │                               │  KSeF sync     │
       └─────────────┘                               └───────────────┘
```

### Directory structure

```
reverse-os/
├── api/v1/endpoints/
│   ├── auth.py               # Token redemption, session management
│   ├── orders.py             # Order fetch (requires session)
│   ├── returns.py            # Return initiation, warehouse inspect
│   ├── webhooks.py           # InPost + Stripe webhook receivers
│   └── admin/
│       ├── auth.py           # Admin JWT login
│       ├── stats.py          # Dashboard KPIs
│       ├── returns.py        # Return list/detail/override
│       ├── rules.py          # Rule set CRUD
│       ├── financial.py      # Refund, store credit, order sync
│       ├── users.py          # User management
│       └── ksef.py           # KSeF export endpoints
├── core/
│   ├── config.py             # Pydantic Settings
│   ├── database/session.py   # Async SQLAlchemy engine
│   ├── models/               # ORM models
│   ├── security/
│   │   ├── pii.py            # AES-256-GCM encrypt/decrypt
│   │   ├── return_token.py   # One-time CSPRNG tokens
│   │   ├── session.py        # Redis session store
│   │   ├── jwt.py            # JWT creation/decoding
│   │   └── rbac.py           # Role-based access control
│   └── licensing/
│       ├── license.py        # License key validation
│       └── keygen.py         # Internal key generation tool
├── integrators/
│   ├── ecommerce/            # Shopify, Magento, WooCommerce
│   ├── logistics/            # InPost
│   └── payments/             # Stripe, PayU
├── modules/
│   ├── rule_engine/engine.py # Condition evaluator
│   └── returns/
│       ├── service.py        # Return initiation business logic
│       ├── financial.py      # Refund + store credit service
│       └── ksef_export.py    # FA(2) correction invoice builder
├── workers/
│   ├── celery_app.py         # Celery configuration + beat schedule
│   └── tasks.py              # Async tasks
├── migrations/
│   ├── 001_initial_schema.sql
│   └── 002_seed_rules.sql
└── frontend/                 # Next.js app (portal + admin)
```

---

## Quick Start

### Prerequisites

- Python 3.11+
- PostgreSQL 16
- Redis 7
- Node.js 20+ (frontend)

### Option A — Docker Compose (recommended)

```bash
git clone https://github.com/your-org/reverse-os
cd reverse-os
cp .env.example .env        # edit with your credentials
docker compose up
```

The API will be available at `http://localhost:8000`.  
Interactive docs: `http://localhost:8000/docs`

### Option B — Local development

**Backend:**

```bash
# Install dependencies
pip install poetry
poetry install

# Set up database
createdb reverseos
psql reverseos < migrations/001_initial_schema.sql
psql reverseos < migrations/002_seed_rules.sql

# Configure environment
cp .env.example .env        # edit DATABASE_URL, PII_ENCRYPTION_KEY, etc.

# Start API
uvicorn main:app --reload

# Start Celery worker (separate terminal)
celery -A workers.celery_app worker --loglevel=info

# Start Celery beat scheduler (separate terminal)
celery -A workers.celery_app beat --loglevel=info
```

**Frontend:**

```bash
cd frontend
npm install
npm run dev                 # http://localhost:3000
```

---

## Configuration

All configuration is via environment variables (or `.env` file).

### Required

| Variable | Description |
|----------|-------------|
| `DATABASE_URL` | PostgreSQL DSN — `postgresql+asyncpg://user:pass@host:5432/db` |
| `APP_SECRET_KEY` | Random secret for JWT signing — generate with `openssl rand -hex 32` |
| `PII_ENCRYPTION_KEY` | AES-256 key (base64) for PII vault — generate with `openssl rand -base64 32` |

### Optional

| Variable | Default | Description |
|----------|---------|-------------|
| `REDIS_URL` | `redis://localhost:6379/0` | Redis for sessions + Celery |
| `APP_ENV` | `development` | Set to `production` to disable `/docs` |
| `LICENSE_KEY` | — | Enterprise license key (`REVOS-ENT-...`) |
| `JWT_ACCESS_TOKEN_EXPIRE_MINUTES` | `60` | Admin token TTL |
| `COMPANY_NAME` | `REVERSE-OS Sp. z o.o.` | Used in KSeF invoices |
| `COMPANY_NIP` | `0000000000` | Used in KSeF invoices |
| `COMPANY_ADDRESS` | — | Used in KSeF invoices |
| `ERP_WEBHOOK_URL` | — | POST endpoint for KSeF correction payloads |

### eCommerce integrations

| Variable | Description |
|----------|-------------|
| `SHOPIFY_API_KEY` | Shopify API key |
| `SHOPIFY_API_SECRET` | Shopify API secret (HMAC verification) |
| `MAGENTO_BASE_URL` | Magento 2 base URL |
| `MAGENTO_ACCESS_TOKEN` | Magento 2 bearer token |

### Logistics

| Variable | Description |
|----------|-------------|
| `INPOST_API_TOKEN` | InPost ShipX API token |

### Payments

| Variable | Description |
|----------|-------------|
| `STRIPE_SECRET_KEY` | Stripe secret key |
| `STRIPE_WEBHOOK_SECRET` | Stripe webhook signing secret |
| `PAYU_CLIENT_ID` | PayU OAuth2 client ID |
| `PAYU_CLIENT_SECRET` | PayU OAuth2 client secret |

---

## Database

### Schema overview

```sql
pii_vault          -- AES-256-GCM encrypted PII (name, email, phone, address)
customers          -- Anonymized customer records (links to pii_vault)
orders             -- Order header + platform reference
order_items        -- Line items with unit_price_net, vat_rate
returns            -- Return lifecycle (state machine)
return_items       -- Individual items in a return request
rule_sets          -- Configurable rule definitions
rule_execution_log -- Immutable rule evaluation trace
audit_log          -- Immutable record of all actions
refunds            -- Refund records with idempotency_key
vouchers           -- Store credit voucher codes
users              -- Admin/warehouse/viewer accounts
return_tokens      -- One-time customer portal tokens
return_status_transitions -- Valid state transitions (reference table)
```

### Running migrations

```bash
# Apply schema
psql $DATABASE_URL < migrations/001_initial_schema.sql

# Seed default rule sets
psql $DATABASE_URL < migrations/002_seed_rules.sql
```

### Return state machine

```
draft
  └─▶ pending
        ├─▶ requires_inspection ─▶ approved ─▶ label_generated ─▶ in_transit ─▶ received
        │                        └─▶ keep_it ─▶ refund_initiated
        │         └─▶ partial_received ─▶ refund_initiated
        ├─▶ approved ─────────────────────────────▶ refund_initiated ─▶ refunded ─▶ closed
        ├─▶ rejected ─▶ closed                                       └─▶ store_credit_issued ─▶ closed
        └─▶ keep_it ─▶ refund_initiated
```

Illegal transitions raise `ValueError` at the ORM layer and are blocked at the DB layer via the `return_status_transitions` reference table.

---

## API Reference

Full interactive documentation is available at `http://localhost:8000/docs` (Swagger UI) or `http://localhost:8000/redoc`.

### Customer Portal flow

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/v1/orders/{id}` | Fetch order (requires `X-Session-Id` header from BFF) |
| `POST` | `/api/v1/returns/` | Initiate return (consumes session + token atomically) |
| `GET` | `/api/v1/returns/{rma_number}` | Get return status |

### Merchant API

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/v1/orders/token` | Generate one-time return portal deep-link |

### Admin API

All admin endpoints require `Authorization: Bearer <jwt>`.

| Method | Path | Role | Description |
|--------|------|------|-------------|
| `POST` | `/api/v1/admin/auth/login` | — | Get JWT |
| `GET` | `/api/v1/admin/stats/` | warehouse+ | Dashboard KPIs |
| `GET` | `/api/v1/admin/returns/` | warehouse+ | Paginated return list |
| `GET` | `/api/v1/admin/returns/{id}` | warehouse+ | Return detail with rule log + audit trail |
| `PATCH` | `/api/v1/admin/returns/{id}/status` | admin | Manual status override |
| `PATCH` | `/api/v1/admin/returns/{id}/notes` | warehouse+ | Update internal notes |
| `POST` | `/api/v1/admin/financial/{id}/refund` | admin | Initiate refund |
| `POST` | `/api/v1/admin/financial/{id}/store-credit` | admin | Issue store credit voucher |
| `POST` | `/api/v1/admin/financial/{id}/sync-order` | admin | Sync status to eCommerce platform |
| `GET` | `/api/v1/admin/rules/` | warehouse+ | List rule sets |
| `POST` | `/api/v1/admin/rules/` | admin | Create rule set |
| `PUT` | `/api/v1/admin/rules/{id}` | admin | Update rule set |
| `DELETE` | `/api/v1/admin/rules/{id}` | admin | Deactivate rule set |
| `GET` | `/api/v1/admin/users/` | admin | List users |
| `POST` | `/api/v1/admin/users/` | admin | Create user |
| `PATCH` | `/api/v1/admin/users/{id}` | admin | Update role / active status |
| `POST` | `/api/v1/admin/users/{id}/reset-password` | admin | Reset password |
| `GET` | `/api/v1/admin/ksef/queue` | admin | Returns awaiting KSeF correction invoice |
| `GET` | `/api/v1/admin/returns/{id}/ksef-export` | admin | Export FA(2) correction invoice (`?format=json\|xml`) |

### Webhooks

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/v1/webhooks/inpost` | InPost tracking updates (HMAC-verified) |
| `POST` | `/api/v1/webhooks/stripe` | Stripe payment events (signature-verified) |

---

## Rule Engine

Rules are evaluated in priority order (lowest number first). The first matching rule wins.

### Rule set structure

```json
{
  "name": "Low Value — Auto Approve",
  "priority": 10,
  "platform": null,
  "conditions": {
    "all": [
      { "field": "order_value", "operator": "lte", "value": 100 },
      { "field": "customer_return_count", "operator": "lte", "value": 3 }
    ]
  },
  "actions": [
    { "type": "approve_instant" }
  ]
}
```

### Available condition fields

| Field | Type | Description |
|-------|------|-------------|
| `order_value` | number | Total order gross value (PLN) |
| `item_value` | number | Return item gross value |
| `return_reason` | string | Customer-provided reason code |
| `customer_return_count` | number | Customer's historical return count |
| `days_since_order` | number | Age of the order in days |
| `platform` | string | eCommerce platform name |

### Available operators

`eq`, `neq`, `gt`, `gte`, `lt`, `lte`, `in`, `not_in`, `contains`

### Condition nesting

```json
{
  "any": [
    { "field": "return_reason", "operator": "eq", "value": "defective" },
    {
      "all": [
        { "field": "order_value", "operator": "lte", "value": 200 },
        { "field": "customer_return_count", "operator": "lte", "value": 2 }
      ]
    }
  ]
}
```

### Available action types

| Action | Description |
|--------|-------------|
| `approve_instant` | Auto-approve, skip warehouse |
| `require_inspection` | Route to warehouse queue |
| `reject_return` | Reject with reason |
| `keep_it` | Customer keeps the item, refund issued |
| `free_shipping_toggle` | Override shipping cost to 0 |
| `offer_store_credit_bonus` | Apply store credit multiplier |

---

## Integrations

### eCommerce — adding a new platform

Implement the `EcommerceIntegrator` ABC from `integrators/ecommerce/base.py`:

```python
from integrators.ecommerce.base import EcommerceIntegrator, RemoteOrder

class MyPlatformIntegrator(EcommerceIntegrator):
    platform = "myplatform"

    async def fetch_order(self, external_order_id: str) -> RemoteOrder:
        ...

    async def update_order_status(self, external_order_id: str, status: str) -> None:
        ...

    def verify_order_token(self, token: str, order_id: str) -> bool:
        ...
```

Register in `main.py`:

```python
from integrators.ecommerce.myplatform import MyPlatformIntegrator
ecommerce_registry.register(MyPlatformIntegrator())
```

### Logistics — adding a new courier

Implement `LogisticsIntegrator` from `integrators/logistics/base.py`:

```python
from integrators.logistics.base import LogisticsIntegrator, ShippingLabel, TrackingStatus

class DPDIntegrator(LogisticsIntegrator):
    provider = "dpd"

    async def create_return_label(self, ...) -> ShippingLabel:
        ...

    async def get_tracking_status(self, tracking_number: str) -> TrackingStatus:
        ...
```

### Payments — adding a new provider

Implement `PaymentIntegrator` from `integrators/payments/base.py`:

```python
from integrators.payments.base import PaymentIntegrator, RefundResult

class BlikIntegrator(PaymentIntegrator):
    provider = "blik"

    async def create_refund(self, ...) -> RefundResult:
        ...
```

---

## Frontend

### Customer portal (`/return`)

The customer portal is a 4-step React flow:

1. **Order verification** — auto-loaded from session (no token in URL)
2. **Item selection** — quantity, reason, condition, optional detail text
3. **Return method** — Paczkomat / Kurier / Poczta
4. **Confirmation** — RMA number, rule decision, voucher code / label link

### Deep-link token flow

```
Merchant backend
  │
  ├─▶ POST /api/v1/orders/token  →  returns { deep_link: "http://your-store/redeem?t=abc123" }
  │
Customer clicks link
  │
  └─▶ GET /redeem?t=abc123  (Next.js Route Handler)
        ├─▶ POST /api/v1/auth/redeem  →  validates token, creates Redis session
        ├─▶ Set-Cookie: rsid=...; HttpOnly; SameSite=Strict
        └─▶ Redirect: /return  (clean URL, no token)
              │
              └─▶ /api/orders  (Next.js BFF)  →  reads cookie server-side
                    └─▶ GET /api/v1/orders/{id}  (with X-Session-Id header)
```

The token never appears in the browser address bar after redemption.

### Admin panel (`/admin`)

- **Dashboard** — KPI cards (total, today, auto-approval rate), 30-day trend chart, status breakdown
- **Returns** — paginated table, status filter, detail view with rule log trace and audit trail, manual override, financial actions
- **Rules** — priority-ordered list, toggle active, JSON condition editor
- **Users** — user table, role selector, activate/deactivate, create user, reset password

---

## Security

### Three Golden Rules

1. **Idempotency** — every write operation has a `UNIQUE idempotency_key`. Safe to retry at any layer.
2. **State machine** — `Return.transition_to()` raises `ValueError` on illegal transitions. The `return_status_transitions` DB table is the reference.
3. **Immutable logs** — `rule_execution_log` and `audit_log` have a DB trigger that blocks `UPDATE` and `DELETE`.

### One-time tokens

Customer portal tokens are stored in the `return_tokens` table:

- Generated with `secrets.token_hex(32)` (256-bit CSPRNG)
- Single use — consumed atomically via `UPDATE ... WHERE used = false AND expires_at > NOW() RETURNING token`
- TTL: 24 hours
- Separate Redis session created on first use — token is exchanged for an HttpOnly cookie

### PII vault

All personally identifiable information is stored in a separate `pii_vault` table, encrypted at rest with AES-256-GCM. The main `customers` table holds only an opaque reference. `anonymize_payload()` is called before anything reaches the audit log.

### Admin authentication

JWT (HS256), signed with `APP_SECRET_KEY`. Tokens expire after `JWT_ACCESS_TOKEN_EXPIRE_MINUTES` (default: 60 minutes). Stored in `localStorage` on the frontend — admin panel is not accessible to customers.

---

## License Keys (Enterprise)

The free tier allows 100 returns per month. Enterprise and Starter licenses remove this limit and unlock gated features (`auto_refund`, `ksef`, `rbac`, `multi_store`).

### Key format

```
REVOS-{TIER}-{base64url(json_payload)}-{HMAC-SHA256[:16].upper()}
```

Example:
```
REVOS-ENT-eyJjaWQiOiJhY21lIiwibWF4X3JldCI6MCwiZXhwIjoxODA3MjM3NjAwLCJmZWF0dXJlcyI6WyJhdXRvX3JlZnVuZCIsImtzZWYiLCJyYmFjIiwibXVsdGlfc3RvcmUiXX0-A3B2C4D5E6F7A8B9
```

### Generating a key (internal tool)

```bash
REVERSEOS_LICENSE_MASTER=your-secret python -m core.licensing.keygen \
  --cid customer-name \
  --tier ENT \
  --max 0 \
  --exp 2027-01-01 \
  --features auto_refund ksef rbac multi_store
```

The `keygen.py` module must never be shipped in the product binary.

### Validating in code

```python
from core.licensing.license import LicenseManager

lic = LicenseManager.load(settings.LICENSE_KEY)
lic.require_feature("ksef")          # raises HTTP 402 if not licensed
LicenseManager.check_return_limit(n) # raises HTTP 402 if monthly limit exceeded
```

---

## RBAC

| Role | Level | Permissions |
|------|-------|-------------|
| `admin` | 4 | Full access — users, rules, status overrides, financial, KSeF |
| `warehouse` | 3 | View returns, submit inspection, update notes |
| `viewer` | 2 | Read-only: returns, stats, dashboard |
| `api_key` | 1 | Machine-to-machine: submit returns, receive webhooks |

### Usage in endpoints

```python
from core.security.rbac import require_role, require_min_role, IsAdmin, IsStaff

# Exact role match
actor: dict = Depends(require_role("admin"))
actor: dict = Depends(require_role("admin", "warehouse"))

# Minimum level (inclusive upward)
actor: dict = Depends(require_min_role("warehouse"))  # allows admin + warehouse

# Convenience aliases
dependencies=[IsAdmin]
dependencies=[IsStaff]     # warehouse+
dependencies=[IsAnyStaff]  # viewer+
```

---

## KSeF Export

REVERSE-OS generates FA(2) correction invoices (Faktura korygująca) per §106j ustawy o VAT for finalized returns.

### Export flow

```
Return finalized (status: refunded)
  │
  ├─▶ GET /admin/returns/{id}/ksef-export?format=json   → FA(2) JSON dict
  └─▶ GET /admin/returns/{id}/ksef-export?format=xml    → FA(2) XML file (KSeF-compatible)
```

Automated sync (if `ERP_WEBHOOK_URL` is configured):

```
Celery beat (every 1 hour)
  └─▶ sync_ksef_references task
        ├─▶ finds refunded returns with no ksef_reference
        ├─▶ builds FA(2) payload
        ├─▶ POST to ERP_WEBHOOK_URL
        └─▶ on 200: stores ksef_reference_number in returns table
            on 202: retries on next beat cycle
```

### VAT rate mapping

| Rate | KSeF code |
|------|-----------|
| 23% | A |
| 8% | B |
| 5% | C |
| 0% (ZW) | E |

---

## Contributing

Pull requests are welcome. Please:

1. Fork the repo and create a feature branch
2. Run the test suite: `pytest --cov`
3. Lint: `ruff check . && ruff format .`
4. Ensure new endpoints have role guards and audit log entries
5. Never log raw PII — use `anonymize_payload()` from `core/security/pii.py`
6. Keep the three golden rules (idempotency, state machine, immutable logs)

### Running tests

```bash
poetry run pytest                    # full suite
poetry run pytest tests/unit/        # unit only
poetry run pytest --cov --cov-report=html
```

### Code style

```bash
ruff check .          # lint
ruff format .         # format
mypy .                # type check
```

---

## License

MIT — see [LICENSE](LICENSE).
