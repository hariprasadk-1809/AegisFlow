"""
AegisFlow — Planner Agent.

Takes a natural-language task and turns it into a structured list of
steps (action_type + invoice_id). This is the only "AI" part of the
pipeline — everything downstream of this (Policy Engine, Tool Gateway,
Verification) treats the plan as untrusted input, not as ground truth.

Design choice for demo reliability: if an ANTHROPIC_API_KEY is set,
we call the real API. If not (e.g. no internet on the judging floor,
or you just don't want live-demo API risk), we fall back to a
deterministic rule-based planner that produces the same demo scenario.
This means the demo NEVER breaks on stage due to network/API issues.
"""
import os
import json
from backend.db import get_conn

USE_LLM = bool(os.environ.get("ANTHROPIC_API_KEY"))


def _fallback_plan(task: str) -> list[dict]:
    """Deterministic plan used when no API key is configured, or as a
    guaranteed-safe demo path. Mirrors what a real LLM planner would
    output for the 'chase overdue invoices' task."""
    conn = get_conn()
    overdue = conn.execute(
        "SELECT id FROM invoices WHERE status = 'overdue' ORDER BY id"
    ).fetchall()
    conn.close()

    steps = []
    for row in overdue:
        steps.append({"action_type": "send_reminder_email", "invoice_id": row["id"]})

    # Deliberately also propose a high-risk action so the Policy Engine
    # has something to block in the demo.
    if overdue:
        steps.append({"action_type": "waive_late_fee", "invoice_id": overdue[-1]["id"]})

    return steps


def _llm_plan(task: str) -> list[dict]:
    import urllib.request

    conn = get_conn()
    invoices = [dict(r) for r in conn.execute("SELECT * FROM invoices").fetchall()]
    conn.close()

    prompt = f"""You are a planning agent. Given this task and this list of invoices,
output ONLY a JSON array of steps. Each step must be an object with
"action_type" (either "send_reminder_email" or "waive_late_fee") and
"invoice_id" (integer). No prose, no markdown fences, JSON array only.

Task: {task}
Invoices: {json.dumps(invoices)}
"""

    body = json.dumps({
        "model": "claude-sonnet-4-6",
        "max_tokens": 1000,
        "messages": [{"role": "user", "content": prompt}],
    }).encode()

    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=body,
        headers={
            "Content-Type": "application/json",
            "x-api-key": os.environ["ANTHROPIC_API_KEY"],
            "anthropic-version": "2023-06-01",
        },
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        data = json.loads(resp.read())

    text = "".join(b["text"] for b in data["content"] if b["type"] == "text")
    text = text.strip().strip("`").replace("json", "", 1).strip()
    return json.loads(text)


def plan(task: str) -> list[dict]:
    if USE_LLM:
        try:
            return _llm_plan(task)
        except Exception:
            # Never let a network/API hiccup break the live demo.
            return _fallback_plan(task)
    return _fallback_plan(task)
