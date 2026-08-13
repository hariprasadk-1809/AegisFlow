"""
AegisFlow — Policy Engine.

This is the "LLM != Authority" layer. Every action an agent wants to take
gets looked up here BEFORE it is allowed anywhere near the Tool Gateway.

For the hackathon MVP this is intentionally a simple rules table, not a
full RBAC system. That's a documented, honest scope decision — see the
Idea/Approach slide.
"""

# risk tier -> what happens
#   low    -> auto-approved, runs immediately
#   medium -> would need human approval (demo: auto-approved for flow, but logged as medium)
#   high   -> blocked outright, never reaches the Tool Gateway

POLICY_RULES = {
    "send_reminder_email": "low",
    "waive_late_fee": "high",
    "update_invoice_status": "medium",
}

DECISION_BY_TIER = {
    "low": "auto_approved",
    "medium": "needs_approval",
    "high": "blocked",
}


def evaluate(action_type: str) -> dict:
    """
    Returns the policy decision for a given action type.
    Unknown action types default to 'high' risk / blocked — fail closed,
    not fail open. This is a deliberate safety default.
    """
    risk_tier = POLICY_RULES.get(action_type, "high")
    decision = DECISION_BY_TIER[risk_tier]
    return {
        "action_type": action_type,
        "risk_tier": risk_tier,
        "decision": decision,
    }
