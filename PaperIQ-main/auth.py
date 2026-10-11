import sqlite3
import hashlib
import html
import os
import json
import uuid
import sys
import csv
import io
import time
from datetime import datetime


def _unescape_val(val):
    if val is None or not isinstance(val, str):
        return val
    out = val
    for _ in range(2):
        if "&" not in out:
            break
        out = html.unescape(out)
    return out


# Resolve database path relative to this file to avoid working directory issues
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "users.db")

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def hash_password(password):
    return hashlib.sha256(password.encode("utf-8")).hexdigest()

def create_users_table():
    conn = get_db_connection()
    c = conn.cursor()
    # Users table
    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            username TEXT PRIMARY KEY,
            password TEXT,
            role TEXT DEFAULT 'Student',
            theme_preference TEXT DEFAULT 'System',
            created_at TEXT DEFAULT '2026-03-01 00:00:00',
            status TEXT DEFAULT 'Active'
        )
    """)
    # Ensure all users columns exist for safe schema migrations
    c.execute("PRAGMA table_info(users)")
    cols = [col["name"] for col in c.fetchall()]
    if "role" not in cols:
        try:
            c.execute("ALTER TABLE users ADD COLUMN role TEXT DEFAULT 'Student'")
        except Exception:
            pass
    if "theme_preference" not in cols:
        try:
            c.execute("ALTER TABLE users ADD COLUMN theme_preference TEXT DEFAULT 'System'")
        except Exception:
            pass
    if "created_at" not in cols:
        try:
            c.execute("ALTER TABLE users ADD COLUMN created_at TEXT DEFAULT '2026-03-01 00:00:00'")
        except Exception:
            pass
    if "status" not in cols:
        try:
            c.execute("ALTER TABLE users ADD COLUMN status TEXT DEFAULT 'Active'")
        except Exception:
            pass

    # Ensure existing rows have non-null status and created_at
    try:
        c.execute("UPDATE users SET status = 'Active' WHERE status IS NULL OR status = ''")
        c.execute("UPDATE users SET created_at = '2026-03-01 00:00:00' WHERE created_at IS NULL OR created_at = ''")
    except Exception:
        pass

    # Persistent analysis history table
    c.execute("""
        CREATE TABLE IF NOT EXISTS analysis_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            analysis_id TEXT,
            username TEXT,
            filename TEXT,
            original_filename TEXT,
            display_title TEXT,
            report_filename TEXT,
            domain TEXT,
            score REAL,
            grade TEXT,
            document_hash TEXT,
            language_score REAL,
            coherence_score REAL,
            argumentation_score REAL,
            academic_style_score REAL,
            readability_score REAL,
            pdf_data BLOB,
            created_at TEXT,
            results_json TEXT
        )
    """)
    
    # Ensure all columns exist for schema migrations
    c.execute("PRAGMA table_info(analysis_history)")
    h_cols = [col["name"] for col in c.fetchall()]
    
    columns_to_ensure = [
        ("analysis_id", "TEXT"),
        ("original_filename", "TEXT"),
        ("display_title", "TEXT"),
        ("report_filename", "TEXT"),
        ("grade", "TEXT"),
        ("document_hash", "TEXT"),
        ("language_score", "REAL"),
        ("coherence_score", "REAL"),
        ("argumentation_score", "REAL"),
        ("academic_style_score", "REAL"),
        ("readability_score", "REAL"),
        ("results_json", "TEXT")
    ]
    for col_name, col_type in columns_to_ensure:
        if col_name not in h_cols:
            try:
                c.execute(f"ALTER TABLE analysis_history ADD COLUMN {col_name} {col_type}")
            except Exception:
                pass

    # Login History Table (Audit Log)
    c.execute("""
        CREATE TABLE IF NOT EXISTS login_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT,
            role TEXT,
            login_time TEXT,
            status TEXT DEFAULT 'Success',
            ip_address TEXT DEFAULT '127.0.0.1',
            action_type TEXT DEFAULT 'AUTH',
            target TEXT DEFAULT '',
            details TEXT DEFAULT ''
        )
    """)

    # Ensure all columns exist in login_history for audit enhancements
    c.execute("PRAGMA table_info(login_history)")
    lh_cols = [col["name"] for col in c.fetchall()]
    if "action_type" not in lh_cols:
        try:
            c.execute("ALTER TABLE login_history ADD COLUMN action_type TEXT DEFAULT 'AUTH'")
        except Exception:
            pass
    if "target" not in lh_cols:
        try:
            c.execute("ALTER TABLE login_history ADD COLUMN target TEXT DEFAULT ''")
        except Exception:
            pass
    if "details" not in lh_cols:
        try:
            c.execute("ALTER TABLE login_history ADD COLUMN details TEXT DEFAULT ''")
        except Exception:
            pass

    # Saved Papers Repository Table (Institutional Shared Library)
    c.execute("""
        CREATE TABLE IF NOT EXISTS saved_papers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            paper_id TEXT UNIQUE,
            title TEXT,
            authors TEXT,
            domain TEXT,
            uploaded_by TEXT,
            uploaded_at TEXT,
            filename TEXT,
            file_bytes BLOB,
            pdf_report_bytes BLOB,
            score REAL,
            grade TEXT,
            results_json TEXT,
            is_public INTEGER DEFAULT 1
        )
    """)

    # Upload History Table
    c.execute("""
        CREATE TABLE IF NOT EXISTS upload_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT,
            filename TEXT,
            file_type TEXT,
            file_size_kb REAL,
            upload_time TEXT,
            status TEXT DEFAULT 'Processed',
            target TEXT DEFAULT 'Personal'
        )
    """)

    # Performance & Lookup Indexes
    indexes = [
        ("idx_users_role", "users(role)"),
        ("idx_users_status", "users(status)"),
        ("idx_login_time", "login_history(login_time)"),
        ("idx_login_user", "login_history(username)"),
        ("idx_login_action", "login_history(action_type)"),
        ("idx_saved_papers_uploaded_at", "saved_papers(uploaded_at)"),
        ("idx_analysis_user", "analysis_history(username)"),
        ("idx_analysis_created", "analysis_history(created_at)"),
        ("idx_upload_history_time", "upload_history(upload_time)")
    ]
    for idx_name, idx_target in indexes:
        try:
            c.execute(f"CREATE INDEX IF NOT EXISTS {idx_name} ON {idx_target}")
        except Exception:
            pass

    # Safe Administrator Bootstrap: Ensure at least one Administrator exists
    c.execute("SELECT username FROM users WHERE role = 'Administrator'")
    admin_exists = c.fetchone()
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    if not admin_exists:
        c.execute("SELECT username FROM users WHERE username = 'admin'")
        existing_admin_user = c.fetchone()
        if not existing_admin_user:
            c.execute(
                "INSERT INTO users (username, password, role, theme_preference, created_at, status) VALUES (?, ?, 'Administrator', 'System', ?, 'Active')",
                ("admin", hash_password("AdminSecure2026!"), now_str)
            )
            c.execute(
                """
                INSERT INTO login_history (username, role, login_time, status, ip_address, action_type, target, details)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                ("admin", "Administrator", now_str, "System Bootstrap Provisioned", "127.0.0.1", "SYSTEM_BOOTSTRAP", "admin", "Primary Administrator Account Created")
            )
        else:
            c.execute("UPDATE users SET role = 'Administrator', status = 'Active' WHERE username = 'admin'")

    # Backfill users created_at from their earliest recorded activity if available
    try:
        c.execute("SELECT username FROM users WHERE created_at = '2026-03-01 00:00:00' OR created_at IS NULL")
        for u_row in c.fetchall():
            u_name = u_row["username"]
            c.execute("SELECT login_time FROM login_history WHERE username = ? ORDER BY id ASC LIMIT 1", (u_name,))
            earliest = c.fetchone()
            if earliest and earliest["login_time"]:
                c.execute("UPDATE users SET created_at = ? WHERE username = ?", (earliest["login_time"], u_name))
    except Exception:
        pass

    conn.commit()
    conn.close()

# ---------------------------------------------------------------------------
# AUDIT LOGGING MODULE
# ---------------------------------------------------------------------------
def record_audit_event(username, action_type="AUTH", target="", details="", status="Success", role=None, ip="127.0.0.1"):
    """
    Inserts a structured audit event into login_history.
    Sensitive credentials and hashes are NEVER recorded.
    """
    try:
        create_users_table()
        conn = get_db_connection()
        c = conn.cursor()
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        clean_user = username.strip() if username else "system"
        if not role:
            try:
                c.execute("SELECT role FROM users WHERE username = ?", (clean_user,))
                r_row = c.fetchone()
                role = r_row["role"] if r_row else "Unknown"
            except Exception:
                role = "Unknown"
        c.execute(
            """
            INSERT INTO login_history (username, role, login_time, status, ip_address, action_type, target, details)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (clean_user, str(role).strip(), now_str, str(status).strip(), str(ip).strip(), str(action_type).strip(), str(target).strip(), str(details).strip())
        )
        conn.commit()
        conn.close()
        return True
    except Exception:
        return False

def record_login(username, role, status="Success", ip="127.0.0.1"):
    """Backward-compatible wrapper for record_audit_event."""
    return record_audit_event(username=username, action_type="LOGIN", status=status, role=role, ip=ip)

def get_login_history(limit=500, action_type=None, username=None, status=None):
    """Retrieves audit trail with optional filtering, sorted newest first."""
    create_users_table()
    conn = get_db_connection()
    c = conn.cursor()
    query = "SELECT * FROM login_history WHERE 1=1"
    params = []
    if action_type and action_type != "All Action Types":
        query += " AND action_type = ?"
        params.append(action_type)
    if username:
        query += " AND username LIKE ?"
        params.append(f"%{username.strip()}%")
    if status and status != "All Statuses":
        query += " AND status = ?"
        params.append(status)
    query += " ORDER BY id DESC LIMIT ?"
    params.append(limit)
    c.execute(query, params)
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    return rows

def get_user_role(username):
    """Fetches verified user role directly from SQLite database."""
    if not username:
        return None
    try:
        conn = get_db_connection()
        c = conn.cursor()
        c.execute("SELECT role, status FROM users WHERE username = ?", (str(username).strip(),))
        row = c.fetchone()
        conn.close()
        if row and row["status"] != "Disabled":
            return row["role"]
        return None
    except Exception:
        return None

def is_admin_user(username):
    """Strict verification of administrator privileges directly against database."""
    role = get_user_role(username)
    return role in ["Administrator", "Admin"]

def is_researcher_user(username):
    """Strict verification of researcher privileges directly against database."""
    role = get_user_role(username)
    return role in ["Researcher", "researcher"]

def verify_analysis_ownership(record_id, username):
    """
    Verifies that the given user strictly owns the specified analysis record.
    Guards against cross-account data leakage, tampering, or deletion.
    """
    if not record_id or not username:
        return False
    try:
        conn = get_db_connection()
        c = conn.cursor()
        c.execute(
            "SELECT username FROM analysis_history WHERE (id = ? OR analysis_id = ?)",
            (record_id, str(record_id))
        )
        row = c.fetchone()
        conn.close()
        return bool(row and row["username"] == str(username).strip())
    except Exception:
        return False

def get_analysis_record(record_id, username=None):
    """
    Retrieves a single analysis record with strict ownership verification in the data-access layer.
    If username is missing or does not own the record (and is not an Administrator), returns None.
    """
    clean_user = str(username).strip() if username else ""
    if not record_id or not clean_user:
        return None
    try:
        create_users_table()
        conn = get_db_connection()
        c = conn.cursor()
        if is_admin_user(clean_user):
            c.execute(
                "SELECT * FROM analysis_history WHERE (id = ? OR analysis_id = ?)",
                (record_id, str(record_id))
            )
        else:
            c.execute(
                "SELECT * FROM analysis_history WHERE (id = ? OR analysis_id = ?) AND username = ?",
                (record_id, str(record_id), clean_user)
            )
        row = c.fetchone()
        conn.close()
        if not row:
            record_audit_event(
                username=clean_user,
                action_type="UNAUTHORIZED_ACCESS",
                target=f"analysis_id={record_id}",
                details="Blocked attempt to read/view an analysis record not owned by user",
                status="Denied"
            )
            return None
        row_dict = dict(row)
        return {
            "id": row_dict.get("id"),
            "analysis_id": row_dict.get("analysis_id"),
            "username": row_dict.get("username"),
            "filename": row_dict.get("filename"),
            "original_filename": row_dict.get("original_filename"),
            "display_title": row_dict.get("display_title"),
            "report_filename": row_dict.get("report_filename"),
            "domain": row_dict.get("domain"),
            "score": float(row_dict.get("score", 0.0)),
            "grade": row_dict.get("grade"),
            "document_hash": row_dict.get("document_hash"),
            "language_score": row_dict.get("language_score"),
            "coherence_score": row_dict.get("coherence_score"),
            "argumentation_score": row_dict.get("argumentation_score"),
            "academic_style_score": row_dict.get("academic_style_score"),
            "readability_score": row_dict.get("readability_score"),
            "pdf": bytes(row_dict["pdf_data"]) if row_dict.get("pdf_data") else b"",
            "created_at": row_dict.get("created_at"),
            "results_json": row_dict.get("results_json")
        }
    except Exception:
        return None

def get_analysis_pdf_report(record_id, username):
    """
    Phase 3: Retrieves PDF report bytes for a record only after verifying record ownership
    in the data-access layer. Returns None if unauthorized.
    """
    rec = get_analysis_record(record_id, username=username)
    if not rec:
        return None
    return rec.get("pdf") or b""

def clear_login_history(current_admin_user=None):
    """Authorized audit purge with an immutable self-record and strict administrator verification."""
    if not is_admin_user(current_admin_user):
        record_audit_event(
            username=current_admin_user or "unknown",
            action_type="UNAUTHORIZED_ACCESS",
            target="login_history",
            details="Unauthorized attempt to purge audit log",
            status="Denied"
        )
        return False, "Access Denied: Administrator role required."
    try:
        create_users_table()
        conn = get_db_connection()
        c = conn.cursor()
        c.execute("DELETE FROM login_history")
        conn.commit()
        conn.close()
        # Record self-contained audit event of this purge
        record_audit_event(
            username=current_admin_user or "admin",
            action_type="LOG_PURGE",
            target="login_history",
            details=f"Audit trail purged by {current_admin_user or 'admin'}",
            status="Audit Cleared"
        )
        return True, "Login history cleared successfully."
    except Exception as e:
        return False, str(e)

# ---------------------------------------------------------------------------
# AUTHENTICATION & USER MANAGEMENT
# ---------------------------------------------------------------------------
def signup_user(username, password, role="Student", ip="127.0.0.1"):
    create_users_table()
    conn = get_db_connection()
    c = conn.cursor()
    clean_user = username.strip()
    c.execute("SELECT username FROM users WHERE username = ?", (clean_user,))
    existing = c.fetchone()
    if existing:
        conn.close()
        return False, "Username already exists. Please choose another."
    
    clean_role = role.strip()
    # Public registration strictly accepts Student or Researcher
    if clean_role not in ["Student", "Researcher"]:
        if "student" in clean_role.lower():
            clean_role = "Student"
        elif "researcher" in clean_role.lower():
            clean_role = "Researcher"
        else:
            clean_role = "Student"

    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    c.execute(
        "INSERT INTO users (username, password, role, created_at, status) VALUES (?, ?, ?, ?, 'Active')",
        (clean_user, hash_password(password), clean_role, now_str)
    )
    conn.commit()
    conn.close()
    
    record_audit_event(
        username=clean_user,
        action_type="REGISTRATION",
        target=clean_user,
        details=f"New {clean_role} registered",
        status="Account Registered",
        role=clean_role,
        ip=ip
    )
    return True, "Account created successfully!"

def login_user(username, password, ip="127.0.0.1"):
    create_users_table()
    conn = get_db_connection()
    c = conn.cursor()
    clean_user = username.strip()
    c.execute(
        "SELECT username, role, theme_preference, status FROM users WHERE username = ? AND password = ?",
        (clean_user, hash_password(password))
    )
    user = c.fetchone()
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    if user:
        role = user["role"] if user["role"] else "Student"
        status = user["status"] if "status" in user.keys() and user["status"] else "Active"
        theme = "System"
        try:
            if "theme_preference" in user.keys() and user["theme_preference"]:
                theme = user["theme_preference"]
        except Exception:
            theme = "System"
        conn.close()

        # Check account status (Active vs Disabled)
        if status == "Disabled":
            record_audit_event(
                username=clean_user,
                action_type="LOGIN",
                target=clean_user,
                details="Login denied: Account is deactivated by an administrator",
                status="Failed: Account Disabled",
                role=role,
                ip=ip
            )
            return {
                "username": user["username"],
                "role": role,
                "status": "Disabled",
                "disabled": True
            }

        # Successful login event
        record_audit_event(
            username=clean_user,
            action_type="LOGIN",
            target=clean_user,
            details="User authenticated successfully",
            status="Success",
            role=role,
            ip=ip
        )
        return {
            "username": user["username"],
            "role": role,
            "theme_preference": theme,
            "status": "Active"
        }
    else:
        conn.close()
        # Record failed attempt without password
        record_audit_event(
            username=clean_user,
            action_type="LOGIN",
            target=clean_user,
            details="Invalid username or password supplied",
            status="Failed: Invalid Credentials",
            role="Unknown",
            ip=ip
        )
        return None

def update_user_theme(username, theme_preference):
    """Persists user theme preference in database."""
    create_users_table()
    conn = get_db_connection()
    c = conn.cursor()
    c.execute(
        "UPDATE users SET theme_preference = ? WHERE username = ?",
        (theme_preference, username.strip())
    )
    conn.commit()
    conn.close()
    return True

def get_user_theme(username):
    """Retrieves user theme preference from database."""
    create_users_table()
    conn = get_db_connection()
    c = conn.cursor()
    c.execute(
        "SELECT theme_preference FROM users WHERE username = ?",
        (username.strip(),)
    )
    user = c.fetchone()
    conn.close()
    if user:
        try:
            if "theme_preference" in user.keys() and user["theme_preference"]:
                return user["theme_preference"]
        except Exception:
            pass
    return "System"

def get_all_users():
    """Retrieves all registered users with metadata and analysis counts."""
    create_users_table()
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("""
        SELECT u.username, u.role, u.theme_preference, u.created_at, u.status,
               COUNT(ah.id) as analysis_count
        FROM users u
        LEFT JOIN analysis_history ah ON u.username = ah.username
        GROUP BY u.username, u.role, u.theme_preference, u.created_at, u.status
        ORDER BY u.created_at DESC, u.username ASC
    """)
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    return rows

def toggle_user_status(username, new_status, current_admin_user):
    """Enables or disables a user account with self-lockout safeguards and administrator verification."""
    clean_user = username.strip() if username else ""
    if not is_admin_user(current_admin_user):
        record_audit_event(
            username=current_admin_user or "unknown",
            action_type="UNAUTHORIZED_ACCESS",
            target=clean_user,
            details="Unauthorized attempt to modify user account status",
            status="Denied"
        )
        return False, "Access Denied: Administrator role required."
    if clean_user == current_admin_user:
        return False, "Self-lockout safeguard: You cannot deactivate your own currently active Administrator account."
    create_users_table()
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT role, status FROM users WHERE username = ?", (clean_user,))
    row = c.fetchone()
    if not row:
        conn.close()
        return False, f"User '{clean_user}' not found."
    if row["role"] == "Administrator" and new_status == "Disabled":
        c.execute("SELECT COUNT(*) FROM users WHERE role = 'Administrator' AND status != 'Disabled'")
        active_admins = c.fetchone()[0]
        if active_admins <= 1:
            conn.close()
            return False, "Safeguard: Cannot deactivate the only remaining active Administrator account."
    c.execute("UPDATE users SET status = ? WHERE username = ?", (new_status, clean_user))
    conn.commit()
    conn.close()
    record_audit_event(
        username=current_admin_user,
        action_type="STATUS_CHANGE",
        target=clean_user,
        details=f"Account status of '{clean_user}' changed to '{new_status}'",
        status="Success"
    )
    return True, f"Account '{clean_user}' is now {new_status}."

def update_user_role(username, new_role, current_admin_user=None):
    """Updates user academic role with last-admin demotion safeguards and administrator verification."""
    clean_user = username.strip() if username else ""
    if not is_admin_user(current_admin_user):
        record_audit_event(
            username=current_admin_user or "unknown",
            action_type="UNAUTHORIZED_ACCESS",
            target=clean_user,
            details=f"Unauthorized attempt to modify academic role to '{new_role}'",
            status="Denied"
        )
        return False, "Access Denied: Administrator role required."
    create_users_table()
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT role FROM users WHERE username = ?", (clean_user,))
    row = c.fetchone()
    if not row:
        conn.close()
        return False, f"User '{clean_user}' not found."
    if row["role"] == "Administrator" and new_role != "Administrator":
        c.execute("SELECT COUNT(*) FROM users WHERE role = 'Administrator' AND status != 'Disabled'")
        active_admins = c.fetchone()[0]
        if active_admins <= 1:
            conn.close()
            return False, "Safeguard: Cannot demote the only remaining active Administrator account."
    c.execute("UPDATE users SET role = ? WHERE username = ?", (new_role.strip(), clean_user))
    conn.commit()
    conn.close()
    record_audit_event(
        username=current_admin_user or "admin",
        action_type="ROLE_CHANGE",
        target=clean_user,
        details=f"Academic role for '{clean_user}' changed from '{row['role']}' to '{new_role}'",
        status="Success"
    )
    return True, f"Role for '{clean_user}' updated to '{new_role}'."

def admin_reset_password(username, new_password, current_admin_user=None):
    """Sets a new password for a user with administrator verification."""
    clean_user = username.strip() if username else ""
    if not is_admin_user(current_admin_user):
        record_audit_event(
            username=current_admin_user or "unknown",
            action_type="UNAUTHORIZED_ACCESS",
            target=clean_user,
            details="Unauthorized attempt to reset user password",
            status="Denied"
        )
        return False, "Access Denied: Administrator role required."
    if len(new_password) < 4:
        return False, "Password must be at least 4 characters."
    try:
        create_users_table()
        conn = get_db_connection()
        c = conn.cursor()
        c.execute("UPDATE users SET password = ? WHERE username = ?", (hash_password(new_password), clean_user))
        conn.commit()
        conn.close()
        record_audit_event(
            username=current_admin_user or "admin",
            action_type="PASSWORD_RESET",
            target=clean_user,
            details=f"Password reset performed for account '{clean_user}'",
            status="Success"
        )
        return True, f"Password for '{clean_user}' reset successfully."
    except Exception as e:
        return False, str(e)

def delete_user_account(username, current_admin_user=None):
    """Permanently deletes user account and cascading data with safeguards and administrator verification."""
    clean_user = username.strip() if username else ""
    if not is_admin_user(current_admin_user):
        record_audit_event(
            username=current_admin_user or "unknown",
            action_type="UNAUTHORIZED_ACCESS",
            target=clean_user,
            details="Unauthorized attempt to delete user account",
            status="Denied"
        )
        return False, "Access Denied: Administrator role required."
    if current_admin_user and clean_user == current_admin_user:
        return False, "Self-lockout safeguard: You cannot delete your own currently active Administrator account."
    try:
        create_users_table()
        conn = get_db_connection()
        c = conn.cursor()
        c.execute("SELECT role FROM users WHERE username = ?", (clean_user,))
        row = c.fetchone()
        if not row:
            conn.close()
            return False, f"User '{clean_user}' not found."
        if row["role"] == "Administrator":
            c.execute("SELECT COUNT(*) FROM users WHERE role = 'Administrator'")
            cnt = c.fetchone()[0]
            if cnt <= 1:
                conn.close()
                return False, "Safeguard: Cannot delete the only remaining Administrator account."
        c.execute("DELETE FROM users WHERE username = ?", (clean_user,))
        c.execute("DELETE FROM analysis_history WHERE username = ?", (clean_user,))
        conn.commit()
        conn.close()
        record_audit_event(
            username=current_admin_user or "admin",
            action_type="USER_DELETE",
            target=clean_user,
            details=f"Account '{clean_user}' and associated analysis history permanently deleted",
            status="Success"
        )
        return True, f"User account '{clean_user}' and associated data deleted successfully."
    except Exception as e:
        return False, str(e)

def provision_admin(username, password):
    if not username or len(username.strip()) < 3:
        return False, "Administrator username must be at least 3 characters."
    if not password or len(password) < 6:
        return False, "Administrator password must be at least 6 characters."
    create_users_table()
    conn = get_db_connection()
    c = conn.cursor()
    u = username.strip()
    c.execute("SELECT username FROM users WHERE username = ?", (u,))
    existing = c.fetchone()
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    if existing:
        c.execute("UPDATE users SET password = ?, role = 'Administrator', status = 'Active' WHERE username = ?", (hash_password(password), u))
    else:
        c.execute("INSERT INTO users (username, password, role, theme_preference, created_at, status) VALUES (?, ?, 'Administrator', 'System', ?, 'Active')", (u, hash_password(password), now_str))
    conn.commit()
    conn.close()
    record_audit_event(
        username=u,
        action_type="SYSTEM_BOOTSTRAP",
        target=u,
        details=f"Administrator account '{u}' provisioned",
        status="Admin Provisioned"
    )
    return True, f"Administrator account '{u}' successfully provisioned."

# ---------------------------------------------------------------------------
# ANALYSIS HISTORY MODULE
# ---------------------------------------------------------------------------
def save_analysis_record(
    username,
    filename,
    domain,
    score,
    pdf_bytes,
    results_json=None,
    analysis_id=None,
    display_title=None,
    report_filename=None,
    document_hash=None,
    grade=None,
    dimension_scores=None
):
    create_users_table()
    conn = get_db_connection()
    c = conn.cursor()
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    if not analysis_id:
        analysis_id = f"ANL-{uuid.uuid4().hex[:10].upper()}"
        
    c.execute("SELECT id FROM analysis_history WHERE analysis_id = ? AND username = ?", (analysis_id, username))
    existing_rec = c.fetchone()
    if existing_rec:
        record_id = existing_rec["id"]
        conn.close()
        return record_id, now_str, analysis_id
        
    dim = dimension_scores or {}
    l_sc = dim.get("Language Quality", dim.get("Language", score))
    c_sc = dim.get("Structural Coherence", dim.get("Coherence", score))
    a_sc = dim.get("Argumentation", dim.get("Reasoning", score))
    s_sc = dim.get("Academic Style", dim.get("Sophistication", score))
    r_sc = dim.get("Readability", score)
    
    clean_fn = _unescape_val(filename)
    clean_disp_title = _unescape_val(display_title)
    clean_domain = _unescape_val(domain)
    clean_results_json = _unescape_val(results_json)

    c.execute(
        """
        INSERT INTO analysis_history (
            analysis_id, username, filename, original_filename, display_title,
            report_filename, domain, score, grade, document_hash,
            language_score, coherence_score, argumentation_score, academic_style_score, readability_score,
            pdf_data, created_at, results_json
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            analysis_id,
            username,
            clean_fn,
            clean_fn,
            clean_disp_title,
            report_filename,
            clean_domain,
            float(score),
            grade,
            document_hash,
            float(l_sc),
            float(c_sc),
            float(a_sc),
            float(s_sc),
            float(r_sc),
            pdf_bytes,
            now_str,
            clean_results_json
        )
    )
    conn.commit()
    record_id = c.lastrowid
    conn.close()
    return record_id, now_str, analysis_id

def get_user_history(username):
    create_users_table()
    conn = get_db_connection()
    c = conn.cursor()
    c.execute(
        """
        SELECT *
        FROM analysis_history
        WHERE username = ?
        ORDER BY id DESC
        """,
        (username,)
    )
    rows = c.fetchall()
    conn.close()
    history = []
    for r in rows:
        row_dict = dict(r)
        rec = {
            "id": row_dict.get("id"),
            "analysis_id": row_dict.get("analysis_id") or f"ANL-{row_dict.get('id')}",
            "username": row_dict.get("username"),
            "filename": _unescape_val(row_dict.get("filename", "Paper.pdf")),
            "original_filename": _unescape_val(row_dict.get("original_filename") or row_dict.get("filename", "Paper.pdf")),
            "display_title": _unescape_val(row_dict.get("display_title")),
            "report_filename": row_dict.get("report_filename"),
            "domain": _unescape_val(row_dict.get("domain", "General Academic")),
            "score": float(row_dict.get("score", 0.0)),
            "grade": row_dict.get("grade"),
            "document_hash": row_dict.get("document_hash"),
            "language_score": row_dict.get("language_score"),
            "coherence_score": row_dict.get("coherence_score"),
            "argumentation_score": row_dict.get("argumentation_score"),
            "academic_style_score": row_dict.get("academic_style_score"),
            "readability_score": row_dict.get("readability_score"),
            "pdf": bytes(row_dict["pdf_data"]) if row_dict.get("pdf_data") else b"",
            "created_at": row_dict.get("created_at"),
            "results_json": _unescape_val(row_dict.get("results_json"))
        }
        history.append(rec)
    return history

def delete_analysis_record(record_id, username):
    try:
        clean_user = str(username).strip() if username else ""
        if not clean_user or not verify_analysis_ownership(record_id, clean_user):
            record_audit_event(
                username=clean_user or "unknown",
                action_type="UNAUTHORIZED_ACCESS",
                target=f"analysis_id={record_id}",
                details="Unauthorized attempt to delete an analysis record not owned by user",
                status="Denied"
            )
            return False, "Access Denied: You can only delete your own analysis records."
        create_users_table()
        conn = get_db_connection()
        c = conn.cursor()
        c.execute(
            "DELETE FROM analysis_history WHERE (id = ? OR analysis_id = ?) AND username = ?",
            (record_id, str(record_id), clean_user)
        )
        conn.commit()
        conn.close()
        return True, "Analysis record deleted successfully."
    except Exception as e:
        return False, str(e)

def clear_user_history(username):
    try:
        create_users_table()
        conn = get_db_connection()
        c = conn.cursor()
        c.execute(
            "DELETE FROM analysis_history WHERE username = ?",
            (username,)
        )
        conn.commit()
        conn.close()
        return True, "All analysis history cleared successfully."
    except Exception as e:
        return False, str(e)

def get_all_analyses_summary():
    """Returns domain, score, grade, created_at for all analyses across all users."""
    try:
        create_users_table()
        conn = get_db_connection()
        c = conn.cursor()
        c.execute("SELECT id, username, filename, domain, score, grade, created_at FROM analysis_history ORDER BY id DESC")
        rows = [dict(r) for r in c.fetchall()]
        conn.close()
        return rows
    except Exception:
        return []

# ---------------------------------------------------------------------------
# UPLOAD HISTORY MODULE
# ---------------------------------------------------------------------------
def record_upload(username, filename, file_type, file_size_kb, status="Processed", target="Personal"):
    try:
        create_users_table()
        conn = get_db_connection()
        c = conn.cursor()
        
        # Debounce safeguard: prevent duplicate audit logs from rapid reruns within 5 seconds
        c.execute(
            """
            SELECT upload_time FROM upload_history 
            WHERE username = ? AND filename = ? AND target = ? 
            ORDER BY id DESC LIMIT 1
            """,
            (username.strip(), filename.strip(), target)
        )
        last_rec = c.fetchone()
        if last_rec and last_rec[0]:
            try:
                last_dt = datetime.strptime(last_rec[0], "%Y-%m-%d %H:%M:%S")
                if (datetime.now() - last_dt).total_seconds() < 5:
                    conn.close()
                    return True
            except Exception:
                pass

        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        c.execute(
            """
            INSERT INTO upload_history (username, filename, file_type, file_size_kb, upload_time, status, target)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (username.strip(), filename.strip(), file_type.strip(), float(file_size_kb), now_str, status, target)
        )
        conn.commit()
        conn.close()
        return True
    except Exception:
        return False

def get_upload_history(username=None, limit=250):
    create_users_table()
    conn = get_db_connection()
    c = conn.cursor()
    if username:
        c.execute("SELECT * FROM upload_history WHERE username = ? ORDER BY id DESC LIMIT ?", (username, limit))
    else:
        c.execute("SELECT * FROM upload_history ORDER BY id DESC LIMIT ?", (limit,))
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    return rows

# ---------------------------------------------------------------------------
# SAVED PAPERS (INSTITUTIONAL SHARED REPOSITORY) MODULE
# ---------------------------------------------------------------------------
def save_repository_paper(title, authors, domain, uploaded_by, filename, file_bytes, pdf_report_bytes, score, grade, results_json=None, is_public=1):
    create_users_table()
    conn = get_db_connection()
    c = conn.cursor()
    paper_id = f"LIB-{uuid.uuid4().hex[:8].upper()}"
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    c.execute(
        """
        INSERT INTO saved_papers (
            paper_id, title, authors, domain, uploaded_by, uploaded_at,
            filename, file_bytes, pdf_report_bytes, score, grade, results_json, is_public
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            paper_id,
            title.strip() if title else filename.strip(),
            authors.strip() if authors else "Institutional Authors",
            domain.strip() if domain else "General Academic",
            uploaded_by.strip(),
            now_str,
            filename.strip(),
            file_bytes,
            pdf_report_bytes,
            float(score),
            grade,
            results_json,
            int(is_public)
        )
    )
    conn.commit()
    conn.close()
    record_audit_event(
        username=uploaded_by,
        action_type="REPOSITORY_UPLOAD",
        target=paper_id,
        details=f"Manuscript '{title or filename}' added to institutional repository",
        status="Success"
    )
    return paper_id

def get_saved_papers():
    create_users_table()
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM saved_papers ORDER BY id DESC")
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    return rows

def get_saved_paper(paper_id):
    create_users_table()
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM saved_papers WHERE paper_id = ? OR id = ?", (paper_id, str(paper_id)))
    row = c.fetchone()
    conn.close()
    return dict(row) if row else None

def delete_saved_paper(paper_id, current_admin_user=None):
    if not is_admin_user(current_admin_user):
        record_audit_event(
            username=current_admin_user or "unknown",
            action_type="UNAUTHORIZED_ACCESS",
            target=str(paper_id),
            details="Unauthorized attempt to remove repository paper",
            status="Denied"
        )
        return False, "Access Denied: Administrator role required."
    try:
        create_users_table()
        conn = get_db_connection()
        c = conn.cursor()
        c.execute("SELECT title FROM saved_papers WHERE paper_id = ? OR id = ?", (paper_id, str(paper_id)))
        row = c.fetchone()
        title = row["title"] if row else paper_id
        c.execute("DELETE FROM saved_papers WHERE paper_id = ? OR id = ?", (paper_id, str(paper_id)))
        conn.commit()
        conn.close()
        record_audit_event(
            username=current_admin_user or "admin",
            action_type="REPOSITORY_DELETE",
            target=str(paper_id),
            details=f"Manuscript '{title}' removed from repository",
            status="Success"
        )
        return True, "Paper removed from institutional repository."
    except Exception as e:
        return False, str(e)

# ---------------------------------------------------------------------------
# SYSTEM METRICS, HEALTH & DATA MANAGEMENT MODULE
# ---------------------------------------------------------------------------
def get_system_stats():
    """Returns 100% real database metrics for administration dashboard."""
    create_users_table()
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM users")
    total_users = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM users WHERE role = 'Student'")
    student_count = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM users WHERE role = 'Researcher'")
    researcher_count = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM users WHERE role = 'Administrator'")
    admin_count = c.fetchone()[0]
    legacy_count = total_users - (student_count + researcher_count + admin_count)
    c.execute("SELECT COUNT(*) FROM users WHERE status != 'Disabled'")
    active_users = c.fetchone()[0]
    disabled_users = total_users - active_users
    c.execute("SELECT COUNT(*) FROM saved_papers")
    saved_papers_count = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM analysis_history")
    analysis_count = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM login_history")
    audit_count = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM upload_history")
    upload_count = c.fetchone()[0]
    conn.close()
    
    db_size = os.path.getsize(DB_PATH) if os.path.exists(DB_PATH) else 0
    if db_size > 1024 * 1024:
        db_size_str = f"{db_size / (1024*1024):.2f} MB"
    elif db_size > 1024:
        db_size_str = f"{db_size / 1024:.1f} KB"
    else:
        db_size_str = f"{db_size} bytes"

    return {
        "total_users": total_users,
        "student_count": student_count,
        "researcher_count": researcher_count,
        "admin_count": admin_count,
        "legacy_count": legacy_count,
        "active_users": active_users,
        "disabled_users": disabled_users,
        "saved_papers_count": saved_papers_count,
        "analysis_count": analysis_count,
        "audit_count": audit_count,
        "upload_count": upload_count,
        "db_size_bytes": db_size,
        "db_size_formatted": db_size_str
    }

def get_system_health():
    """Runs lightweight real-time diagnostic checks on SQLite database."""
    create_users_table()
    t0 = time.perf_counter()
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT 1")
    c.fetchone()
    latency_ms = (time.perf_counter() - t0) * 1000.0

    c.execute("PRAGMA integrity_check")
    integrity_res = c.fetchone()[0]

    tables = ["users", "analysis_history", "login_history", "saved_papers", "upload_history"]
    table_counts = {}
    for t in tables:
        c.execute(f"SELECT COUNT(*) FROM {t}")
        table_counts[t] = c.fetchone()[0]

    c.execute("PRAGMA page_count")
    page_count = c.fetchone()[0]
    c.execute("PRAGMA page_size")
    page_size = c.fetchone()[0]
    conn.close()

    db_size = os.path.getsize(DB_PATH) if os.path.exists(DB_PATH) else 0
    return {
        "status": "Healthy" if integrity_res == "ok" else "Degraded",
        "integrity": integrity_res,
        "latency_ms": round(latency_ms, 2),
        "db_size_bytes": db_size,
        "page_count": page_count,
        "page_size": page_size,
        "table_counts": table_counts
    }

def vacuum_database(current_admin_user=None):
    """Executes SQLite VACUUM to reclaim space and defragment database with administrator authorization."""
    if not is_admin_user(current_admin_user):
        record_audit_event(
            username=current_admin_user or "unknown",
            action_type="UNAUTHORIZED_ACCESS",
            target="users.db",
            details="Unauthorized attempt to execute database vacuum",
            status="Denied"
        )
        return False, "Access Denied: Administrator role required."
    try:
        conn = get_db_connection()
        conn.isolation_level = None
        c = conn.cursor()
        c.execute("VACUUM")
        conn.close()
        record_audit_event(
            username=current_admin_user or "admin",
            action_type="SYSTEM_MAINTENANCE",
            target="users.db",
            details="Database VACUUM optimization executed",
            status="Success"
        )
        return True, "Database vacuum completed successfully. Unused disk space reclaimed."
    except Exception as e:
        return False, str(e)

# ---------------------------------------------------------------------------
# CSV EXPORT UTILITIES (FORMULA-INJECTION SAFE)
# ---------------------------------------------------------------------------
def sanitize_csv_cell(val):
    """Prevents spreadsheet formula injection by escaping dangerous leading characters."""
    if val is None:
        return ""
    s = str(val)
    if s and s[0] in ("=", "+", "-", "@", "\t", "\r"):
        s = "'" + s
    return s

def export_users_csv():
    """Generates sanitized CSV export of registered user accounts (no passwords/hashes)."""
    users = get_all_users()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Username", "Academic Role", "Status", "Created At", "Theme Preference", "Analyses Count"])
    for u in users:
        writer.writerow([
            sanitize_csv_cell(u.get("username")),
            sanitize_csv_cell(u.get("role")),
            sanitize_csv_cell(u.get("status", "Active")),
            sanitize_csv_cell(u.get("created_at", "")),
            sanitize_csv_cell(u.get("theme_preference", "System")),
            sanitize_csv_cell(u.get("analysis_count", 0)),
        ])
    return output.getvalue()

def export_audit_csv(limit=1000):
    """Generates sanitized CSV export of security audit logs."""
    logs = get_login_history(limit=limit)
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Event ID", "Timestamp", "Username", "Role", "Action Type", "Status / Outcome", "IP Address", "Target", "Details"])
    for l in logs:
        writer.writerow([
            sanitize_csv_cell(l.get("id")),
            sanitize_csv_cell(l.get("login_time")),
            sanitize_csv_cell(l.get("username")),
            sanitize_csv_cell(l.get("role")),
            sanitize_csv_cell(l.get("action_type", "AUTH")),
            sanitize_csv_cell(l.get("status")),
            sanitize_csv_cell(l.get("ip_address")),
            sanitize_csv_cell(l.get("target", "")),
            sanitize_csv_cell(l.get("details", "")),
        ])
    return output.getvalue()

def export_repository_csv():
    """Generates sanitized CSV export of institutional repository metadata."""
    papers = get_saved_papers()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Paper ID", "Title", "Authors", "Domain", "Uploaded By", "Uploaded At", "Filename", "Score", "Grade", "Is Public"])
    for p in papers:
        writer.writerow([
            sanitize_csv_cell(p.get("paper_id")),
            sanitize_csv_cell(p.get("title")),
            sanitize_csv_cell(p.get("authors")),
            sanitize_csv_cell(p.get("domain")),
            sanitize_csv_cell(p.get("uploaded_by")),
            sanitize_csv_cell(p.get("uploaded_at")),
            sanitize_csv_cell(p.get("filename")),
            sanitize_csv_cell(p.get("score")),
            sanitize_csv_cell(p.get("grade")),
            sanitize_csv_cell(p.get("is_public", 1)),
        ])
    return output.getvalue()

if __name__ == "__main__":
    if len(sys.argv) >= 4 and sys.argv[1] == "provision-admin":
        success, msg = provision_admin(sys.argv[2], sys.argv[3])
        print(msg)
        sys.exit(0 if success else 1)
    else:
        create_users_table()
        print("PaperIQ Database initialized with tables, schema migrations, and audit security.")
