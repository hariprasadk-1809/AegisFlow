# AegisFlow — Demo

## Run it

```bash
pip install -r requirements.txt
uvicorn backend.main:app --reload --port 8000
```

Open http://localhost:8000

## What to click during the demo

1. Click **Run Pipeline** with the default task text.
2. Watch the trace panel — 4 reminders get evaluated, then a fee-waiver attempt.
3. Point out **Orion Textiles**: the gateway claims success, but Verification catches
   that the database was never actually updated — this is the "don't trust the
   agent's self-report" moment.
4. Point out the last step: **waive_late_fee is blocked** by the Policy Engine
   before it even reaches the Tool Gateway — this is the "LLM != Authority" moment.
5. Click **Reset Demo** to restore the seed data if you want to run it again.

## Optional: real LLM planner

By default the Planner uses a deterministic fallback (so the demo never breaks on
stage due to network/API issues). To use a real Claude call for planning instead:

```bash
export ANTHROPIC_API_KEY=your_key_here
uvicorn backend.main:app --reload --port 8000
```

## Project structure

```
backend/
  db.py            - SQLite setup + seed data + audit logging
  policy.py        - Policy Engine (risk tiers, auto/approve/block)
  gateway.py        - Tool Gateway (only path to "real" actions)
  verification.py  - Verification Engine (checks real DB state)
  planner.py        - Planner Agent (LLM or fallback)
  main.py           - FastAPI orchestrator + API endpoints
frontend/
  index.html        - Live demo UI
```
