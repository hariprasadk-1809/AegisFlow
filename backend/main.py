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

from backend.db import init_db, get_conn, log_audit
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


@app.post("/api/run")
def run_pipeline(body: dict):
    """
    Runs the full AegisFlow pipeline for a given task description.
    Returns a step-by-step trace so the frontend can animate it.
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
            "gateway_result": None,
            "verification": None,
        }

        if decision["decision"] == "blocked":
            log_audit(
                action_type, target_name, decision["risk_tier"], decision["decision"],
                details="Blocked by Policy Engine before reaching Tool Gateway.",
            )
            trace.append(step_trace)
            continue

        # 2. TOOL GATEWAY (only reached if not blocked)
        gateway_result = gateway.execute(action_type, invoice_id)
        step_trace["gateway_result"] = gateway_result

        # 3. VERIFICATION ENGINE (only meaningful for send_reminder_email in this MVP)
        if action_type == "send_reminder_email":
            verify_result = verification.verify_reminder_sent(
                invoice_id, gateway_result.get("claimed_success", False)
            )
            step_trace["verification"] = verify_result

            log_audit(
                action_type, target_name, decision["risk_tier"], decision["decision"],
                agent_claimed=str(gateway_result.get("claimed_success")),
                verified_result=verify_result["verification_status"],
                verification_status=verify_result["verification_status"],
                details=verify_result["reason"],
            )
        else:
            log_audit(
                action_type, target_name, decision["risk_tier"], decision["decision"],
                agent_claimed=str(gateway_result.get("claimed_success")),
                details=gateway_result.get("detail"),
            )

        trace.append(step_trace)

    return {"task": task, "trace": trace}
