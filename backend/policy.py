"""
AegisFlow — Policy Engine.

This is the "LLM != Authority" layer. Every action an agent wants to take
gets looked up here BEFORE it is allowed anywhere near the Tool Gateway.

For the hackathon MVP this is intentionally a simple rules table, not a
full RBAC system. That's a documented, honest scope decision — see the
Idea/Approach slide.
"""

# Each rule: risk tier + a short human-readable reason, so the trace can
# show WHY a decision was made, not just what the decision was.
POLICY_RULES = {
    "send_reminder_email": {
        "risk_tier": "low",
        "rule_id": "R1",
        "reason": "Reversible, no financial impact — auto-approved by default.",
    },
    "update_invoice_status": {
        "risk_tier": "medium",
        "rule_id": "R2",
        "reason": "Changes system-of-record state — requires human approval before executing.",
    },
    "waive_late_fee": {
        "risk_tier": "high",
        "rule_id": "R3",
        "reason": "Direct financial impact, hard to reverse — blocked outright, never reaches the Tool Gateway.",
    },
}

DEFAULT_RULE = {
    "risk_tier": "high",
    "rule_id": "R0",
    "reason": "Unrecognized action type — fails closed (blocked) by default, not fail-open.",
}

DECISION_BY_TIER = {
    "low": "auto_approved",
    "medium": "needs_approval",
    "high": "blocked",
}


def evaluate(action_type: str) -> dict:
    """
    Returns the policy decision for a given action type, including which
    rule fired and why — so the UI can show more than just a verdict.
    Unknown action types default to 'high' risk / blocked — fail closed,
    not fail open. This is a deliberate safety default.
    """
    rule = POLICY_RULES.get(action_type, DEFAULT_RULE)
    decision = DECISION_BY_TIER[rule["risk_tier"]]
    return {
        "action_type": action_type,
        "risk_tier": rule["risk_tier"],
        "decision": decision,
        "rule_id": rule["rule_id"],
        "reason": rule["reason"],
    }
