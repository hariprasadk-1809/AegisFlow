# AegisFlow — Demo

## Run it

```bash
pip install -r requirements.txt
uvicorn backend.main:app --reload --port 8000
```

Open http://localhost:8000

## What to click during the demo

1. Click **Run Pipeline** with the default task text.
2. Watch the trace panel — 4 reminders get evaluated (low risk, auto-approved),
   then a status-update attempt, then a fee-waiver attempt.
3. Point out **Orion Textiles**: the gateway claims success, but Verification catches
   that the database was never actually updated — this is the "don't trust the
   agent's self-report" moment.
4. Point out the **update_invoice_status** step: it's medium risk, so it's held —
   the Tool Gateway is never called until you click **Approve** or **Reject** in the
   UI. Click **Approve** and watch the System of Record and Audit Log update live.
   This is the actual human-in-the-loop gate, not just a label.
5. Point out the last step: **waive_late_fee is blocked** by the Policy Engine
   before it even reaches the Tool Gateway — this is the "LLM != Authority" moment.
6. Click **Reset Demo** to restore the seed data if you want to run it again.

## Optional: real LLM planner

By default the Planner uses a deterministic fallback (so the demo never breaks on
stage due to network/API issues). To use a real Claude call for planning instead:

```bash
uvicorn backend.main:app --reload --port 8000
```

## Project structure

```
backend/
  db.py            - SQLite setup + seed data + audit logging (incl. approval tracking)
  policy.py        - Policy Engine (risk tiers, rule IDs + reasons, auto/approve/block)
  gateway.py        - Tool Gateway (only path to "real" actions incl. update_invoice_status)
  verification.py  - Verification Engine (checks real DB state)
  planner.py        - Planner Agent (LLM or fallback)
  main.py           - FastAPI orchestrator + /api/run + /api/approve endpoints
frontend/
  index.html        - Live demo UI (approve/reject, scoreboard, live pipeline highlight)
```

## API endpoints

- `GET  /api/invoices` — current system-of-record state
- `GET  /api/audit-log` — full audit trail, including approval status
- `POST /api/run` — runs the pipeline; `needs_approval` steps are held, not executed
- `POST /api/approve` — human decision on a held step: `{action_type, invoice_id, target, audit_id, approved, approved_by}`
- `POST /api/reset` — restores seed data
