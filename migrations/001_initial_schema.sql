-- ============================================================
-- REVERSE-OS: Initial Database Schema
-- Privacy-First, Event-Driven Returns Management System
-- ============================================================

-- ============================================================
-- EXTENSIONS
-- ============================================================
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ============================================================
-- PII VAULT (Separate encrypted table - Privacy by Design)
-- Never join this to analytics tables directly.
-- Access only via API layer with audit logging.
-- ============================================================
CREATE TABLE pii_vault (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email_encrypted BYTEA NOT NULL,         -- pgcrypto encrypted
    name_encrypted  BYTEA,
    phone_encrypted BYTEA,
    address_encrypted BYTEA,               -- JSON blob, encrypted
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Lookup index on encrypted email hash (for dedup without decryption)
CREATE UNIQUE INDEX idx_pii_vault_email_hash
    ON pii_vault (digest(email_encrypted, 'sha256'));

-- ============================================================
-- CUSTOMERS (No PII here - only references)
-- ============================================================
CREATE TABLE customers (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    pii_id          UUID NOT NULL REFERENCES pii_vault(id),
    external_id     VARCHAR(255),           -- Shopify/Magento customer ID
    platform        VARCHAR(50),            -- 'shopify', 'magento', 'woocommerce'
    segment         VARCHAR(50) DEFAULT 'standard',  -- 'trusted', 'vip', 'standard', 'flagged'
    total_orders    INTEGER DEFAULT 0,
    total_returns   INTEGER DEFAULT 0,
    return_rate     NUMERIC(5,4) DEFAULT 0, -- 0.0000 - 1.0000
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (external_id, platform)
);

CREATE INDEX idx_customers_pii_id ON customers(pii_id);
CREATE INDEX idx_customers_external ON customers(external_id, platform);

-- ============================================================
-- ORDERS (Fetched from eCommerce, cached locally)
-- ============================================================
CREATE TABLE orders (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    external_id     VARCHAR(255) NOT NULL,  -- Shopify order ID / Magento increment_id
    platform        VARCHAR(50) NOT NULL,
    customer_id     UUID NOT NULL REFERENCES customers(id),
    order_number    VARCHAR(100),           -- Human-readable: #1001
    ordered_at      TIMESTAMPTZ NOT NULL,
    currency        CHAR(3) NOT NULL DEFAULT 'PLN',
    total_gross     NUMERIC(12,2) NOT NULL,
    total_net       NUMERIC(12,2),
    total_vat       NUMERIC(12,2),
    invoice_ref     VARCHAR(255),           -- For KSeF/ERP bridge
    platform_data   JSONB,                 -- Raw platform response (no PII)
    synced_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (external_id, platform)
);

CREATE INDEX idx_orders_customer ON orders(customer_id);
CREATE INDEX idx_orders_external ON orders(external_id, platform);
CREATE INDEX idx_orders_ordered_at ON orders(ordered_at DESC);

-- ============================================================
-- ORDER ITEMS
-- ============================================================
CREATE TABLE order_items (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    order_id        UUID NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
    external_id     VARCHAR(255),           -- Platform's line item ID
    sku             VARCHAR(255) NOT NULL,
    name            VARCHAR(500) NOT NULL,
    variant         VARCHAR(255),
    quantity        INTEGER NOT NULL CHECK (quantity > 0),
    unit_price_gross NUMERIC(12,2) NOT NULL,
    unit_price_net  NUMERIC(12,2),
    vat_rate        NUMERIC(5,4),
    image_url       VARCHAR(1024),
    product_data    JSONB                   -- Extended platform metadata
);

CREATE INDEX idx_order_items_order ON order_items(order_id);
CREATE INDEX idx_order_items_sku ON order_items(sku);

-- ============================================================
-- RETURNS (State Machine - Core Entity)
-- ============================================================
CREATE TYPE return_status AS ENUM (
    'draft',                -- Customer started form, not submitted
    'pending',              -- Submitted, awaiting rule engine evaluation
    'requires_inspection',  -- Rule engine flagged for manual review
    'approved',             -- Auto or manually approved
    'rejected',             -- Rejected (with reason)
    'label_generated',      -- Shipping label sent to customer
    'in_transit',           -- Courier picked up / label scanned
    'received',             -- Warehouse confirmed receipt
    'partial_received',     -- Some items received, some missing/damaged
    'refund_initiated',     -- Payment provider call made
    'refunded',             -- Refund confirmed by payment provider
    'store_credit_issued',  -- Voucher/credit issued instead of refund
    'keep_it',              -- Low-value: refund without physical return
    'closed',               -- Terminal state
    'cancelled'             -- Customer cancelled before shipping
);

CREATE TYPE return_method AS ENUM (
    'courier_pickup',
    'drop_off_point',       -- InPost parcel locker
    'drop_off_post',
    'keep_it'
);

CREATE TABLE returns (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    rma_number      VARCHAR(50) UNIQUE NOT NULL,  -- Human-readable: RMA-2024-00001
    order_id        UUID NOT NULL REFERENCES orders(id),
    customer_id     UUID NOT NULL REFERENCES customers(id),
    status          return_status NOT NULL DEFAULT 'draft',
    return_method   return_method,
    -- Financial
    requested_refund_amount NUMERIC(12,2),
    approved_refund_amount  NUMERIC(12,2),
    refund_type     VARCHAR(50),            -- 'original_payment', 'store_credit', 'bank_transfer'
    -- Logistics
    label_url       VARCHAR(1024),
    tracking_number VARCHAR(255),
    logistics_provider VARCHAR(50),         -- 'inpost', 'dhl', 'dpd'
    logistics_data  JSONB,                 -- Courier API response
    -- Rule engine outcome
    rule_set_id     UUID,                  -- Which rule set evaluated this
    rule_decision   VARCHAR(50),           -- 'auto_approved', 'manual_required', 'rejected'
    rule_log        JSONB,                 -- WHY was this decision made (Golden Rule #3)
    -- KSeF / ERP
    ksef_reference  VARCHAR(255),          -- Populated after ERP processes correction
    erp_sync_at     TIMESTAMPTZ,
    -- Metadata
    customer_notes  TEXT,
    internal_notes  TEXT,
    submitted_at    TIMESTAMPTZ,
    resolved_at     TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    -- Idempotency (Golden Rule #1)
    idempotency_key VARCHAR(255) UNIQUE,
    -- State machine guard (Golden Rule #2) - enforced at app layer too
    CONSTRAINT no_refund_regression CHECK (
        NOT (status = 'refunded' AND status != 'closed')
    )
);

CREATE INDEX idx_returns_order ON returns(order_id);
CREATE INDEX idx_returns_customer ON returns(customer_id);
CREATE INDEX idx_returns_status ON returns(status);
CREATE INDEX idx_returns_rma ON returns(rma_number);
CREATE INDEX idx_returns_submitted ON returns(submitted_at DESC);

-- Auto-generate RMA number
CREATE SEQUENCE rma_seq START 1;
CREATE OR REPLACE FUNCTION generate_rma_number()
RETURNS TRIGGER AS $$
BEGIN
    NEW.rma_number := 'RMA-' || TO_CHAR(NOW(), 'YYYY') || '-' || LPAD(NEXTVAL('rma_seq')::TEXT, 5, '0');
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_returns_rma
    BEFORE INSERT ON returns
    FOR EACH ROW
    WHEN (NEW.rma_number IS NULL OR NEW.rma_number = '')
    EXECUTE FUNCTION generate_rma_number();

-- Auto-update updated_at
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_returns_updated_at
    BEFORE UPDATE ON returns
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

-- ============================================================
-- RETURN ITEMS (Line items being returned)
-- ============================================================
CREATE TYPE return_item_reason AS ENUM (
    'damaged_in_transit',
    'wrong_item_sent',
    'not_as_described',
    'changed_mind',
    'defective',
    'size_fit_issue',
    'quality_issue',
    'duplicate_order',
    'arrived_late',
    'other'
);

CREATE TYPE return_item_condition AS ENUM (
    'unopened',
    'opened_unused',
    'used_good',
    'used_damaged',
    'defective'
);

CREATE TYPE warehouse_decision AS ENUM (
    'accept',
    'reject',
    'partial_accept'
);

CREATE TABLE return_items (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    return_id           UUID NOT NULL REFERENCES returns(id) ON DELETE CASCADE,
    order_item_id       UUID NOT NULL REFERENCES order_items(id),
    quantity_requested  INTEGER NOT NULL CHECK (quantity_requested > 0),
    quantity_accepted   INTEGER,            -- Set by warehouse inspection
    reason              return_item_reason NOT NULL,
    reason_detail       TEXT,               -- Free text elaboration
    customer_condition  return_item_condition,
    -- Warehouse inspection result
    warehouse_decision  warehouse_decision,
    warehouse_condition return_item_condition,
    warehouse_notes     TEXT,
    inspection_photo_urls JSONB,            -- Array of S3/CDN URLs
    inspected_at        TIMESTAMPTZ,
    inspected_by        UUID,               -- References users table
    -- Financial
    refund_amount       NUMERIC(12,2),      -- Approved per-item refund
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_return_items_return ON return_items(return_id);
CREATE INDEX idx_return_items_order_item ON return_items(order_item_id);

-- ============================================================
-- RULE SETS (JSON-based Rule Engine - Enterprise)
-- ============================================================
CREATE TABLE rule_sets (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name        VARCHAR(255) NOT NULL,
    description TEXT,
    priority    INTEGER NOT NULL DEFAULT 100,  -- Lower = higher priority
    is_active   BOOLEAN NOT NULL DEFAULT true,
    platform    VARCHAR(50),                   -- NULL = applies to all
    -- The rule tree (json-rules-engine compatible schema)
    conditions  JSONB NOT NULL,               -- {"all": [...]} or {"any": [...]}
    actions     JSONB NOT NULL,               -- [{"type": "approve_instant", ...}]
    -- Versioning
    version     INTEGER NOT NULL DEFAULT 1,
    created_by  UUID,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_rule_sets_priority ON rule_sets(priority) WHERE is_active = true;

-- Example rule set (seeded below in a separate file)
COMMENT ON COLUMN rule_sets.conditions IS
'JSON Rules Engine format. Example:
{
  "all": [
    {"fact": "item_price", "operator": "lessThan", "value": 50},
    {"fact": "customer_segment", "operator": "equal", "value": "trusted"},
    {"fact": "days_since_purchase", "operator": "lessThanInclusive", "value": 30}
  ]
}';

COMMENT ON COLUMN rule_sets.actions IS
'Array of actions to execute. Example:
[
  {"type": "approve_instant", "params": {}},
  {"type": "free_shipping_toggle", "params": {"enabled": true}}
]';

-- ============================================================
-- RULE EXECUTION LOG (Immutable - Golden Rule #3)
-- ============================================================
CREATE TABLE rule_execution_log (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    return_id       UUID NOT NULL REFERENCES returns(id),
    rule_set_id     UUID REFERENCES rule_sets(id),
    rule_set_name   VARCHAR(255),           -- Denormalized for immutability
    facts_snapshot  JSONB NOT NULL,         -- Exact facts at time of evaluation
    conditions_snapshot JSONB NOT NULL,     -- Exact rule at time of evaluation
    matched         BOOLEAN NOT NULL,
    actions_taken   JSONB,
    executed_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
    -- No update trigger - this table is append-only
);

CREATE INDEX idx_rule_log_return ON rule_execution_log(return_id);
CREATE INDEX idx_rule_log_executed ON rule_execution_log(executed_at DESC);

-- Prevent updates/deletes (immutability)
CREATE OR REPLACE FUNCTION deny_rule_log_mutation()
RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION 'rule_execution_log is immutable';
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_rule_log_no_update
    BEFORE UPDATE ON rule_execution_log
    FOR EACH ROW EXECUTE FUNCTION deny_rule_log_mutation();

CREATE TRIGGER trg_rule_log_no_delete
    BEFORE DELETE ON rule_execution_log
    FOR EACH ROW EXECUTE FUNCTION deny_rule_log_mutation();

-- ============================================================
-- AUDIT LOG (Immutable - every refund/approval action)
-- ============================================================
CREATE TABLE audit_log (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    entity_type VARCHAR(50) NOT NULL,       -- 'return', 'refund', 'rule_set'
    entity_id   UUID NOT NULL,
    action      VARCHAR(100) NOT NULL,      -- 'status_changed', 'refund_approved'
    actor_id    UUID,                       -- User or system (NULL = system/automation)
    actor_type  VARCHAR(50),                -- 'user', 'system', 'webhook'
    old_value   JSONB,
    new_value   JSONB,
    ip_address  INET,
    user_agent  TEXT,
    -- Anonymized context (no PII)
    meta        JSONB,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_audit_entity ON audit_log(entity_type, entity_id);
CREATE INDEX idx_audit_created ON audit_log(created_at DESC);
CREATE INDEX idx_audit_actor ON audit_log(actor_id);

-- Immutability
CREATE TRIGGER trg_audit_no_update
    BEFORE UPDATE ON audit_log
    FOR EACH ROW EXECUTE FUNCTION deny_rule_log_mutation();

CREATE TRIGGER trg_audit_no_delete
    BEFORE DELETE ON audit_log
    FOR EACH ROW EXECUTE FUNCTION deny_rule_log_mutation();

-- ============================================================
-- REFUNDS (Payment processor transactions)
-- ============================================================
CREATE TYPE refund_status AS ENUM (
    'pending',
    'processing',
    'succeeded',
    'failed',
    'cancelled'
);

CREATE TABLE refunds (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    return_id           UUID NOT NULL REFERENCES returns(id),
    idempotency_key     VARCHAR(255) UNIQUE NOT NULL,  -- Golden Rule #1: no double refunds
    provider            VARCHAR(50) NOT NULL,          -- 'stripe', 'payu', 'adyen'
    provider_refund_id  VARCHAR(255),                  -- External ID from payment provider
    amount              NUMERIC(12,2) NOT NULL,
    currency            CHAR(3) NOT NULL DEFAULT 'PLN',
    status              refund_status NOT NULL DEFAULT 'pending',
    provider_response   JSONB,
    failure_reason      TEXT,
    initiated_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at        TIMESTAMPTZ,
    created_by          UUID
);

CREATE INDEX idx_refunds_return ON refunds(return_id);
CREATE INDEX idx_refunds_provider_id ON refunds(provider_refund_id);
CREATE UNIQUE INDEX idx_refunds_idempotency ON refunds(idempotency_key);

-- ============================================================
-- USERS (Internal: Warehouse staff, Admins)
-- ============================================================
CREATE TYPE user_role AS ENUM (
    'admin',
    'warehouse',
    'viewer',
    'api_key'
);

CREATE TABLE users (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email           VARCHAR(255) UNIQUE NOT NULL,
    name            VARCHAR(255),
    role            user_role NOT NULL DEFAULT 'viewer',
    password_hash   VARCHAR(255),
    api_key_hash    VARCHAR(255),
    is_active       BOOLEAN NOT NULL DEFAULT true,
    last_login_at   TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ============================================================
-- RETURN STATUS TRANSITIONS (State Machine enforcement)
-- ============================================================
CREATE TABLE return_status_transitions (
    from_status return_status NOT NULL,
    to_status   return_status NOT NULL,
    PRIMARY KEY (from_status, to_status)
);

INSERT INTO return_status_transitions (from_status, to_status) VALUES
    ('draft',               'pending'),
    ('draft',               'cancelled'),
    ('pending',             'requires_inspection'),
    ('pending',             'approved'),
    ('pending',             'rejected'),
    ('pending',             'keep_it'),
    ('requires_inspection', 'approved'),
    ('requires_inspection', 'rejected'),
    ('requires_inspection', 'partial_received'),
    ('approved',            'label_generated'),
    ('approved',            'keep_it'),
    ('label_generated',     'in_transit'),
    ('label_generated',     'cancelled'),
    ('in_transit',          'received'),
    ('in_transit',          'partial_received'),
    ('received',            'refund_initiated'),
    ('received',            'store_credit_issued'),
    ('partial_received',    'refund_initiated'),
    ('partial_received',    'store_credit_issued'),
    ('keep_it',             'refund_initiated'),
    ('refund_initiated',    'refunded'),
    ('refund_initiated',    'store_credit_issued'),
    ('refunded',            'closed'),
    ('store_credit_issued', 'closed'),
    ('rejected',            'closed'),
    ('cancelled',           'closed');
