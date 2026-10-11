"""
Repeatable Demo Activity Seeding Script for PaperIQ Administrator Workspace.
Clearly marked: runs ONLY when explicitly invoked (e.g. `python seed_demo_data.py`).
Seeds realistic telemetry into:
- `processing_events` (succeeded & failed runs across PDF, DOCX, TXT, including
  'scanned PDF, no text layer', 'password-protected', and 'corrupted file')
- `app_errors` (sanitized historical error records so the System Health table is populated)
- `backups/` (creates a verified SQLite database backup if none exists)
- Normalizes any legacy discipline labels and verifies the audit log SHA-256 hash chain.
"""

import sqlite3
from datetime import datetime, timedelta
import auth


def seed_admin_demo_activity() -> dict:
    """Idempotently seeds realistic demo telemetry for the PaperIQ Administrator workspace."""
    auth.create_users_table()
    now = datetime.now()

    conn = sqlite3.connect(auth.DB_PATH)
    c = conn.cursor()

    # 1. Seed processing_events if table has fewer than 5 rows or no failure rows
    c.execute("SELECT COUNT(*) FROM processing_events")
    total_proc = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM processing_events WHERE status = 'failed'")
    failed_proc = c.fetchone()[0]

    seeded_proc = 0
    if total_proc < 8 or failed_proc < 2:
        sample_events = [
            # Successful runs across PDF, DOCX, TXT
            ((now - timedelta(days=5, hours=3)).strftime("%Y-%m-%d %H:%M:%S"), "researcher", "PDF", 1420.5, "extraction", "success", "", 312.4),
            ((now - timedelta(days=5, hours=3)).strftime("%Y-%m-%d %H:%M:%S"), "researcher", "PDF", 1420.5, "analysis", "success", "", 485.2),
            ((now - timedelta(days=4, hours=6)).strftime("%Y-%m-%d %H:%M:%S"), "sohit", "PDF", 890.2, "extraction", "success", "", 210.8),
            ((now - timedelta(days=4, hours=6)).strftime("%Y-%m-%d %H:%M:%S"), "sohit", "PDF", 890.2, "analysis", "success", "", 390.1),
            ((now - timedelta(days=3, hours=11)).strftime("%Y-%m-%d %H:%M:%S"), "Student_Demo", "DOCX", 340.0, "extraction", "success", "", 118.5),
            ((now - timedelta(days=3, hours=11)).strftime("%Y-%m-%d %H:%M:%S"), "Student_Demo", "DOCX", 340.0, "analysis", "success", "", 275.0),
            ((now - timedelta(days=2, hours=8)).strftime("%Y-%m-%d %H:%M:%S"), "researcher", "TXT", 95.4, "extraction", "success", "", 42.3),
            ((now - timedelta(days=2, hours=8)).strftime("%Y-%m-%d %H:%M:%S"), "researcher", "TXT", 95.4, "analysis", "success", "", 188.7),
            ((now - timedelta(days=1, hours=5)).strftime("%Y-%m-%d %H:%M:%S"), "admin", "PDF", 2150.0, "repository_analysis", "success", "", 610.4),
            ((now - timedelta(hours=6)).strftime("%Y-%m-%d %H:%M:%S"), "researcher", "PDF", 1180.0, "extraction", "success", "", 265.9),
            ((now - timedelta(hours=6)).strftime("%Y-%m-%d %H:%M:%S"), "researcher", "PDF", 1180.0, "analysis", "success", "", 412.6),
            # Simulated processing failures (timestamped >24h ago so 24h System Status remains Healthy)
            ((now - timedelta(days=3, hours=2)).strftime("%Y-%m-%d %H:%M:%S"), "Student_Demo", "PDF", 4820.0, "extraction", "failed", "scanned PDF, no text layer", 145.0),
            ((now - timedelta(days=2, hours=14)).strftime("%Y-%m-%d %H:%M:%S"), "sohit", "PDF", 1640.0, "extraction", "failed", "password-protected", 64.2),
            ((now - timedelta(days=4, hours=9)).strftime("%Y-%m-%d %H:%M:%S"), "Student_Demo", "DOCX", 512.0, "extraction", "failed", "corrupted file", 52.8),
        ]
        for ts, uid, ftype, fkb, stage, st_val, reason, dur in sample_events:
            c.execute(
                """
                INSERT INTO processing_events (timestamp, user_id, file_type, file_size_kb, stage, status, failure_reason, duration_ms)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (ts, uid, ftype, fkb, stage, st_val, reason, dur),
            )
            seeded_proc += 1

    # 2. Seed sample app_errors (timestamped >24h ago so 24h System Status stays Healthy while 7d/30d table is populated)
    c.execute("SELECT COUNT(*) FROM app_errors")
    total_err = c.fetchone()[0]
    seeded_err = 0
    if total_err < 2:
        sample_errors = [
            (
                (now - timedelta(days=2, hours=4)).strftime("%Y-%m-%d %H:%M:%S"),
                "Student_Demo",
                "Student",
                "Analyze Paper",
                "PDFSyntaxError",
                "Malformed XRef table encountered during stream parsing in <path>/pdf_reader.py",
                "a91f4c82b03e19d4",
            ),
            (
                (now - timedelta(days=4, hours=7)).strftime("%Y-%m-%d %H:%M:%S"),
                "researcher",
                "Researcher",
                "Compare Manuscripts",
                "ValueError",
                "Insufficient section overlap for cross-manuscript alignment in <path>/comparator.py",
                "7c3e9104d82a55b1",
            ),
        ]
        for ts, uid, role_v, pg, etype, msg_s, shash in sample_errors:
            c.execute(
                """
                INSERT INTO app_errors (timestamp, user_id, role, page, error_type, message_short, stack_hash)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (ts, uid, role_v, pg, etype, auth.sanitize_error_message(msg_s), shash),
            )
            seeded_err += 1

    conn.commit()
    conn.close()

    # 3. Ensure at least one verified backup exists in backups/
    backups = auth.list_db_backups()
    created_backup = None
    if not backups:
        ok, msg, info = auth.create_db_backup(created_by="admin", label="initial_baseline")
        if ok and info:
            created_backup = info.get("filename")

    # 4. Ensure audit hash chain is anchored and verified
    auth.ensure_audit_hash_chain()
    chain_status = auth.verify_audit_log_integrity()

    return {
        "seeded_processing_events": seeded_proc,
        "seeded_app_errors": seeded_err,
        "created_backup": created_backup,
        "total_backups": len(auth.list_db_backups()),
        "audit_chain_valid": chain_status.get("valid"),
        "audit_verified_rows": chain_status.get("verified_count"),
    }


if __name__ == "__main__":
    summary = seed_admin_demo_activity()
    print("PaperIQ Admin Demo Activity Seed Complete:", summary)
