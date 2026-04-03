"""
Rule Engine: evaluates a return against all active rule sets.
Implements the json-rules-engine condition schema locally (no external AI/cloud).
Golden Rule #3: every execution is logged to rule_execution_log.
"""
from __future__ import annotations

import operator
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

import structlog

log = structlog.get_logger(__name__)

OPERATORS = {
    "equal":                  operator.eq,
    "notEqual":               operator.ne,
    "lessThan":               operator.lt,
    "lessThanInclusive":      operator.le,
    "greaterThan":            operator.gt,
    "greaterThanInclusive":   operator.ge,
}


@dataclass
class RuleEngineResult:
    matched_rule_id: str | None
    matched_rule_name: str | None
    decision: str                   # 'auto_approved', 'keep_it', 'require_inspection', 'rejected', 'no_match'
    actions: list[dict]
    facts_snapshot: dict
    log_entries: list[dict]         # Per-rule evaluation trace


class RuleEngine:
    async def evaluate(
        self,
        db: AsyncSession,
        return_id: str,
        facts: dict[str, Any],
    ) -> RuleEngineResult:
        """
        Evaluate all active rule sets against `facts`.
        Rules are sorted by priority (lower = evaluated first).
        First matching rule wins.
        """
        from core.models.rule_set_model import RuleSet  # avoid circular imports

        result = await db.execute(
            select(RuleSet)
            .where(RuleSet.is_active == True)  # noqa: E712
            .order_by(RuleSet.priority.asc())
        )
        rule_sets = result.scalars().all()

        log_entries = []
        for rule_set in rule_sets:
            matched = self._evaluate_conditions(rule_set.conditions, facts)
            log_entries.append({
                "rule_id": str(rule_set.id),
                "rule_name": rule_set.name,
                "matched": matched,
                "conditions": rule_set.conditions,
            })

            # Write to immutable rule_execution_log
            await self._write_log(db, return_id, rule_set, facts, matched)

            if matched:
                decision = self._derive_decision(rule_set.actions)
                log.info(
                    "rule_engine.match",
                    return_id=return_id,
                    rule=rule_set.name,
                    decision=decision,
                )
                return RuleEngineResult(
                    matched_rule_id=str(rule_set.id),
                    matched_rule_name=rule_set.name,
                    decision=decision,
                    actions=rule_set.actions,
                    facts_snapshot=facts,
                    log_entries=log_entries,
                )

        log.info("rule_engine.no_match", return_id=return_id)
        return RuleEngineResult(
            matched_rule_id=None,
            matched_rule_name=None,
            decision="no_match",
            actions=[],
            facts_snapshot=facts,
            log_entries=log_entries,
        )

    def _evaluate_conditions(self, conditions: dict, facts: dict) -> bool:
        """Recursive evaluation of {"all": [...]} / {"any": [...]} trees."""
        if "all" in conditions:
            return all(self._evaluate_condition(c, facts) for c in conditions["all"])
        if "any" in conditions:
            return any(self._evaluate_condition(c, facts) for c in conditions["any"])
        return False

    def _evaluate_condition(self, condition: dict, facts: dict) -> bool:
        fact_name = condition["fact"]
        op_name = condition["operator"]
        expected = condition["value"]
        actual = facts.get(fact_name)

        if actual is None:
            return False

        op_fn = OPERATORS.get(op_name)
        if op_fn is None:
            log.warning("rule_engine.unknown_operator", operator=op_name)
            return False

        # Coerce for comparison
        if isinstance(expected, (int, float)) and isinstance(actual, Decimal):
            actual = float(actual)

        try:
            return op_fn(actual, expected)
        except TypeError:
            return False

    def _derive_decision(self, actions: list[dict]) -> str:
        action_types = {a["type"] for a in actions}
        if "keep_it" in action_types:
            return "keep_it"
        if "approve_instant" in action_types:
            return "auto_approved"
        if "require_inspection" in action_types:
            return "require_inspection"
        if "reject_return" in action_types:
            return "rejected"
        return "auto_approved"

    async def _write_log(
        self,
        db: AsyncSession,
        return_id: str,
        rule_set: Any,
        facts: dict,
        matched: bool,
    ) -> None:
        from core.models.rule_execution_log_model import RuleExecutionLog
        db.add(RuleExecutionLog(
            return_id=return_id,
            rule_set_id=str(rule_set.id),
            rule_set_name=rule_set.name,
            facts_snapshot=facts,
            conditions_snapshot=rule_set.conditions,
            matched=matched,
            actions_taken=rule_set.actions if matched else None,
        ))


def build_facts(return_obj: Any, order: Any, customer: Any) -> dict[str, Any]:
    """
    Extract rule-engine facts from domain objects.
    No PII here — only numerical/categorical values.
    """
    max_item_price = max(
        (float(item.unit_price_gross) for item in order.items),
        default=0.0,
    )
    days_since = (
        datetime.now(timezone.utc) - order.ordered_at
    ).days if order.ordered_at else 999

    reasons = [ri.reason for ri in return_obj.items]

    return {
        "item_price_max": max_item_price,
        "total_order_value": float(order.total_gross),
        "customer_segment": customer.segment,
        "customer_return_rate": float(customer.return_rate or 0),
        "days_since_purchase": days_since,
        "return_reason": reasons[0] if len(reasons) == 1 else reasons,
        "items_count": len(return_obj.items),
    }


rule_engine = RuleEngine()
