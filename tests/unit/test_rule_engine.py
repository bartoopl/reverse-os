"""Rule engine unit tests — Golden Rule #3 (logging) tested via integration."""
import pytest
from modules.rule_engine.engine import RuleEngine


engine = RuleEngine()


@pytest.mark.parametrize("facts,expected", [
    ({"item_price_max": 49, "customer_segment": "trusted", "days_since_purchase": 20}, True),
    ({"item_price_max": 50, "customer_segment": "trusted", "days_since_purchase": 20}, False),  # not < 50
    ({"item_price_max": 49, "customer_segment": "standard", "days_since_purchase": 20}, False),
    ({"item_price_max": 49, "customer_segment": "trusted", "days_since_purchase": 31}, False),
])
def test_low_value_trusted_condition(facts, expected):
    conditions = {
        "all": [
            {"fact": "item_price_max", "operator": "lessThan", "value": 50},
            {"fact": "customer_segment", "operator": "equal", "value": "trusted"},
            {"fact": "days_since_purchase", "operator": "lessThanInclusive", "value": 30},
        ]
    }
    assert engine._evaluate_conditions(conditions, facts) == expected


def test_any_condition():
    conditions = {
        "any": [
            {"fact": "customer_segment", "operator": "equal", "value": "flagged"},
            {"fact": "customer_return_rate", "operator": "greaterThan", "value": 0.5},
        ]
    }
    assert engine._evaluate_conditions(conditions, {"customer_segment": "flagged", "customer_return_rate": 0.1})
    assert engine._evaluate_conditions(conditions, {"customer_segment": "standard", "customer_return_rate": 0.6})
    assert not engine._evaluate_conditions(conditions, {"customer_segment": "standard", "customer_return_rate": 0.3})


def test_missing_fact_returns_false():
    conditions = {"all": [{"fact": "nonexistent_fact", "operator": "equal", "value": "x"}]}
    assert engine._evaluate_conditions(conditions, {}) == False


def test_derive_decision_keep_it():
    actions = [{"type": "keep_it"}, {"type": "approve_instant"}]
    assert engine._derive_decision(actions) == "keep_it"


def test_derive_decision_inspection():
    assert engine._derive_decision([{"type": "require_inspection"}]) == "require_inspection"
