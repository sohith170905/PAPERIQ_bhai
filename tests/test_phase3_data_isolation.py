import json
import os
import sys
import tempfile

import pytest

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

import app
import auth


@pytest.fixture
def isolated_db(monkeypatch):
    """Create a temporary SQLite database for data isolation tests so production users.db is untouched."""
    fd, temp_db_path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    monkeypatch.setattr(auth, "DB_PATH", temp_db_path)
    auth.create_users_table()
    yield temp_db_path
    try:
        os.remove(temp_db_path)
    except OSError:
        pass


def test_3_1_two_student_accounts_strict_record_isolation(isolated_db):
    """
    Create two student accounts (student_alice and student_bob) and prove that
    Account B cannot read, download, verify ownership of, or delete Account A's records.
    """
    ok_a, _ = auth.signup_user("student_alice", "alicepass123", "Student")
    ok_b, _ = auth.signup_user("student_bob", "bobpass123", "Student")
    assert ok_a is True
    assert ok_b is True

    # Alice saves an analysis record with PDF report bytes
    alice_pdf = b"%PDF-1.4 Alice private report"
    alice_record_id, _, _ = auth.save_analysis_record(
        username="student_alice",
        filename="Gangadharan45122023JEAI111549.pdf",
        domain="Agricultural & Food Sciences",
        score=84.5,
        pdf_bytes=alice_pdf,
        results_json=json.dumps({"overall_score": 84.5, "full_text": "Alice full paper text."}),
        display_title="Growth Performance of Nutri-Cereals in India",
        grade="A",
    )

    # Bob saves his own record
    bob_record_id, _, _ = auth.save_analysis_record(
        username="student_bob",
        filename="Bob_Paper.pdf",
        domain="Computer Science & AI",
        score=71.0,
        pdf_bytes=b"%PDF-1.4 Bob report",
        results_json=json.dumps({"overall_score": 71.0, "full_text": "Bob full paper text."}),
        display_title="Bob Independent Paper",
        grade="B",
    )

    # 1. History isolation: Alice only sees Alice's record; Bob only sees Bob's record
    alice_hist = auth.get_user_history("student_alice")
    bob_hist = auth.get_user_history("student_bob")
    assert len(alice_hist) == 1
    assert len(bob_hist) == 1
    assert alice_hist[0]["id"] == alice_record_id
    assert bob_hist[0]["id"] == bob_record_id
    assert alice_hist[0]["username"] == "student_alice"
    assert bob_hist[0]["username"] == "student_bob"

    # 2. Ownership verification: Bob cannot verify ownership of Alice's record
    assert auth.verify_analysis_ownership(alice_record_id, "student_alice") is True
    assert auth.verify_analysis_ownership(alice_record_id, "student_bob") is False
    assert auth.verify_analysis_ownership(alice_record_id, "") is False

    # 3. Direct record read isolation: Bob cannot read Alice's record by ID
    assert auth.get_analysis_record(alice_record_id, "student_alice") is not None
    assert auth.get_analysis_record(alice_record_id, "student_bob") is None
    assert auth.get_analysis_record(alice_record_id, None) is None

    # 4. Direct PDF report download isolation: Bob cannot download Alice's PDF report by ID
    assert auth.get_analysis_pdf_report(alice_record_id, "student_alice") == alice_pdf
    assert auth.get_analysis_pdf_report(alice_record_id, "student_bob") is None
    assert auth.get_analysis_pdf_report(alice_record_id, "") is None

    # 5. Session loader isolation: Bob cannot load Alice's record into session state
    app.st.session_state["username"] = "student_bob"
    app.st.session_state["user_data"] = {"username": "student_bob", "role": "Student"}
    app.clear_active_analysis_session()
    loaded = app.load_analysis_into_session(alice_hist[0], source="history")
    assert loaded is False
    assert not bool(app.st.session_state.get("analyzed"))

    # 6. Delete isolation: Bob cannot delete Alice's record or clear Alice's history
    del_ok, del_msg = auth.delete_analysis_record(alice_record_id, "student_bob")
    assert del_ok is False
    assert "Access Denied" in del_msg
    assert len(auth.get_user_history("student_alice")) == 1

    # Bob clearing his own history only deletes Bob's records, leaving Alice's intact
    clear_ok, _ = auth.clear_user_history("student_bob")
    assert clear_ok is True
    assert len(auth.get_user_history("student_bob")) == 0
    assert len(auth.get_user_history("student_alice")) == 1


def test_3_2_parameterized_queries_prevent_sql_injection(isolated_db):
    """Verify SQL injection payloads in username/record queries do not leak records."""
    auth.signup_user("student_safe", "safepass123", "Student")
    rec_id, _, _ = auth.save_analysis_record(
        username="student_safe",
        filename="Safe_Paper.pdf",
        domain="General Academic",
        score=80.0,
        pdf_bytes=b"%PDF-1.4",
    )
    injected_username = "' OR '1'='1"
    assert auth.get_user_history(injected_username) == []
    assert auth.get_analysis_record(rec_id, injected_username) is None
    assert auth.get_analysis_pdf_report(rec_id, injected_username) is None
    del_ok, _ = auth.delete_analysis_record(rec_id, injected_username)
    assert del_ok is False
