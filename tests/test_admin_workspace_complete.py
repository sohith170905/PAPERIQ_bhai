"""
Comprehensive Pytest Verification Suite for the PaperIQ Administrator Workspace Upgrade (Parts 1–5).
Covers all 15 mandatory verification categories from Part 5.9:
1. password_hashing
2. lockout
3. role_guardrails
4. reset_password
5. user_deletion
6. audit_hash_chain
7. audit_purge
8. privacy
9. backups
10. settings_enforcement
11. error_logging
12. duplicate_repo
13. discipline_normalization
14. csv_formula_injection
15. migrations_idempotent
"""

import hashlib
import io
import json
import os
import sqlite3
from datetime import datetime, timedelta

import pytest

import auth
import admin_panel


@pytest.fixture()
def isolated_db(tmp_path, monkeypatch):
    """
    Provides an isolated SQLite database and backups folder for each test so
    the production users.db is never mutated by destructive test scenarios.
    """
    test_db = str(tmp_path / "test_users.db")
    test_backups = str(tmp_path / "backups")
    os.makedirs(test_backups, exist_ok=True)

    monkeypatch.setattr(auth, "DB_PATH", test_db)
    monkeypatch.setattr(auth, "BACKUPS_DIR", test_backups)
    monkeypatch.setattr(auth, "_TABLES_INITIALIZED_PATH", None)

    auth.create_users_table(force=True)
    yield test_db, test_backups


# ===========================================================================
# 1. PASSWORD HASHING (PBKDF2-HMAC-SHA256 + Legacy SHA-256 Auto-Upgrade)
# ===========================================================================
def test_password_hashing_pbkdf2_and_legacy_upgrade(isolated_db):
    # PBKDF2 format check
    h1 = auth.hash_password("CorrectHorseBatteryStaple!99")
    h2 = auth.hash_password("CorrectHorseBatteryStaple!99")
    assert h1.startswith("pbkdf2_sha256$")
    parts = h1.split("$")
    assert len(parts) == 4
    assert int(parts[1]) >= 600000
    assert len(parts[2]) == 32  # 16-byte random salt hex
    # Random per-user salt ensures two hashes of the same password differ
    assert h1 != h2

    # Verification works for PBKDF2 and is not marked as legacy
    assert auth.verify_password("CorrectHorseBatteryStaple!99", h1) is True
    assert auth.is_legacy_hash(h1) is False
    assert auth.verify_password("WrongPassword", h1) is False

    # Legacy raw SHA-256 verification and automatic upgrade on login
    legacy_pw = "LegacyPass123"
    legacy_sha256 = hashlib.sha256(legacy_pw.encode("utf-8")).hexdigest()
    assert auth.verify_password(legacy_pw, legacy_sha256) is True
    assert auth.is_legacy_hash(legacy_sha256) is True

    # Insert user with legacy SHA-256 hash directly into DB
    conn = auth.get_db_connection()
    conn.execute(
        "INSERT INTO users (username, password, role, status) VALUES (?, ?, 'Student', 'Active')",
        ("legacy_alice", legacy_sha256),
    )
    conn.commit()
    conn.close()

    # Log in as legacy_alice -> should succeed and transparently upgrade stored hash to PBKDF2
    user_info = auth.login_user("legacy_alice", legacy_pw)
    assert user_info is not None
    assert user_info["username"] == "legacy_alice"

    conn = auth.get_db_connection()
    row = conn.execute("SELECT password, last_login FROM users WHERE username = 'legacy_alice'").fetchone()
    conn.close()
    assert row["password"].startswith("pbkdf2_sha256$")
    assert bool(row["last_login"])


# ===========================================================================
# 2. FAILED-LOGIN LOCKOUT & RATE LIMITING
# ===========================================================================
def test_lockout_after_five_failed_logins(isolated_db):
    assert auth.signup_user("lockout_bob", "ValidPass!234", "Student")[0] is True

    # 5 failed login attempts
    for i in range(5):
        res = auth.login_user("lockout_bob", f"WrongPass_{i}", ip="10.0.0.55")
        assert res is None

    # Account must now be locked for ~15 minutes
    is_locked, rem_sec, locked_until = auth.check_account_lockout("lockout_bob", ip="10.0.0.55")
    assert is_locked is True
    assert rem_sec > 600  # ~900 seconds (15 minutes)
    assert locked_until != ""

    # Even the CORRECT password must be rejected while locked out
    res_during_lock = auth.login_user("lockout_bob", "ValidPass!234", ip="10.0.0.55")
    assert res_during_lock is None

    # Verify LOGIN_LOCKOUT audit event was written
    logs = auth.get_login_history(username="lockout_bob", current_admin_user="admin")
    actions = [l.get("action_type") for l in logs]
    statuses = [l.get("status") for l in logs]
    assert "LOGIN_LOCKOUT" in actions
    assert any("Lock" in str(s) for s in statuses)

    # Clearing lockout restores access with valid password
    auth.clear_account_lockout("lockout_bob")
    res_after_clear = auth.login_user("lockout_bob", "ValidPass!234", ip="10.0.0.55")
    assert res_after_clear is not None
    assert res_after_clear["username"] == "lockout_bob"


# ===========================================================================
# 3. ROLE-CHANGE & SELF-PROTECTION GUARDRAILS
# ===========================================================================
def test_role_guardrails_self_demotion_last_admin_and_forged_signup(isolated_db):
    # 1. Self-registration with forged role 'Administrator' MUST fail and log audit event
    ok_forge, msg_forge = auth.signup_user("mallory_hacker", "Pass1234!", role="Administrator")
    assert ok_forge is False
    assert "Administrator" in msg_forge or "Student" in msg_forge or "Denied" in msg_forge or "forbidden" in msg_forge.lower()

    conn = auth.get_db_connection()
    mallory_row = conn.execute("SELECT * FROM users WHERE username = 'mallory_hacker'").fetchone()
    conn.close()
    assert mallory_row is None

    # Verify UNAUTHORIZED_ACCESS audit event was logged for mallory_hacker
    audit_rows = auth.get_login_history(username="mallory_hacker", current_admin_user="admin")
    assert any(r["action_type"] == "UNAUTHORIZED_ACCESS" for r in audit_rows)

    # 2. Admin cannot demote their own account
    ok_self_demote, msg_self_demote = auth.update_user_role("admin", "Student", current_admin_user="admin")
    assert ok_self_demote is False
    assert "demote your own" in msg_self_demote.lower() or "self-lockout" in msg_self_demote.lower()

    # 3. Admin cannot deactivate their own account
    ok_self_deact, msg_self_deact = auth.toggle_user_status("admin", "Disabled", current_admin_user="admin")
    assert ok_self_deact is False

    # 4. Promoting another user to Administrator requires matching confirm_username
    auth.signup_user("TrustedResearcher", "ResPass123!", "Researcher")
    ok_no_conf, msg_no_conf = auth.update_user_role(
        "TrustedResearcher", "Administrator", current_admin_user="admin", confirm_username=""
    )
    assert ok_no_conf is False
    assert "confirmation" in msg_no_conf.lower()

    ok_with_conf, _ = auth.update_user_role(
        "TrustedResearcher",
        "Administrator",
        current_admin_user="admin",
        confirm_username="TrustedResearcher",
    )
    assert ok_with_conf is True
    assert auth.get_user_role("TrustedResearcher") == "Administrator"

    # 5. Demote TrustedResearcher back to Researcher so 'admin' is the ONLY active admin
    ok_demote, _ = auth.update_user_role("TrustedResearcher", "Researcher", current_admin_user="admin")
    assert ok_demote is True

    # Ensure last-admin protection blocks bulk deactivation of 'admin'
    ok_bulk, msg_bulk, _ = auth.bulk_update_user_status(
        ["admin", "TrustedResearcher"], "Disabled", current_admin_user="admin"
    )
    assert ok_bulk is True
    assert "skipped" in msg_bulk.lower()
    assert auth.get_user_role("admin") == "Administrator"


# ===========================================================================
# 4. ADMIN PASSWORD RESET & MUST_CHANGE_PASSWORD WORKFLOW
# ===========================================================================
def test_reset_password_generates_strong_temp_and_sets_flag(isolated_db):
    auth.signup_user("student_reset_user", "InitialPass123", "Student")

    res = auth.admin_reset_password("student_reset_user", current_admin_user="admin")
    ok, msg = res
    assert ok is True
    assert hasattr(res, "temp_password")
    temp_pw = res.temp_password
    assert len(temp_pw) >= 12

    # Check DB flag must_change_password == 1
    conn = auth.get_db_connection()
    row = conn.execute("SELECT must_change_password, password FROM users WHERE username = 'student_reset_user'").fetchone()
    conn.close()
    assert int(row["must_change_password"]) == 1

    # Ensure audit log has PASSWORD_RESET without leaking temp_pw or password hash
    logs = auth.get_login_history(action_type="PASSWORD_RESET", current_admin_user="admin")
    assert len(logs) >= 1
    latest_log = logs[0]
    assert temp_pw not in str(latest_log.get("details", ""))
    assert row["password"] not in str(latest_log.get("details", ""))

    # Logging in with temp_pw works and returns must_change_password=True
    logged = auth.login_user("student_reset_user", temp_pw)
    assert logged is not None
    assert logged["must_change_password"] is True

    # Changing password clears must_change_password=0
    ok_chg, _ = auth.change_user_password("student_reset_user", temp_pw, "BrandNewSecurePass#2026")
    assert ok_chg is True
    logged_after = auth.login_user("student_reset_user", "BrandNewSecurePass#2026")
    assert logged_after is not None
    assert logged_after["must_change_password"] is False


# ===========================================================================
# 5. USER DELETION (CONFIRMATION, DELETE_ALL VS ANONYMIZE, AUDIT PRESERVED)
# ===========================================================================
def test_user_deletion_modes_and_confirmation(isolated_db):
    # Create two users with analyses
    auth.signup_user("del_user_all", "Pass1234!", "Student")
    auth.save_analysis_record(
        "del_user_all", "paper1.pdf", "Computer Science", 85.0, b"%PDF-1.4", json.dumps({"overall_score": 85.0})
    )

    auth.signup_user("del_user_anon", "Pass1234!", "Researcher")
    auth.save_analysis_record(
        "del_user_anon", "paper2.pdf", "Medicine & Health", 91.0, b"%PDF-1.4", json.dumps({"overall_score": 91.0})
    )

    # 1. Deletion without matching confirmation fails
    ok_no_conf, _ = auth.delete_user_account(
        "del_user_all", mode="delete_all", confirm_username="wrong_name", current_admin_user="admin"
    )
    assert ok_no_conf is False

    # 2. Admin cannot delete self
    ok_self, _ = auth.delete_user_account(
        "admin", mode="delete_all", confirm_username="admin", current_admin_user="admin"
    )
    assert ok_self is False

    # 3. Delete with mode='delete_all' removes user and their analyses, preserves login_history
    ok_del1, _ = auth.delete_user_account(
        "del_user_all", mode="delete_all", confirm_username="del_user_all", current_admin_user="admin"
    )
    assert ok_del1 is True
    conn = auth.get_db_connection()
    assert conn.execute("SELECT 1 FROM users WHERE username = 'del_user_all'").fetchone() is None
    assert conn.execute("SELECT COUNT(*) FROM analysis_history WHERE username = 'del_user_all'").fetchone()[0] == 0
    assert conn.execute("SELECT COUNT(*) FROM login_history WHERE target = 'del_user_all' AND action_type = 'USER_DELETE'").fetchone()[0] == 1
    conn.close()

    # 4. Delete with mode='anonymize' removes user account but keeps analysis_history under 'anon_<hash>'
    ok_del2, _ = auth.delete_user_account(
        "del_user_anon", mode="anonymize", confirm_username="del_user_anon", current_admin_user="admin"
    )
    assert ok_del2 is True
    conn = auth.get_db_connection()
    assert conn.execute("SELECT 1 FROM users WHERE username = 'del_user_anon'").fetchone() is None
    anon_row = conn.execute("SELECT username FROM analysis_history WHERE username LIKE 'anon_%'").fetchone()
    conn.close()
    assert anon_row is not None


# ===========================================================================
# 6. AUDIT LOG CRYPTOGRAPHIC HASH CHAIN & TAMPER DETECTION
# ===========================================================================
def test_audit_hash_chain_verification_and_tamper_detection(isolated_db):
    auth.record_audit_event("admin", "SETTINGS_UPDATE", "max_upload_size_mb", "Changed 25 -> 30", "Success")
    auth.record_audit_event("admin", "USER_STATUS_CHANGE", "demo", "Status Active", "Success")

    ver_ok = auth.verify_audit_log_integrity(current_admin_user="admin")
    assert ver_ok["ok"] is True
    assert ver_ok["verified_count"] >= 2
    assert ver_ok["broken_row_id"] is None

    # Directly tamper with a row in SQLite
    conn = auth.get_db_connection()
    target_row = conn.execute("SELECT id, details FROM login_history ORDER BY id DESC LIMIT 1").fetchone()
    tampered_id = target_row["id"]
    conn.execute("UPDATE login_history SET details = 'TAMPERED BY ATTACKER' WHERE id = ?", (tampered_id,))
    conn.commit()
    conn.close()

    ver_bad = auth.verify_audit_log_integrity(current_admin_user="admin")
    assert ver_bad["ok"] is False
    assert ver_bad["broken_row_id"] == tampered_id or tampered_id in ver_bad.get("tamper_ids", [])
    assert "TAMPER" in ver_bad["message"].upper()
    assert ver_bad.get("tamper_count", 0) >= 1


# ===========================================================================
# 7. AUDIT LOG RETENTION PURGE, AUTO-ARCHIVE, AND IMMUTABLE PURGE RECORD
# ===========================================================================
def test_audit_purge_policy_and_immutable_record(isolated_db):
    # Insert an old audit record (120 days ago) and a recent audit record
    old_ts = (datetime.now() - timedelta(days=120)).strftime("%Y-%m-%d %H:%M:%S")
    conn = auth.get_db_connection()
    conn.execute(
        """
        INSERT INTO login_history (username, role, login_time, status, ip_address, action_type, target, details, is_immutable)
        VALUES ('old_actor', 'Student', ?, 'Success', '127.0.0.1', 'LOGIN', '', 'Old login event', 0)
        """,
        (old_ts,),
    )
    conn.commit()
    auth._reanchor_audit_hash_chain_after_purge(conn)
    conn.commit()
    conn.close()

    # 1. "Purge all" (older_than_days=None) MUST be rejected
    res_all = auth.clear_login_history(current_admin_user="admin", older_than_days=None, reason="Try purge all")
    assert res_all[0] is False
    assert "blocked" in res_all[1].lower()

    # 2. Purge < retention days (e.g. 30 < 90) MUST be rejected
    res_short = auth.purge_audit_history(older_than_days=30, reason="Too short retention", current_admin_user="admin")
    assert res_short[0] is False

    # 3. Purge without reason MUST be rejected
    res_noreason = auth.purge_audit_history(older_than_days=90, reason="", current_admin_user="admin")
    assert res_noreason[0] is False

    # 4. Valid purge (>= 90 days + reason) succeeds, archives CSV, re-anchors chain, and writes immutable LOG_PURGE
    res_valid = auth.purge_audit_history(
        older_than_days=90, reason="Quarterly compliance retention cleanup", current_admin_user="admin"
    )
    assert res_valid[0] is True
    assert res_valid.purged_count >= 1
    assert os.path.exists(res_valid.archive_path)

    # Chain integrity must still be 100% valid after purge!
    ver = auth.verify_audit_log_integrity(current_admin_user="admin")
    assert ver["ok"] is True

    # Verify LOG_PURGE record has is_immutable=1 and cannot be purged even if backdated
    conn = auth.get_db_connection()
    purge_row = conn.execute("SELECT id, is_immutable FROM login_history WHERE action_type = 'LOG_PURGE'").fetchone()
    assert purge_row is not None
    assert int(purge_row["is_immutable"]) == 1
    conn.execute("UPDATE login_history SET login_time = ? WHERE id = ?", (old_ts, purge_row["id"]))
    conn.commit()
    conn.close()

    res_second = auth.purge_audit_history(
        older_than_days=90, reason="Attempt to purge immutable record", current_admin_user="admin"
    )
    assert res_second[0] is True
    conn = auth.get_db_connection()
    still_exists = conn.execute("SELECT id FROM login_history WHERE id = ?", (purge_row["id"],)).fetchone()
    conn.close()
    assert still_exists is not None


# ===========================================================================
# 8. PRIVACY ENFORCEMENT (NO PRIVATE CONTENT ACCESS FOR ADMIN + CSV SAFETY)
# ===========================================================================
def test_privacy_admin_blocked_from_private_papers_and_csv_sanitized(isolated_db):
    auth.signup_user("private_student", "StudPass123!", "Student")
    rec_id, _, _ = auth.save_analysis_record(
        "private_student",
        "secret_thesis_draft.pdf",
        "Computer Science",
        92.5,
        b"%PDF-1.4-SECRET-CONTENT",
        json.dumps(
            {
                "overall_score": 92.5,
                "full_text": "ULTRA CONFIDENTIAL UNPUBLISHED STUDENT RESEARCH TEXT",
                "sections": {"Abstract": "Private abstract text"},
            }
        ),
    )
    auth.record_upload("private_student", "secret_thesis_draft.pdf", "PDF", 240.0, "Processed", "Personal")
    assert rec_id is not None

    # 1. Owner can access their own analysis record
    owner_rec = auth.get_analysis_record(rec_id, username="private_student")
    assert owner_rec is not None
    assert owner_rec["filename"] == "secret_thesis_draft.pdf"

    # 2. Admin calling get_analysis_record / get_analysis_pdf_report / get_user_history for private_student MUST be denied
    admin_rec = auth.get_analysis_record(rec_id, username="admin")
    assert admin_rec is None
    admin_pdf = auth.get_analysis_pdf_report(rec_id, username="admin")
    assert admin_pdf is None
    admin_hist = auth.get_user_history("private_student", requester_username="admin")
    assert admin_hist == []

    # Verify UNAUTHORIZED_ACCESS was logged against admin
    unauth_logs = auth.get_login_history(action_type="UNAUTHORIZED_ACCESS", current_admin_user="admin")
    assert any(l["username"] == "admin" for l in unauth_logs)

    # 3. Admin aggregate summary contains NO filenames, titles, full_text, or results_json
    agg_rows = auth.get_all_analyses_summary(current_admin_user="admin")
    assert len(agg_rows) >= 1
    for r in agg_rows:
        assert "filename" not in r
        assert "original_filename" not in r
        assert "display_title" not in r
        assert "results_json" not in r
        assert "pdf_data" not in r

    # 4. Admin upload_history masks filenames as 'sec….pdf'
    uploads = auth.get_upload_history()
    assert len(uploads) >= 1
    for u in uploads:
        assert "secret_thesis_draft" not in u["filename"]
        assert "…" in u["filename"]

    # 5. CSV exports contain no password_hash, full_text, results_json, or unmasked filenames
    users_csv = auth.export_users_csv(current_admin_user="admin")
    assert "pbkdf2_sha256$" not in users_csv
    assert "password_hash" not in users_csv.lower()

    uploads_csv = auth.export_upload_history_csv(current_admin_user="admin")
    assert "secret_thesis_draft" not in uploads_csv
    assert "ULTRA CONFIDENTIAL" not in uploads_csv

    analytics_csv = auth.export_analytics_summary_csv(current_admin_user="admin")
    assert "secret_thesis_draft" not in analytics_csv
    assert "ULTRA CONFIDENTIAL" not in analytics_csv


# ===========================================================================
# 9. ONLINE SQLITE BACKUPS & RETENTION CLEANUP
# ===========================================================================
def test_sqlite_online_backups_and_retention(isolated_db):
    _, backups_dir = isolated_db

    ok, msg, fname = auth.create_db_backup(current_admin_user="admin")
    assert ok is True
    assert fname is not None
    backup_path = os.path.join(backups_dir, fname)
    assert os.path.exists(backup_path)
    assert os.path.getsize(backup_path) > 0

    # Verify backup passes PRAGMA integrity_check
    bconn = sqlite3.connect(backup_path)
    chk = bconn.execute("PRAGMA integrity_check").fetchone()[0]
    bconn.close()
    assert chk.lower() == "ok"

    # Verify backup listing and last backup info
    backups = auth.list_db_backups()
    assert len(backups) == 1
    last_info = auth.get_last_backup_info()
    assert last_info is not None
    assert last_info["last_backup_filename"] == fname

    # Create additional backup files and test retention cleanup (keep newest 2)
    for idx in range(3):
        dummy_name = f"users_backup_2025010{idx+1}_120000.db"
        with open(os.path.join(backups_dir, dummy_name), "wb") as f:
            f.write(b"SQLite format 3\x00")

    all_before = auth.list_db_backups()
    assert len(all_before) == 4

    ok_ret, msg_ret, removed_cnt = auth.apply_backup_retention(keep_last_n=2, current_admin_user="admin")
    assert ok_ret is True
    assert removed_cnt == 2
    all_after = auth.list_db_backups()
    assert len(all_after) == 2


# ===========================================================================
# 10. PLATFORM SETTINGS VALIDATION & LIVE ENFORCEMENT
# ===========================================================================
def test_platform_settings_validation_and_enforcement(isolated_db):
    # 1. Validation rejects out-of-range settings
    ok_bad, _ = auth.update_platform_setting("max_upload_size_mb", "9999", current_admin_user="admin")
    assert ok_bad is False

    # 2. Disable registration and verify signup_user rejects new accounts
    ok_reg, _ = auth.update_platform_setting("registration_enabled", "false", current_admin_user="admin")
    assert ok_reg is True
    ok_su, msg_su = auth.signup_user("blocked_new_user", "Pass1234!", "Student")
    assert ok_su is False
    assert "disabled" in msg_su.lower()

    # Re-enable registration and set default_role to Researcher
    auth.update_platform_setting("registration_enabled", "true", current_admin_user="admin")
    auth.update_platform_setting("default_role", "Researcher", current_admin_user="admin")
    ok_su2, _ = auth.signup_user("auto_researcher_user", "Pass1234!", role=None)
    assert ok_su2 is True
    assert auth.get_user_role("auto_researcher_user") == "Researcher"

    # 3. Restrict allowed_formats to PDF only and verify app.extract_text_from_file blocks TXT
    import app
    auth.update_platform_setting("allowed_formats", "PDF", current_admin_user="admin")
    fake_txt = io.BytesIO(b"Sample text file content for upload check")
    fake_txt.name = "notes.txt"
    extracted = app.extract_text_from_file(fake_txt)
    assert extracted in (None, "__ERROR_UNSUPPORTED_FORMAT__")

    # Verify processing_events logged 'unsupported type'
    events = auth.get_processing_events(status="failed", current_admin_user="admin")
    assert any(e["failure_reason"] == "unsupported type" for e in events)

    # Restore allowed_formats
    auth.update_platform_setting("allowed_formats", "PDF,DOCX,TXT", current_admin_user="admin")


# ===========================================================================
# 11. APPLICATION ERROR LOGGING & SANITIZATION + PROCESSING EVENTS
# ===========================================================================
def test_error_logging_sanitizes_paths_and_secrets_and_logs_processing_events(isolated_db):
    raw_sensitive_msg = (
        r"FileNotFoundError in C:\Users\sohit\Downloads\PaperIQ-Streamlit-Final-Fixed\secret_paper.pdf "
        r"password_hash=pbkdf2_sha256$600000$abcdef$1234567890 "
        + ("X" * 400)
    )
    err_id = auth.log_app_error(
        error_type="FileNotFoundError",
        message=raw_sensitive_msg,
        page="Analyze Paper",
        role="Student",
        user_id="student1",
        stack_text="Traceback (most recent call last): File C:\\Users\\sohit\\app.py line 100",
    )
    assert err_id is not None

    errors = auth.get_app_errors(current_admin_user="admin")
    assert len(errors) >= 1
    logged_err = errors[0]
    msg_short = logged_err["message_short"]
    # Truncated to <= 300 chars and strips Windows user path and pbkdf2 hash
    assert len(msg_short) <= 300
    assert "sohit" not in msg_short.lower()
    assert "pbkdf2_sha256$600000" not in msg_short
    assert len(logged_err["stack_hash"]) == 16

    # Log processing events and check stats
    auth.log_processing_event("student1", "PDF", 450.0, "extraction", "failed", "scanned PDF, no text layer", 310.0)
    auth.log_processing_event("student1", "PDF", 320.0, "analysis", "success", "", 820.0)
    p_stats = auth.get_processing_stats(days=7)
    assert p_stats["total"] >= 2
    assert p_stats["failed"] >= 1
    assert "scanned PDF, no text layer" in p_stats["by_reason"]


# ===========================================================================
# 12. REPOSITORY DUPLICATE DETECTION & CLEANUP
# ===========================================================================
def test_duplicate_repository_detection_and_override(isolated_db):
    content_bytes = b"%PDF-1.4 SAMPLE REPOSITORY MANUSCRIPT BYTES"
    pid1 = auth.save_repository_paper(
        title="Deep Learning in Agriculture",
        authors="Dr. Jane Smith",
        domain="Agri",
        uploaded_by="admin",
        filename="dl_agri.pdf",
        file_bytes=content_bytes,
        pdf_report_bytes=b"%PDF-1.4 REPORT",
        score=91.0,
        grade="A",
        allow_duplicate=False,
    )
    assert pid1 is not None

    # Uploading the exact same paper a second time with allow_duplicate=False MUST be blocked
    pid2 = auth.save_repository_paper(
        title="deep learning in agriculture",
        authors="Dr. Jane Smith",
        domain="Agriculture",
        uploaded_by="admin",
        filename="dl_agri_copy.pdf",
        file_bytes=content_bytes,
        pdf_report_bytes=b"%PDF-1.4 REPORT",
        score=91.0,
        grade="A",
        allow_duplicate=False,
    )
    assert pid2 is None

    # Uploading with allow_duplicate=True (explicit override) succeeds
    pid3 = auth.save_repository_paper(
        title="Deep Learning in Agriculture",
        authors="Dr. Jane Smith",
        domain="Agriculture & Food Science",
        uploaded_by="admin",
        filename="dl_agri_v2.pdf",
        file_bytes=content_bytes,
        pdf_report_bytes=b"%PDF-1.4 REPORT",
        score=92.0,
        grade="A",
        allow_duplicate=True,
    )
    assert pid3 is not None

    dups = auth.find_repository_duplicates()
    assert len(dups) == 1
    assert dups[0]["count"] == 2

    ok_rem, _, rem_cnt = auth.remove_duplicate_repository_papers(current_admin_user="admin", confirm=True)
    assert ok_rem is True
    assert rem_cnt == 1
    assert len(auth.find_repository_duplicates()) == 0


# ===========================================================================
# 13. DISCIPLINE NORMALIZATION
# ===========================================================================
def test_discipline_normalization_canonical_labels():
    assert auth.normalize_discipline("Agri") == "Agriculture & Food Science"
    assert auth.normalize_discipline("agriculture") == "Agriculture & Food Science"
    assert auth.normalize_discipline("Agriculture & Food Science") == "Agriculture & Food Science"
    assert auth.normalize_discipline("CS") == "Computer Science & Artificial Intelligence"
    assert auth.normalize_discipline("Machine Learning") == "Computer Science & Artificial Intelligence"
    assert auth.normalize_discipline("Medical") == "Biomedical & Health Sciences"
    assert auth.normalize_discipline("Unknown Custom XYZ") in auth.CANONICAL_DISCIPLINES


# ===========================================================================
# 14. CSV FORMULA INJECTION SANITIZATION
# ===========================================================================
def test_csv_formula_injection_escaping(isolated_db):
    dangerous = "=cmd|' /C calc'!A0"
    escaped = auth.sanitize_csv_cell(dangerous)
    assert escaped.startswith("'=cmd")

    assert auth.sanitize_csv_cell("+SUM(A1:A10)").startswith("'+SUM")
    assert auth.sanitize_csv_cell("-2+3").startswith("'-2+3")
    assert auth.sanitize_csv_cell("@import").startswith("'@import")

    # Verify exported audit CSV escapes formula-prefixed usernames/details
    auth.record_audit_event("=evil_admin", "SYSTEM", "=target", "=cmd|' /C calc'!A0", "Success")
    csv_out = auth.export_audit_logs_csv(current_admin_user="admin")
    assert "'=evil_admin" in csv_out
    assert "'=cmd|" in csv_out


# ===========================================================================
# 15. IDEMPOTENT MIGRATIONS & SYSTEM HEALTH / DEPENDENCY CHECKS
# ===========================================================================
def test_migrations_idempotent_and_system_health(isolated_db):
    auth.signup_user("persist_user", "Pass1234!", "Student")
    # Run create_users_table(force=True) twice in a row
    auth.create_users_table(force=True)
    auth.create_users_table(force=True)

    # Verify zero data loss and all required tables exist
    conn = auth.get_db_connection()
    tables = {
        r["name"]
        for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    }
    conn.close()
    for required_table in (
        "users",
        "analysis_history",
        "login_history",
        "saved_papers",
        "upload_history",
        "app_errors",
        "processing_events",
        "app_settings",
        "account_lockouts",
    ):
        assert required_table in tables

    assert auth.get_user_role("persist_user") == "Student"

    # Check dependency checker and system status badge
    deps = auth.check_dependencies()
    assert len(deps) >= 6
    assert any(d["package"] == "streamlit" and d["status"] == "OK" for d in deps)

    status_label, status_reason = auth.compute_system_status_badge()
    assert status_label in ("Healthy", "Degraded", "Error", "Critical")
    assert bool(status_reason)

    # Check admin_panel exposes all 11 required view functions
    for fn_name in (
        "render_admin_dashboard",
        "render_all_users_view",
        "render_login_history_view",
        "render_saved_papers_view",
        "render_upload_history_view",
        "render_upload_research_paper_view",
        "render_analytics_view",
        "render_system_health_view",
        "render_storage_management_view",
        "render_platform_settings_view",
        "render_admin_about_view",
    ):
        assert hasattr(admin_panel, fn_name), f"Missing view function in admin_panel: {fn_name}"
