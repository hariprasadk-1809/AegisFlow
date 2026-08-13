"""
AegisFlow — Verification Engine.

This is the whole point of the project. After the Tool Gateway executes
an action and returns "claimed_success", we do NOT take that at face
value. We go back to the actual system of record (the invoices table)
and check whether the claimed outcome is actually true.

This is deliberately a single, honest, hardcoded check for the MVP —
not a generalized verification framework. See Idea/Approach slide for
the scope note.
"""
from backend.db import get_conn


def verify_reminder_sent(invoice_id: int, agent_claimed_success: bool) -> dict:
    conn = get_conn()
    row = conn.execute("SELECT * FROM invoices WHERE id = ?", (invoice_id,)).fetchone()
    conn.close()

    if not row:
        return {
            "verification_status": "failed",
            "reason": "invoice not found — cannot verify",
        }

    actually_sent = bool(row["reminder_sent"])

    if agent_claimed_success and actually_sent:
        return {
            "verification_status": "verified",
            "reason": "Agent claimed success, and reminder_sent = 1 in DB. Confirmed.",
        }

    if agent_claimed_success and not actually_sent:
        return {
            "verification_status": "mismatch",
            "reason": (
                "Agent claimed the reminder was sent, but the invoice record "
                "was never updated. The claim does not match real system state."
            ),
        }

    if not agent_claimed_success:
        return {
            "verification_status": "failed",
            "reason": "Agent itself reported failure — no action taken.",
        }

    return {"verification_status": "unknown", "reason": "unexpected state"}
