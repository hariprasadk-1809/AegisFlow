"""
AegisFlow — orchestrator / API.

This is the only place that calls Planner -> Policy -> Gateway -> Verification
-> Audit in sequence. Run with:

    uvicorn backend.main:app --reload --port 8000

Then open http://localhost:8000 for the demo UI.
"""
from fastapi import FastAPI
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
import os

from backend.db import init_db, get_conn, log_audit, update_audit_approval
from backend import policy, gateway, verification, planner

app = FastAPI(title="AegisFlow")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

init_db(reset=False)

FRONTEND_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend")


@app.get("/", response_class=HTMLResponse)
def index():
    return FileResponse(os.path.join(FRONTEND_DIR, "index.html"))


@app.get("/api/invoices")
def list_invoices():
    conn = get_conn()
    rows = [dict(r) for r in conn.execute("SELECT * FROM invoices ORDER BY id").fetchall()]
    conn.close()
    return rows


@app.get("/api/audit-log")
def get_audit_log():
    conn = get_conn()
    rows = [dict(r) for r in conn.execute(
        "SELECT * FROM audit_log ORDER BY id DESC"
    ).fetchall()]
    conn.close()
    return rows


@app.post("/api/reset")
def reset():
    init_db(reset=True)
    return {"status": "reset"}


def _run_gateway_and_verify(action_type, invoice_id, target_name, decision, audit_id=None):
    """
    Shared by the auto-approved path and the post-approval path: calls the
    Tool Gateway, runs Verification where applicable, and logs/updates the
    audit trail. Returns (gateway_result, verification_result).
    """
    gateway_result = gateway.execute(action_type, invoice_id)
    verify_result = None

    if action_type == "send_reminder_email":
        verify_result = verification.verify_reminder_sent(
            invoice_id, gateway_result.get("claimed_success", False)
        )

    if audit_id is None:
        log_audit(
            action_type, target_name, decision["risk_tier"], decision["decision"],
            rule_id=decision["rule_id"], reason=decision["reason"],
            agent_claimed=str(gateway_result.get("claimed_success")),
            verified_result=verify_result["verification_status"] if verify_result else None,
            verification_status=verify_result["verification_status"] if verify_result else None,
            details=verify_result["reason"] if verify_result else gateway_result.get("detail"),
        )

    return gateway_result, verify_result


@app.post("/api/run")
def run_pipeline(body: dict):
    """
    Runs the full AegisFlow pipeline for a given task description.
    Returns a step-by-step trace so the frontend can animate it.

    Steps the Policy Engine marks 'needs_approval' are NOT executed here —
    they're logged as pending and held for a human decision via /api/approve.
    This is the actual human-in-the-loop gate, not just a label in the trace.
    """
    task = body.get("task", "Chase all overdue invoices and waive fees where reasonable")

    steps = planner.plan(task)
    trace = []

    for step in steps:
        action_type = step["action_type"]
        invoice_id = step["invoice_id"]

        conn = get_conn()
        inv_row = conn.execute("SELECT customer_name FROM invoices WHERE id = ?", (invoice_id,)).fetchone()
        conn.close()
        target_name = inv_row["customer_name"] if inv_row else f"invoice #{invoice_id}"

        # 1. POLICY ENGINE
        decision = policy.evaluate(action_type)

        step_trace = {
            "action_type": action_type,
            "invoice_id": invoice_id,
            "target": target_name,
            "risk_tier": decision["risk_tier"],
            "policy_decision": decision["decision"],
            "rule_id": decision["rule_id"],
            "reason": decision["reason"],
            "gateway_result": None,
            "verification": None,
            "awaiting_approval": False,
            "audit_id": None,
        }

        if decision["decision"] == "blocked":
            log_audit(
                action_type, target_name, decision["risk_tier"], decision["decision"],
                rule_id=decision["rule_id"], reason=decision["reason"],
                details="Blocked by Policy Engine before reaching Tool Gateway.",
            )
            trace.append(step_trace)
            continue

        if decision["decision"] == "needs_approval":
            # HOLD — do not touch the Tool Gateway until a human decides.
            audit_id = log_audit(
                action_type, target_name, decision["risk_tier"], decision["decision"],
                rule_id=decision["rule_id"], reason=decision["reason"],
                approval_status="pending",
                details="Held for human approval before reaching Tool Gateway.",
            )
            step_trace["awaiting_approval"] = True
            step_trace["audit_id"] = audit_id
            trace.append(step_trace)
            continue

        # 2. TOOL GATEWAY (auto-approved / low risk only)
        gateway_result, verify_result = _run_gateway_and_verify(
            action_type, invoice_id, target_name, decision
        )
        step_trace["gateway_result"] = gateway_result
        step_trace["verification"] = verify_result

        trace.append(step_trace)

    return {"task": task, "trace": trace}


@app.post("/api/approve")
def approve_step(body: dict):
    """
    Human decision on a 'needs_approval' step. If approved, this is the
    ONLY other place (besides the auto-approved path in /api/run) that is
    allowed to call the Tool Gateway. If rejected, nothing runs — we just
    close out the audit entry.
    """
    action_type = body.get("action_type")
    invoice_id = body.get("invoice_id")
    target_name = body.get("target")
    audit_id = body.get("audit_id")
    approved = bool(body.get("approved"))
    approved_by = body.get("approved_by", "demo-user")

    if not approved:
        update_audit_approval(audit_id, "rejected", approved_by)
        return {"status": "rejected", "gateway_result": None, "verification": None}

    decision = policy.evaluate(action_type)
    gateway_result, verify_result = _run_gateway_and_verify(
        action_type, invoice_id, target_name, decision, audit_id=audit_id
    )
    update_audit_approval(
        audit_id, "approved", approved_by,
        agent_claimed=str(gateway_result.get("claimed_success")),
        verified_result=verify_result["verification_status"] if verify_result else None,
        verification_status=verify_result["verification_status"] if verify_result else None,
        details=verify_result["reason"] if verify_result else gateway_result.get("detail"),
    )

    return {
        "status": "approved",
        "gateway_result": gateway_result,
        "verification": verify_result,
    }
