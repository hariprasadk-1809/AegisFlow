"""
AegisFlow — Tool Gateway.

This is the ONLY code path allowed to touch real systems (here: the
invoices table, standing in for email/DB in the demo). The Planner
never calls these functions directly — only the orchestrator does,
and only after the Policy Engine has approved the action.

One action ("send_reminder_email" on a specific invoice ID) is wired
to LIE about its own outcome, on purpose — this is what the
Verification Engine below is supposed to catch.
"""
from backend.db import get_conn

# Invoice ID that will "claim success" without actually updating the DB.
# This simulates a real failure mode: the tool call returns 200 OK /
# the agent reports success, but nothing actually changed downstream.
SIMULATED_LIE_INVOICE_ID = 2


def send_reminder_email(invoice_id: int) -> dict:
    conn = get_conn()
    row = conn.execute("SELECT * FROM invoices WHERE id = ?", (invoice_id,)).fetchone()
    if not row:
        conn.close()
        return {"claimed_success": False, "detail": "invoice not found"}

    if invoice_id == SIMULATED_LIE_INVOICE_ID:
        # Simulate a flaky email API / silent failure: we tell the caller
        # it worked, but we do NOT write reminder_sent = 1 to the DB.
        conn.close()
        return {
            "claimed_success": True,
            "detail": f"Reminder email sent to {row['customer_name']} (simulated failure — DB not actually updated)",
        }

    conn.execute("UPDATE invoices SET reminder_sent = 1 WHERE id = ?", (invoice_id,))
    conn.commit()
    conn.close()
    return {
        "claimed_success": True,
        "detail": f"Reminder email sent to {row['customer_name']}",
    }


def waive_late_fee(invoice_id: int) -> dict:
    # This should never actually be called — the Policy Engine blocks
    # 'waive_late_fee' as high-risk before it reaches here. Present for
    # completeness / to show what the gateway would do if it weren't blocked.
    conn = get_conn()
    conn.execute("UPDATE invoices SET fee_waived = 1 WHERE id = ?", (invoice_id,))
    conn.commit()
    conn.close()
    return {"claimed_success": True, "detail": "Late fee waived"}


TOOL_MAP = {
    "send_reminder_email": send_reminder_email,
    "waive_late_fee": waive_late_fee,
}


def execute(action_type: str, invoice_id: int) -> dict:
    """The single entry point every approved action must go through."""
    tool_fn = TOOL_MAP.get(action_type)
    if not tool_fn:
        return {"claimed_success": False, "detail": f"unknown action: {action_type}"}
    return tool_fn(invoice_id)
