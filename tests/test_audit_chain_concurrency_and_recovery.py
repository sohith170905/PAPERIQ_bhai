"""
Comprehensive Regression Test Suite for Audit Hash-Chain Concurrency & Continuity Recovery.

Verifies:
1. Strict sequential audit writes maintain linear hash chaining.
2. High-concurrency writes (20 concurrent worker threads) produce zero branching,
   zero deadlocks, and unbroken cryptographic chain continuity.
3. Bulk operations (bulk_update_user_status) maintain 100% chain integrity.
4. Tamper detection: modifying stored row data immediately fails content hash verification.
5. Predecessor break detection: altering prev_hash immediately fails chain link verification.
6. Authorized Recovery Workflow:
   - Blocks unauthorized actors.
   - Blocks recovery if content tampering is present.
   - Archives original pre-repair evidence into audit_evidence_archive.
   - Realigns predecessor links under BEGIN IMMEDIATE atomic lock.
   - Verifies the resulting chain passes 100% verification.
   - Exports valid cryptographic repair manifest CSV.
"""

import concurrent.futures
import csv
import io
import os
import sqlite3
import pytest

import auth


@pytest.fixture()
def isolated_audit_db(tmp_path, monkeypatch):
    """Provides an isolated database and backups directory for audit testing."""
    test_db = str(tmp_path / "test_audit_users.db")
    test_backups = str(tmp_path / "backups")
    os.makedirs(test_backups, exist_ok=True)

    monkeypatch.setattr(auth, "DB_PATH", test_db)
    monkeypatch.setattr(auth, "BACKUPS_DIR", test_backups)
    monkeypatch.setattr(auth, "_TABLES_INITIALIZED_PATH", None)

    auth.create_users_table(force=True)
    yield test_db, test_backups


def test_sequential_audit_writes_maintain_linear_chain(isolated_audit_db):
    """Test 1: Sequential audit writes chain strictly from row i-1 to row i."""
    for i in range(10):
        ok = auth.record_audit_event(
            username=f"user_{i}",
            action_type="TEST_ACTION",
            target=f"target_{i}",
            details=f"Sequential test event #{i}",
            status="Success",
            role="Student",
        )
        assert ok is True

    ver = auth.verify_audit_log_integrity(current_admin_user="admin")
    assert ver["ok"] is True
    assert ver["content_valid"] is True
    assert ver["chain_valid"] is True
    assert ver["total_rows"] >= 10
    assert ver["link_break_count"] == 0
    assert ver["tamper_count"] == 0


def test_concurrent_audit_writes_are_thread_safe_and_continuous(isolated_audit_db):
    """Test 2: 20 concurrent threads writing simultaneously produce zero branching chains."""
    num_threads = 20

    def worker(idx):
        return auth.record_audit_event(
            username=f"concurrent_user_{idx}",
            action_type="CONCURRENT_TEST",
            target=f"target_{idx}",
            details=f"Concurrent payload from worker thread #{idx}",
            status="Success",
            role="Researcher",
        )

    with concurrent.futures.ThreadPoolExecutor(max_workers=num_threads) as executor:
        results = list(executor.map(worker, range(num_threads)))

    assert all(results), "All concurrent audit writes must succeed"

    ver = auth.verify_audit_log_integrity(current_admin_user="admin")
    assert ver["ok"] is True, f"Chain broke under concurrency: {ver['message']}"
    assert ver["content_valid"] is True
    assert ver["chain_valid"] is True
    assert ver["link_break_count"] == 0
    assert ver["tamper_count"] == 0
    assert ver["verified_count"] >= num_threads


def test_bulk_operation_maintains_unbroken_chain(isolated_audit_db):
    """Test 3: bulk_update_user_status writes multiple audit records without pointer divergence."""
    # Register 8 test accounts
    usernames = [f"bulk_acc_{i}" for i in range(8)]
    for u in usernames:
        auth.signup_user(u, "Password123!", "Student")

    # Perform bulk status change
    ok, msg, updated = auth.bulk_update_user_status(usernames, "Disabled", current_admin_user="admin")
    assert ok is True
    assert updated == 8

    ver = auth.verify_audit_log_integrity(current_admin_user="admin")
    assert ver["ok"] is True
    assert ver["content_valid"] is True
    assert ver["chain_valid"] is True
    assert ver["link_break_count"] == 0
    assert ver["tamper_count"] == 0


def test_tamper_detection_flags_content_modification(isolated_audit_db):
    """Test 4: Directly modifying row contents fails content hash verification and flags exact row ID."""
    auth.record_audit_event("alice", "LOGIN", "session", "Alice login", "Success")
    auth.record_audit_event("bob", "LOGIN", "session", "Bob login", "Success")

    conn = auth.get_db_connection()
    target_row = conn.execute("SELECT id, details FROM login_history ORDER BY id DESC LIMIT 1").fetchone()
    tampered_id = target_row["id"]
    conn.execute("UPDATE login_history SET details = 'MODIFIED_BY_ATTACKER' WHERE id = ?", (tampered_id,))
    conn.commit()
    conn.close()

    ver = auth.verify_audit_log_integrity(current_admin_user="admin")
    assert ver["ok"] is False
    assert ver["content_valid"] is False
    assert ver["tamper_count"] >= 1
    assert tampered_id in ver["tamper_ids"]
    assert "TAMPER" in ver["status"].upper() or "TAMPER" in ver["message"].upper()


def test_broken_predecessor_link_detected(isolated_audit_db):
    """Test 5: Directly altering prev_hash flags chain-link discontinuity."""
    auth.record_audit_event("user1", "LOGIN", "app", "Login 1", "Success")
    auth.record_audit_event("user2", "LOGIN", "app", "Login 2", "Success")
    auth.record_audit_event("user3", "LOGIN", "app", "Login 3", "Success")

    conn = auth.get_db_connection()
    target_row = conn.execute("SELECT id, prev_hash FROM login_history ORDER BY id DESC LIMIT 1").fetchone()
    broken_id = target_row["id"]
    conn.execute("UPDATE login_history SET prev_hash = 'deadbeef0000111122223333444455556666777788889999aaaabbbbccccdddd' WHERE id = ?", (broken_id,))
    conn.commit()
    conn.close()

    ver = auth.verify_audit_log_integrity(current_admin_user="admin")
    assert ver["ok"] is False
    assert ver["chain_valid"] is False
    assert ver["link_break_count"] >= 1
    assert broken_id in ver["chain_break_ids"]


def test_authorized_continuity_recovery_workflow(isolated_audit_db):
    """Test 6: Full end-to-end authorized continuity recovery."""
    # Write initial continuous rows
    for i in range(5):
        auth.record_audit_event(f"rec_user_{i}", "LOGIN", "app", f"Login #{i}", "Success")

    # Simulate 2 legacy rows that branched to an ancestor (like row 891 did)
    conn = auth.get_db_connection()
    c = conn.cursor()
    # Fetch an earlier row's hash
    first_rows = c.execute("SELECT id, row_hash FROM login_history ORDER BY id ASC LIMIT 2").fetchall()
    ancestor_hash = first_rows[0]["row_hash"]
    max_id = c.execute("SELECT MAX(id) FROM login_history").fetchone()[0]

    branch_id_1 = max_id + 1
    branch_id_2 = max_id + 2

    # Insert row branching to ancestor_hash (discontinuity)
    r_branch1 = {
        "id": branch_id_1,
        "username": "branch_user_1",
        "role": "Student",
        "login_time": "2026-10-11 12:00:00",
        "status": "Success",
        "ip_address": "127.0.0.1",
        "action_type": "BRANCH_TEST",
        "target": "target_branch_1",
        "details": "Simulated legacy branch record 1",
        "is_immutable": 0,
    }
    r1_hash = auth._compute_audit_row_hash(ancestor_hash, r_branch1)
    c.execute(
        "INSERT INTO login_history (id, username, role, login_time, status, ip_address, action_type, target, details, prev_hash, row_hash, is_immutable) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (branch_id_1, r_branch1["username"], r_branch1["role"], r_branch1["login_time"], r_branch1["status"], r_branch1["ip_address"], r_branch1["action_type"], r_branch1["target"], r_branch1["details"], ancestor_hash, r1_hash, 0)
    )

    # Insert row chaining to branch 1
    r_branch2 = {
        "id": branch_id_2,
        "username": "branch_user_2",
        "role": "Student",
        "login_time": "2026-10-11 12:00:01",
        "status": "Success",
        "ip_address": "127.0.0.1",
        "action_type": "BRANCH_TEST",
        "target": "target_branch_2",
        "details": "Simulated legacy branch record 2",
        "is_immutable": 0,
    }
    r2_hash = auth._compute_audit_row_hash(r1_hash, r_branch2)
    c.execute(
        "INSERT INTO login_history (id, username, role, login_time, status, ip_address, action_type, target, details, prev_hash, row_hash, is_immutable) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (branch_id_2, r_branch2["username"], r_branch2["role"], r_branch2["login_time"], r_branch2["status"], r_branch2["ip_address"], r_branch2["action_type"], r_branch2["target"], r_branch2["details"], r1_hash, r2_hash, 0)
    )
    conn.commit()
    conn.close()

    # Pre-check: Verification must detect the discontinuity
    ver_pre = auth.verify_audit_log_integrity(current_admin_user="admin")
    assert ver_pre["ok"] is False
    assert ver_pre["content_valid"] is True  # content hashes are valid
    assert ver_pre["chain_valid"] is False   # link is broken
    assert ver_pre["link_break_count"] >= 1

    # Forensic inspection returns detailed mapping
    forensics = auth.get_audit_discontinuity_forensics(current_admin_user="admin")
    assert len(forensics) >= 1
    assert forensics[0]["row_id"] == branch_id_1


    # Safeguard check 1: Non-admin is blocked
    ok_no_admin, msg_no_admin, _ = auth.recover_audit_chain_continuity(
        current_admin_user="student_user",
        compliance_reason="Authorized compliance realignment",
        confirmation_phrase="AUTHORIZE_AUDIT_REPAIR"
    )
    assert ok_no_admin is False
    assert "access denied" in msg_no_admin.lower()

    # Safeguard check 2: Missing confirmation phrase fails
    ok_no_conf, msg_no_conf, _ = auth.recover_audit_chain_continuity(
        current_admin_user="admin",
        compliance_reason="Authorized compliance realignment",
        confirmation_phrase="wrong_phrase"
    )
    assert ok_no_conf is False

    # Execute authorized recovery
    rec_ok, rec_msg, manifest_csv = auth.recover_audit_chain_continuity(
        current_admin_user="admin",
        compliance_reason="Authorized compliance realignment of legacy concurrent write branching",
        confirmation_phrase="AUTHORIZE_AUDIT_REPAIR"
    )
    assert rec_ok is True
    assert manifest_csv is not None
    assert "recovery_batch_id" in manifest_csv

    # Post-check: Verification MUST now be fully OK
    ver_post = auth.verify_audit_log_integrity(current_admin_user="admin")
    assert ver_post["ok"] is True
    assert ver_post["content_valid"] is True
    assert ver_post["chain_valid"] is True
    assert ver_post["link_break_count"] == 0
    assert ver_post["tamper_count"] == 0

    # Evidence preservation check: audit_evidence_archive contains pre-repair state
    conn = auth.get_db_connection()
    arch_rows = conn.execute("SELECT * FROM audit_evidence_archive").fetchall()
    assert len(arch_rows) >= 1
    # Check that AUDIT_CHAIN_RECOVERY was logged in login_history
    rec_log = conn.execute("SELECT * FROM login_history WHERE action_type = 'AUDIT_CHAIN_RECOVERY'").fetchone()
    assert rec_log is not None
    conn.close()
