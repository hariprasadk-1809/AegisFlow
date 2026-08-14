"""
AegisFlow — database layer.
SQLite for simplicity: one file, zero setup, easy to inspect live during a demo.
"""
import sqlite3
import os
from datetime import datetime, timedelta

if os.environ.get("VERCEL"):
    DB_PATH = "/tmp/aegisflow.db"
else:
    DB_PATH = os.path.join(os.path.dirname(__file__), "aegisflow.db")


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(reset=False):
    if reset and os.path.exists(DB_PATH):
        os.remove(DB_PATH)

    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS invoices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_name TEXT NOT NULL,
            amount REAL NOT NULL,
            due_date TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'overdue',
            reminder_sent INTEGER NOT NULL DEFAULT 0,
            fee_waived INTEGER NOT NULL DEFAULT 0
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            action_type TEXT NOT NULL,
            target TEXT NOT NULL,
            risk_tier TEXT NOT NULL,
            policy_decision TEXT NOT NULL,
            agent_claimed TEXT,
            verified_result TEXT,
            verification_status TEXT,
            details TEXT
        )
    """)

    # Seed demo invoices only if table is empty
    cur.execute("SELECT COUNT(*) as c FROM invoices")
    if cur.fetchone()["c"] == 0:
        today = datetime.now()
        demo_invoices = [
            ("Nimbus Retail Pvt Ltd", 48500.00, (today - timedelta(days=12)).strftime("%Y-%m-%d")),
            ("Orion Textiles",        122000.00, (today - timedelta(days=25)).strftime("%Y-%m-%d")),
            ("Kavya Logistics",        15750.00, (today - timedelta(days=5)).strftime("%Y-%m-%d")),
            ("Sundar Traders",         89000.00, (today - timedelta(days=40)).strftime("%Y-%m-%d")),
        ]
        cur.executemany(
            "INSERT INTO invoices (customer_name, amount, due_date) VALUES (?, ?, ?)",
            demo_invoices,
        )

    conn.commit()
    conn.close()


def log_audit(action_type, target, risk_tier, policy_decision,
               agent_claimed=None, verified_result=None,
               verification_status=None, details=None):
    conn = get_conn()
    conn.execute(
        """INSERT INTO audit_log
           (timestamp, action_type, target, risk_tier, policy_decision,
            agent_claimed, verified_result, verification_status, details)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (datetime.now().isoformat(timespec="seconds"), action_type, target,
         risk_tier, policy_decision, agent_claimed, verified_result,
         verification_status, details),
    )
    conn.commit()
    conn.close()
