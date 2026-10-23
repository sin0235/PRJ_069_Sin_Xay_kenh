"""
Canary Rollback Emergency Script for Phase P13.
Immediately rolls back an active canary deployment, marks runs as rolled back,
and logs audit trail to guarantee fast recovery.
"""
import json
import sqlite3
import sys
from datetime import datetime, timezone

def execute_rollback(db_path: str, deployment_id: str, reason: str) -> dict:
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    now_iso = datetime.now(timezone.utc).isoformat()

    cursor.execute("SELECT id, workspace_id, status FROM canary_deployments WHERE id = ?", (deployment_id,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        raise ValueError(f"Canary deployment '{deployment_id}' not found.")

    ws_id = row[1]

    # Cap nhat deployment
    cursor.execute("""
        UPDATE canary_deployments
        SET status = 'ROLLED_BACK', rollback_reason = ?, rolled_back_at = ?
        WHERE id = ?
    """, (reason, now_iso, deployment_id))

    # Cap nhat tat ca runs
    cursor.execute("""
        UPDATE canary_research_runs
        SET run_status = 'ROLLED_BACK'
        WHERE canary_deployment_id = ?
    """, (deployment_id,))

    # Ghi audit
    audit_id = f"aud_rb_{now_iso[:10]}_{deployment_id[:6]}"
    details = json.dumps({"deployment_id": deployment_id, "reason": reason})
    try:
        cursor.execute("""
            INSERT INTO audit_events (id, workspace_id, actor_id, event_type, details, created_at)
            VALUES (?, ?, 'operator_script', 'CANARY_ROLLBACK_CLI', ?, ?)
        """, (audit_id, ws_id, details, now_iso))
    except sqlite3.OperationalError:
        pass

    conn.commit()
    conn.close()

    return {
        "status": "ROLLED_BACK_SUCCESS",
        "deployment_id": deployment_id,
        "workspace_id": ws_id,
        "rollback_reason": reason,
        "rolled_back_at": now_iso
    }

if __name__ == "__main__":
    db = sys.argv[1] if len(sys.argv) > 1 else "sin_content_offline.db"
    dep_id = sys.argv[2] if len(sys.argv) > 2 else ""
    r_reason = sys.argv[3] if len(sys.argv) > 3 else "Manual emergency rollback initiated by operator"
    if not dep_id:
        print("Usage: python rollback_canary.py <db_path> <deployment_id> [reason]")
        sys.exit(1)
    res = execute_rollback(db, dep_id, r_reason)
    print("ROLLBACK RESULT:", json.dumps(res, indent=2))
