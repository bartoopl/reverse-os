-- ============================================================
-- REVERSE-OS: Seed Data - Default Rule Sets
-- ============================================================

INSERT INTO rule_sets (name, description, priority, conditions, actions) VALUES
(
    'Low Value Trusted Customer - Auto Approve',
    'Items under 50 PLN from trusted customers are auto-approved with free shipping.',
    10,
    '{
        "all": [
            {"fact": "item_price_max", "operator": "lessThan", "value": 50},
            {"fact": "customer_segment", "operator": "equal", "value": "trusted"},
            {"fact": "days_since_purchase", "operator": "lessThanInclusive", "value": 30}
        ]
    }',
    '[
        {"type": "approve_instant"},
        {"type": "free_shipping_toggle", "params": {"enabled": true}},
        {"type": "offer_store_credit_bonus", "params": {"bonus_pct": 10}}
    ]'
),
(
    'Low Value Keep-It - Refund Without Return',
    'Items under 25 PLN: refund without requiring physical return (cheaper than processing).',
    5,
    '{
        "all": [
            {"fact": "item_price_max", "operator": "lessThan", "value": 25},
            {"fact": "return_reason", "operator": "notEqual", "value": "defective"},
            {"fact": "days_since_purchase", "operator": "lessThanInclusive", "value": 14}
        ]
    }',
    '[
        {"type": "keep_it"},
        {"type": "approve_instant"}
    ]'
),
(
    'Flagged Customer - Require Inspection',
    'Customers flagged for abuse always require manual warehouse inspection.',
    1,
    '{
        "any": [
            {"fact": "customer_segment", "operator": "equal", "value": "flagged"},
            {"fact": "customer_return_rate", "operator": "greaterThan", "value": 0.5}
        ]
    }',
    '[
        {"type": "require_inspection"},
        {"type": "free_shipping_toggle", "params": {"enabled": false}}
    ]'
),
(
    'High Value Order - Require Inspection',
    'Returns on orders over 1000 PLN always require manual inspection.',
    20,
    '{
        "all": [
            {"fact": "total_order_value", "operator": "greaterThan", "value": 1000}
        ]
    }',
    '[
        {"type": "require_inspection"}
    ]'
),
(
    'Default Fallback - Standard Approval',
    'Default rule: approve all returns within 30 days that pass no other rules.',
    999,
    '{
        "all": [
            {"fact": "days_since_purchase", "operator": "lessThanInclusive", "value": 30}
        ]
    }',
    '[
        {"type": "approve_instant"}
    ]'
);
