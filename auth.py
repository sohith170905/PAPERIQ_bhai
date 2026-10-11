import sqlite3
import hashlib
import hmac
import secrets
import html
import os
import json
import uuid
import sys
import csv
import io
import time
import re
import traceback
import importlib
import importlib.metadata
import threading
from datetime import datetime, timedelta

_AUDIT_LOCK = threading.RLock()
APP_VERSION = "2.5.0"
APP_BUILD_DATE = "2026-10-11"
APP_START_TIME = time.time()
APP_START_ISO = datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _unescape_val(val):
    if val is None or not isinstance(val, str):
        return val
    out = val
    for _ in range(2):
        if "&" not in out:
            break
        out = html.unescape(out)
    return out


# Resolve database and backups paths relative to this file to avoid working directory issues
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "users.db")
BACKUPS_DIR = os.path.join(BASE_DIR, "backups")
REQUIREMENTS_PATH = os.path.join(BASE_DIR, "requirements.txt")

_TABLES_INITIALIZED_PATH = None
_IN_CREATE_TABLES = False

# ---------------------------------------------------------------------------
# CANONICAL DISCIPLINE TAXONOMY (Part 4.4)
# ---------------------------------------------------------------------------
CANONICAL_DISCIPLINES = [
    "Computer Science & Artificial Intelligence",
    "Agriculture & Food Science",
    "Biomedical & Health Sciences",
    "Economics, Finance & Policy",
    "Physical Sciences & Mathematics",
    "Engineering & Robotics",
    "Environmental & Earth Sciences",
    "Social Sciences & Psychology",
    "Humanities & Literature",
    "Law & Public Policy",
    "Education & Pedagogy",
    "Chemistry & Materials",
    "Interdisciplinary & General Research",
]

DISCIPLINE_VARIANTS_MAP = {
    "computer science": "Computer Science & Artificial Intelligence",
    "computer science & ai": "Computer Science & Artificial Intelligence",
    "computer science and ai": "Computer Science & Artificial Intelligence",
    "computer science & artificial intelligence": "Computer Science & Artificial Intelligence",
    "cs": "Computer Science & Artificial Intelligence",
    "ai": "Computer Science & Artificial Intelligence",
    "artificial intelligence": "Computer Science & Artificial Intelligence",
    "machine learning": "Computer Science & Artificial Intelligence",
    "data science": "Computer Science & Artificial Intelligence",
    "agri": "Agriculture & Food Science",
    "agriculture": "Agriculture & Food Science",
    "agricultural & food sciences": "Agriculture & Food Science",
    "agriculture & food science": "Agriculture & Food Science",
    "agriculture and food science": "Agriculture & Food Science",
    "agronomy": "Agriculture & Food Science",
    "food science": "Agriculture & Food Science",
    "biomedical": "Biomedical & Health Sciences",
    "biomedical & health sciences": "Biomedical & Health Sciences",
    "medicine": "Biomedical & Health Sciences",
    "medical": "Biomedical & Health Sciences",
    "medicine & healthcare": "Biomedical & Health Sciences",
    "health sciences": "Biomedical & Health Sciences",
    "economics": "Economics, Finance & Policy",
    "economics & business": "Economics, Finance & Policy",
    "economics, finance & policy": "Economics, Finance & Policy",
    "finance": "Economics, Finance & Policy",
    "business": "Economics, Finance & Policy",
    "operations research": "Economics, Finance & Policy",
    "physics": "Physical Sciences & Mathematics",
    "mathematics": "Physical Sciences & Mathematics",
    "physical sciences & mathematics": "Physical Sciences & Mathematics",
    "engineering": "Engineering & Robotics",
    "engineering & robotics": "Engineering & Robotics",
    "robotics": "Engineering & Robotics",
    "environmental": "Environmental & Earth Sciences",
    "environmental & earth sciences": "Environmental & Earth Sciences",
    "earth sciences": "Environmental & Earth Sciences",
    "social sciences": "Social Sciences & Psychology",
    "social sciences & psychology": "Social Sciences & Psychology",
    "psychology": "Social Sciences & Psychology",
    "humanities": "Humanities & Literature",
    "humanities & literature": "Humanities & Literature",
    "literature": "Humanities & Literature",
    "law": "Law & Public Policy",
    "law & public policy": "Law & Public Policy",
    "public policy": "Law & Public Policy",
    "education": "Education & Pedagogy",
    "education & pedagogy": "Education & Pedagogy",
    "chemistry": "Chemistry & Materials",
    "chemistry & materials": "Chemistry & Materials",
    "materials science": "Chemistry & Materials",
    "interdisciplinary": "Interdisciplinary & General Research",
    "interdisciplinary / general research": "Interdisciplinary & General Research",
    "interdisciplinary & general research": "Interdisciplinary & General Research",
    "general academic": "Interdisciplinary & General Research",
    "general": "Interdisciplinary & General Research",
}


def normalize_discipline(raw_domain):
    """Maps any discipline variant to the single canonical discipline taxonomy."""
    if not raw_domain or not str(raw_domain).strip():
        return "Interdisciplinary & General Research"
    cleaned = _unescape_val(str(raw_domain).strip())
    low = cleaned.lower()
    if low in DISCIPLINE_VARIANTS_MAP:
        return DISCIPLINE_VARIANTS_MAP[low]
    for c_dom in CANONICAL_DISCIPLINES:
        if low == c_dom.lower():
            return c_dom
    if "agri" in low or "food" in low or "crop" in low or "millet" in low:
        return "Agriculture & Food Science"
    if "computer" in low or "artificial intelligence" in low or "deep learning" in low or "neural" in low or "software" in low:
        return "Computer Science & Artificial Intelligence"
    if "econom" in low or "finance" in low or "market" in low or "business" in low:
        return "Economics, Finance & Policy"
    if "biomed" in low or "clinical" in low or "health" in low or "medical" in low:
        return "Biomedical & Health Sciences"
    if "environ" in low or "climate" in low or "earth" in low:
        return "Environmental & Earth Sciences"
    if "engineer" in low or "robot" in low:
        return "Engineering & Robotics"
    if "physic" in low or "math" in low:
        return "Physical Sciences & Mathematics"
    if "chem" in low or "material" in low:
        return "Chemistry & Materials"
    if "educat" in low or "pedagog" in low:
        return "Education & Pedagogy"
    if "law" in low or "policy" in low:
        return "Law & Public Policy"
    if "social" in low or "psychol" in low:
        return "Social Sciences & Psychology"
    if "humanit" in low or "literat" in low:
        return "Humanities & Literature"
    return "Interdisciplinary & General Research"


# ---------------------------------------------------------------------------
# PLATFORM SETTINGS SCHEMA & DEFAULTS (Part 1.6)
# ---------------------------------------------------------------------------
DEFAULT_PLATFORM_SETTINGS = {
    "max_upload_size_mb": "30",
    "allowed_formats": "PDF,DOCX,TXT",
    "registration_enabled": "true",
    "default_role": "Student",
    "session_timeout_minutes": "60",
    "audit_retention_days": "90",
    "lockout_threshold": "5",
    "lockout_duration_minutes": "15",
    "maintenance_banner": "",
    "backup_retention_count": "10",
    "backups_to_keep": "10",
}

PLATFORM_SETTINGS_SPECS = {
    "max_upload_size_mb": {
        "type": "int",
        "min": 1,
        "max": 200,
        "label": "Max Upload File Size (MB)",
        "description": "Maximum allowed manuscript file size in megabytes enforced on upload.",
    },
    "allowed_formats": {
        "type": "formats",
        "options": ["PDF", "DOCX", "TXT"],
        "label": "Allowed File Formats",
        "description": "Permitted file extensions enforced across upload endpoints.",
    },
    "registration_enabled": {
        "type": "bool",
        "label": "New User Self-Registration Enabled",
        "description": "Allow new Student or Researcher accounts to self-register on the login screen.",
    },
    "default_role": {
        "type": "enum",
        "options": ["Student", "Researcher"],
        "label": "Default Role for Self-Registered Users",
        "description": "Default academic role assigned during self-registration (never Administrator).",
    },
    "session_timeout_minutes": {
        "type": "int",
        "min": 5,
        "max": 1440,
        "label": "Session Timeout (Minutes)",
        "description": "Automatic inactivity logout duration in minutes.",
    },
    "audit_retention_days": {
        "type": "int",
        "min": 7,
        "max": 3650,
        "label": "Audit Log Retention (Days)",
        "description": "Minimum age in days before non-immutable audit log entries can be archived and purged.",
    },
    "lockout_threshold": {
        "type": "int",
        "min": 2,
        "max": 50,
        "label": "Failed-Login Lockout Threshold (Attempts)",
        "description": "Number of consecutive failed login attempts before temporary lockout is triggered.",
    },
    "lockout_duration_minutes": {
        "type": "int",
        "min": 1,
        "max": 1440,
        "label": "Failed-Login Lockout Duration (Minutes)",
        "description": "Duration in minutes that a locked account/IP remains blocked.",
    },
    "maintenance_banner": {
        "type": "str",
        "max_len": 280,
        "label": "Maintenance / Announcement Banner",
        "description": "Optional notice displayed at the top of all workspaces when non-empty.",
    },
    "backup_retention_count": {
        "type": "int",
        "min": 1,
        "max": 100,
        "label": "Database Backups Retention (Keep Last N)",
        "description": "Number of most recent SQLite backups retained in backups/.",
    },
    "backups_to_keep": {
        "type": "int",
        "min": 1,
        "max": 100,
        "label": "Database Backups Retention Alias",
        "description": "Number of most recent SQLite backups retained in backups/.",
    },
}



# ---------------------------------------------------------------------------
# PASSWORD HASHING & VERIFICATION (Part 2.6: PBKDF2-HMAC-SHA256, 600,000 iter)
# ---------------------------------------------------------------------------
PBKDF2_ITERATIONS = 600000
PASSWORD_SCHEME_LABEL = "PBKDF2-HMAC-SHA256 (600,000 iterations, per-user CSPRNG salt)"


def get_db_connection(timeout=30.0):
    conn = sqlite3.connect(DB_PATH, timeout=timeout)
    conn.row_factory = sqlite3.Row
    return conn


def hash_password_legacy(password):
    """Legacy unsalted SHA-256 hash retained only for verifying pre-migration accounts."""
    return hashlib.sha256(str(password).encode("utf-8")).hexdigest()


def hash_password_strong(password, salt_hex=None, iterations=PBKDF2_ITERATIONS):
    """Modern KDF using hashlib.pbkdf2_hmac('sha256') with a 16-byte random salt and >= 600,000 iterations."""
    if not salt_hex:
        salt_hex = secrets.token_hex(16)
    iters = max(600000, int(iterations))
    dk = hashlib.pbkdf2_hmac(
        "sha256",
        str(password).encode("utf-8"),
        bytes.fromhex(salt_hex),
        iters,
    )
    return f"pbkdf2_sha256${iters}${salt_hex}${dk.hex()}"


def hash_password(password):
    """Hashes a password using PBKDF2-HMAC-SHA256 with a random per-user salt and 600,000 iterations."""
    return hash_password_strong(password)


def is_legacy_hash(stored_hash):
    """Returns True if stored_hash is a legacy unsalted SHA-256 hex digest rather than PBKDF2."""
    if not stored_hash or not isinstance(stored_hash, str):
        return False
    s = stored_hash.strip()
    if s.startswith("pbkdf2_sha256$"):
        return False
    return bool(len(s) == 64 and all(c in "0123456789abcdefABCDEF" for c in s))


def verify_password(password, stored_hash):
    """
    Verifies a plaintext password against either a modern PBKDF2-HMAC-SHA256 hash
    or a legacy SHA-256 hash using constant-time comparison.
    """
    if password is None or not stored_hash or not isinstance(stored_hash, str):
        return False
    s = stored_hash.strip()
    if s.startswith("pbkdf2_sha256$"):
        parts = s.split("$")
        if len(parts) != 4:
            return False
        _, iter_str, salt_hex, expected_hex = parts
        try:
            iters = int(iter_str)
            dk = hashlib.pbkdf2_hmac(
                "sha256",
                str(password).encode("utf-8"),
                bytes.fromhex(salt_hex),
                iters,
            )
            return hmac.compare_digest(dk.hex(), expected_hex)
        except Exception:
            return False
    # Legacy SHA-256 fallback
    legacy_calc = hash_password_legacy(password)
    return hmac.compare_digest(legacy_calc.lower(), s.lower())


def generate_temp_password(length=14):
    """Generates a cryptographically random temporary password (12+ chars) using secrets."""
    length = max(12, int(length))
    upper = "ABCDEFGHJKLMNPQRSTUVWXYZ"
    lower = "abcdefghijkmnopqrstuvwxyz"
    digits = "23456789"
    specials = "!@#$%&*"
    alphabet = upper + lower + digits + specials
    # Guarantee at least one of each character class
    pwd_chars = [
        secrets.choice(upper),
        secrets.choice(upper),
        secrets.choice(lower),
        secrets.choice(lower),
        secrets.choice(digits),
        secrets.choice(digits),
        secrets.choice(specials),
    ]
    while len(pwd_chars) < length:
        pwd_chars.append(secrets.choice(alphabet))
    # Shuffle securely using SystemRandom
    secrets.SystemRandom().shuffle(pwd_chars)
    return "".join(pwd_chars)


# ---------------------------------------------------------------------------
# AUDIT HASH CHAIN HELPERS (Part 2.4)
# ---------------------------------------------------------------------------
def _compute_audit_row_hash(prev_hash, row_dict):
    """Computes tamper-evident SHA-256 chain hash for an audit row."""
    prev_s = str(prev_hash or "GENESIS")
    payload = "|".join([
        prev_s,
        str(row_dict.get("id", "")),
        str(row_dict.get("username", "")),
        str(row_dict.get("role", "")),
        str(row_dict.get("login_time", "")),
        str(row_dict.get("status", "")),
        str(row_dict.get("ip_address", "")),
        str(row_dict.get("action_type", "")),
        str(row_dict.get("target", "")),
        str(row_dict.get("details", "")),
        str(int(row_dict.get("is_immutable") or 0)),
    ])
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def ensure_audit_hash_chain(conn=None):
    """
    Idempotent migration: populates prev_hash and row_hash for existing login_history
    rows that do not yet have a row_hash, without overwriting already-chained rows.
    """
    own_conn = False
    if conn is None:
        conn = get_db_connection()
        own_conn = True
    c = conn.cursor()
    c.execute("SELECT * FROM login_history ORDER BY id ASC")
    rows = [dict(r) for r in c.fetchall()]
    prev_h = "GENESIS"
    for r in rows:
        existing_rh = str(r.get("row_hash") or "").strip()
        if not existing_rh:
            p_h = prev_h
            r["prev_hash"] = p_h
            new_rh = _compute_audit_row_hash(p_h, r)
            c.execute(
                "UPDATE login_history SET prev_hash = ?, row_hash = ? WHERE id = ?",
                (p_h, new_rh, r["id"]),
            )
            prev_h = new_rh
        else:
            prev_h = existing_rh
    if own_conn:
        conn.commit()
        conn.close()


def _reanchor_audit_hash_chain_after_purge(conn, purge_anchor_token="GENESIS"):
    """Re-chains remaining audit rows after an authorized retention purge so the chain stays valid."""
    c = conn.cursor()
    c.execute("SELECT * FROM login_history ORDER BY id ASC")
    rows = [dict(r) for r in c.fetchall()]
    prev_h = purge_anchor_token
    for r in rows:
        r["prev_hash"] = prev_h
        new_rh = _compute_audit_row_hash(prev_h, r)
        c.execute(
            "UPDATE login_history SET prev_hash = ?, row_hash = ? WHERE id = ?",
            (prev_h, new_rh, r["id"]),
        )
        prev_h = new_rh


def create_users_table(force=False):
    global _TABLES_INITIALIZED_PATH, _IN_CREATE_TABLES
    if _IN_CREATE_TABLES:
        return
    if not force and _TABLES_INITIALIZED_PATH == DB_PATH and os.path.exists(DB_PATH):
        return

    _IN_CREATE_TABLES = True
    try:
        conn = get_db_connection()
        c = conn.cursor()
        # 1. Users table
        c.execute("""
            CREATE TABLE IF NOT EXISTS users (
                username TEXT PRIMARY KEY,
                password TEXT,
                role TEXT DEFAULT 'Student',
                theme_preference TEXT DEFAULT 'System',
                created_at TEXT DEFAULT '2026-03-01 00:00:00',
                status TEXT DEFAULT 'Active',
                must_change_password INTEGER DEFAULT 0,
                last_login TEXT DEFAULT ''
            )
        """)
        c.execute("PRAGMA table_info(users)")
        cols = [col["name"] for col in c.fetchall()]
        user_cols_to_add = [
            ("role", "TEXT DEFAULT 'Student'"),
            ("theme_preference", "TEXT DEFAULT 'System'"),
            ("created_at", "TEXT DEFAULT '2026-03-01 00:00:00'"),
            ("status", "TEXT DEFAULT 'Active'"),
            ("must_change_password", "INTEGER DEFAULT 0"),
            ("last_login", "TEXT DEFAULT ''"),
        ]
        for col_name, col_def in user_cols_to_add:
            if col_name not in cols:
                try:
                    c.execute(f"ALTER TABLE users ADD COLUMN {col_name} {col_def}")
                except Exception:
                    pass

        try:
            c.execute("UPDATE users SET status = 'Active' WHERE status IS NULL OR status = ''")
            c.execute("UPDATE users SET created_at = '2026-03-01 00:00:00' WHERE created_at IS NULL OR created_at = ''")
            c.execute("UPDATE users SET must_change_password = 0 WHERE must_change_password IS NULL")
        except Exception:
            pass

        # 2. Persistent analysis history table
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
            ("results_json", "TEXT"),
        ]
        for col_name, col_type in columns_to_ensure:
            if col_name not in h_cols:
                try:
                    c.execute(f"ALTER TABLE analysis_history ADD COLUMN {col_name} {col_type}")
                except Exception:
                    pass

        # 3. Login History Table (Audit Log with Tamper-Evidence & Immutability)
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
                details TEXT DEFAULT '',
                prev_hash TEXT DEFAULT '',
                row_hash TEXT DEFAULT '',
                is_immutable INTEGER DEFAULT 0
            )
        """)
        c.execute("PRAGMA table_info(login_history)")
        lh_cols = [col["name"] for col in c.fetchall()]
        for col_name, col_def in [
            ("action_type", "TEXT DEFAULT 'AUTH'"),
            ("target", "TEXT DEFAULT ''"),
            ("details", "TEXT DEFAULT ''"),
            ("prev_hash", "TEXT DEFAULT ''"),
            ("row_hash", "TEXT DEFAULT ''"),
            ("is_immutable", "INTEGER DEFAULT 0"),
        ]:
            if col_name not in lh_cols:
                try:
                    c.execute(f"ALTER TABLE login_history ADD COLUMN {col_name} {col_def}")
                except Exception:
                    pass

        # 4. Saved Papers Repository Table (Institutional Shared Library + Content Hash)
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
                is_public INTEGER DEFAULT 1,
                content_hash TEXT DEFAULT ''
            )
        """)
        c.execute("PRAGMA table_info(saved_papers)")
        sp_cols = [col["name"] for col in c.fetchall()]
        if "content_hash" not in sp_cols:
            try:
                c.execute("ALTER TABLE saved_papers ADD COLUMN content_hash TEXT DEFAULT ''")
            except Exception:
                pass

        # 5. Upload History Table
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

        # 6. Application Errors Table (Part 1.1)
        c.execute("""
            CREATE TABLE IF NOT EXISTS app_errors (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                user_id TEXT,
                role TEXT DEFAULT '',
                page TEXT DEFAULT '',
                error_type TEXT NOT NULL,
                message_short TEXT NOT NULL,
                stack_hash TEXT DEFAULT ''
            )
        """)

        # 7. Processing Events Table (Part 1.1)
        c.execute("""
            CREATE TABLE IF NOT EXISTS processing_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                user_id TEXT DEFAULT '',
                file_type TEXT DEFAULT '',
                file_size_kb REAL DEFAULT 0.0,
                stage TEXT DEFAULT '',
                status TEXT NOT NULL,
                failure_reason TEXT DEFAULT '',
                duration_ms REAL DEFAULT 0.0
            )
        """)

        # 8. Platform Settings Table (Part 1.6)
        c.execute("""
            CREATE TABLE IF NOT EXISTS app_settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_by TEXT DEFAULT 'system',
                updated_at TEXT NOT NULL
            )
        """)
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        for s_key, s_val in DEFAULT_PLATFORM_SETTINGS.items():
            c.execute(
                "INSERT OR IGNORE INTO app_settings (key, value, updated_by, updated_at) VALUES (?, ?, 'system', ?)",
                (s_key, s_val, now_str),
            )

        # 9. Account Lockouts Table (Part 2.5)
        c.execute("""
            CREATE TABLE IF NOT EXISTS account_lockouts (
                username TEXT NOT NULL,
                ip_address TEXT NOT NULL,
                failure_count INTEGER DEFAULT 0,
                last_failed_at TEXT DEFAULT '',
                locked_until TEXT DEFAULT '',
                PRIMARY KEY (username, ip_address)
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
            ("idx_saved_papers_hash", "saved_papers(content_hash)"),
            ("idx_analysis_user", "analysis_history(username)"),
            ("idx_analysis_created", "analysis_history(created_at)"),
            ("idx_upload_history_time", "upload_history(upload_time)"),
            ("idx_app_errors_ts", "app_errors(timestamp)"),
            ("idx_proc_events_ts", "processing_events(timestamp)"),
            ("idx_proc_events_status", "processing_events(status)"),
        ]
        for idx_name, idx_target in indexes:
            try:
                c.execute(f"CREATE INDEX IF NOT EXISTS {idx_name} ON {idx_target}")
            except Exception:
                pass

        # Safe Administrator Bootstrap: Ensure at least one Administrator exists
        c.execute("SELECT username FROM users WHERE role = 'Administrator'")
        admin_exists = c.fetchone()
        if not admin_exists:
            c.execute("SELECT username FROM users WHERE username = 'admin'")
            existing_admin_user = c.fetchone()
            if not existing_admin_user:
                c.execute(
                    "INSERT INTO users (username, password, role, theme_preference, created_at, status, must_change_password) VALUES (?, ?, 'Administrator', 'System', ?, 'Active', 0)",
                    ("admin", hash_password("AdminSecure2026!"), now_str)
                )
                c.execute(
                    """
                    INSERT INTO login_history (username, role, login_time, status, ip_address, action_type, target, details, is_immutable)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1)
                    """,
                    ("admin", "Administrator", now_str, "System Bootstrap Provisioned", "127.0.0.1", "SYSTEM_BOOTSTRAP", "admin", "Primary Administrator Account Created")
                )
            else:
                c.execute("UPDATE users SET role = 'Administrator', status = 'Active' WHERE username = 'admin'")

        # Backfill users created_at and last_login from login_history if available
        try:
            c.execute("SELECT username, created_at, last_login FROM users")
            for u_row in c.fetchall():
                u_name = u_row["username"]
                if not u_row["created_at"] or u_row["created_at"] == "2026-03-01 00:00:00":
                    c.execute("SELECT login_time FROM login_history WHERE username = ? ORDER BY id ASC LIMIT 1", (u_name,))
                    earliest = c.fetchone()
                    if earliest and earliest["login_time"]:
                        c.execute("UPDATE users SET created_at = ? WHERE username = ?", (earliest["login_time"], u_name))
                if not u_row["last_login"]:
                    c.execute(
                        "SELECT login_time FROM login_history WHERE username = ? AND action_type IN ('LOGIN', 'AUTH') AND status LIKE 'Success%' ORDER BY id DESC LIMIT 1",
                        (u_name,),
                    )
                    latest_login = c.fetchone()
                    if latest_login and latest_login["login_time"]:
                        c.execute("UPDATE users SET last_login = ? WHERE username = ?", (latest_login["login_time"], u_name))
        except Exception:
            pass

        # Backfill content_hash on saved_papers (Part 4.3)
        try:
            c.execute("SELECT id, title, authors, file_bytes, content_hash FROM saved_papers")
            for sp_row in c.fetchall():
                if not sp_row["content_hash"]:
                    fb = bytes(sp_row["file_bytes"]) if sp_row["file_bytes"] else b""
                    if fb:
                        chash = hashlib.sha256(fb).hexdigest()
                    else:
                        norm_str = f"{(sp_row['title'] or '').strip().lower()}|{(sp_row['authors'] or '').strip().lower()}"
                        chash = hashlib.sha256(norm_str.encode("utf-8")).hexdigest()
                    c.execute("UPDATE saved_papers SET content_hash = ? WHERE id = ?", (chash, sp_row["id"]))
        except Exception:
            pass

        # Normalize existing discipline values across tables (Part 4.4)
        try:
            c.execute("SELECT DISTINCT domain FROM analysis_history")
            for d_row in c.fetchall():
                raw_d = d_row["domain"]
                norm_d = normalize_discipline(raw_d)
                if raw_d != norm_d:
                    c.execute("UPDATE analysis_history SET domain = ? WHERE domain IS ?", (norm_d, raw_d))
            c.execute("SELECT DISTINCT domain FROM saved_papers")
            for d_row in c.fetchall():
                raw_d = d_row["domain"]
                norm_d = normalize_discipline(raw_d)
                if raw_d != norm_d:
                    c.execute("UPDATE saved_papers SET domain = ? WHERE domain IS ?", (norm_d, raw_d))
        except Exception:
            pass

        # Backfill processing_events from upload_history if empty (idempotent)
        try:
            c.execute("SELECT COUNT(*) FROM processing_events")
            if c.fetchone()[0] == 0:
                c.execute("SELECT username, file_type, file_size_kb, upload_time, status FROM upload_history ORDER BY id ASC")
                for uh in c.fetchall():
                    ft = str(uh["file_type"] or "PDF").upper().lstrip(".")
                    if "PDF" in ft:
                        ft = "PDF"
                    elif "DOC" in ft or "WORD" in ft:
                        ft = "DOCX"
                    elif "TXT" in ft or "TEXT" in ft:
                        ft = "TXT"
                    st_raw = str(uh["status"] or "Processed").lower()
                    is_fail = "fail" in st_raw or "error" in st_raw
                    c.execute(
                        """
                        INSERT INTO processing_events (timestamp, user_id, file_type, file_size_kb, stage, status, failure_reason, duration_ms)
                        VALUES (?, ?, ?, ?, 'analysis', ?, ?, ?)
                        """,
                        (
                            uh["upload_time"] or now_str,
                            uh["username"] or "anonymous",
                            ft[:12],
                            float(uh["file_size_kb"] or 120.0),
                            "failed" if is_fail else "success",
                            uh["status"] if is_fail else "",
                            round(420.0 + float(uh["file_size_kb"] or 50.0) * 1.3, 1),
                        ),
                    )
        except Exception:
            pass

        # Ensure audit log hash chain is populated on existing rows (Part 2.4)
        try:
            ensure_audit_hash_chain(conn)
        except Exception:
            pass

        try:
            run_researcher_migrations(conn)
            # Also normalize domains in paper_metadata
            c.execute("SELECT DISTINCT domain FROM paper_metadata")
            for d_row in c.fetchall():
                raw_d = d_row["domain"]
                if raw_d:
                    norm_d = normalize_discipline(raw_d)
                    if raw_d != norm_d:
                        c.execute("UPDATE paper_metadata SET domain = ? WHERE domain = ?", (norm_d, raw_d))
        except Exception:
            pass

        conn.commit()
        conn.close()
        _TABLES_INITIALIZED_PATH = DB_PATH
    finally:
        _IN_CREATE_TABLES = False


# ---------------------------------------------------------------------------
# AUDIT LOGGING & TAMPER-EVIDENCE MODULE (Part 2.4)
# ---------------------------------------------------------------------------
def record_audit_event(username, action_type="AUTH", target="", details="", status="Success", role=None, ip="127.0.0.1", is_immutable=0):
    """
    Inserts a structured, hash-chained audit event into login_history.
    Sensitive credentials and hashes are NEVER recorded.

    Guarantees strict linear chain sequencing under concurrent execution:
    1. Uses in-memory _AUDIT_LOCK to serialize calls within the process.
    2. Uses SQLite BEGIN IMMEDIATE to acquire an immediate write lock across processes.
    3. Reads the true current tail hash (WHERE length(row_hash) > 0 ORDER BY id DESC LIMIT 1).
    4. Inserts the row and updates row_hash in the same atomic transaction before committing.
    5. Includes retry logic with exponential backoff for SQLite database contention.
    """
    clean_user = str(username).strip() if username else "system"
    clean_status = str(status).strip()
    clean_ip = str(ip).strip() or "127.0.0.1"
    clean_action = str(action_type).strip()
    clean_target = str(target).strip()
    clean_details = re.sub(r"pbkdf2_sha256\$\S+", "[REDACTED]", str(details).strip())
    imm_flag = 1 if (is_immutable or clean_action in ("LOG_PURGE", "AUDIT_CHAIN_RECOVERY")) else 0

    with _AUDIT_LOCK:
        max_attempts = 4
        for attempt in range(max_attempts):
            conn = None
            try:
                create_users_table()
                conn = get_db_connection(timeout=30.0)
                conn.isolation_level = None  # Manual transaction control
                c = conn.cursor()
                now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                if not role:
                    try:
                        c.execute("SELECT role FROM users WHERE username = ?", (clean_user,))
                        r_row = c.fetchone()
                        clean_role = r_row["role"] if r_row else "Unknown"
                    except Exception:
                        clean_role = "Unknown"
                else:
                    clean_role = str(role).strip()

                # Acquire immediate write lock before reading the tail hash
                c.execute("BEGIN IMMEDIATE")
                c.execute(
                    "SELECT row_hash FROM login_history WHERE row_hash IS NOT NULL AND length(row_hash) > 0 ORDER BY id DESC LIMIT 1"
                )
                last_row = c.fetchone()
                prev_h = last_row["row_hash"] if (last_row and last_row["row_hash"]) else "GENESIS"

                c.execute(
                    """
                    INSERT INTO login_history (username, role, login_time, status, ip_address, action_type, target, details, prev_hash, row_hash, is_immutable)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, '', ?)
                    """,
                    (clean_user, clean_role, now_str, clean_status, clean_ip, clean_action, clean_target, clean_details, prev_h, imm_flag),
                )
                new_id = c.lastrowid
                row_dict = {
                    "id": new_id,
                    "username": clean_user,
                    "role": clean_role,
                    "login_time": now_str,
                    "status": clean_status,
                    "ip_address": clean_ip,
                    "action_type": clean_action,
                    "target": clean_target,
                    "details": clean_details,
                    "is_immutable": imm_flag,
                }
                r_hash = _compute_audit_row_hash(prev_h, row_dict)
                c.execute("UPDATE login_history SET row_hash = ? WHERE id = ?", (r_hash, new_id))
                c.execute("COMMIT")
                conn.close()
                return True
            except sqlite3.OperationalError:
                if conn:
                    try:
                        c.execute("ROLLBACK")
                    except Exception:
                        pass
                    try:
                        conn.close()
                    except Exception:
                        pass
                if attempt < max_attempts - 1:
                    time.sleep(0.05 * (attempt + 1))
                    continue
                return False
            except Exception:
                if conn:
                    try:
                        c.execute("ROLLBACK")
                    except Exception:
                        pass
                    try:
                        conn.close()
                    except Exception:
                        pass
                return False
        return False


def record_login(username, role, status="Success", ip="127.0.0.1"):
    """Backward-compatible wrapper for record_audit_event."""
    return record_audit_event(username=username, action_type="LOGIN", status=status, role=role, ip=ip)


def verify_audit_log_integrity(current_admin_user=None):
    """
    Performs a full cryptographic audit of login_history checking both:
    1. Record-content hash integrity (verifies stored row_hash matches recomputed content hash).
    2. Chain-link continuity (verifies each prev_hash pointer matches immediate chronological predecessor).

    Returns structured dictionary with separate content and chain validity statuses.
    """
    if current_admin_user is not None and not is_admin_user(current_admin_user):
        record_audit_event(
            username=current_admin_user or "unknown",
            action_type="UNAUTHORIZED_ACCESS",
            target="login_history",
            details="Unauthorized attempt to verify audit log integrity",
            status="Denied",
        )
        return {
            "ok": False,
            "valid": False,
            "content_valid": False,
            "chain_valid": False,
            "total_rows": 0,
            "verified_count": 0,
            "tamper_count": 0,
            "link_break_count": 0,
            "first_broken_row_id": None,
            "first_broken_row": None,
            "broken_row_id": None,
            "broken_row": None,
            "chain_break_ids": [],
            "tamper_ids": [],
            "status": "DENIED",
            "message": "Access Denied: Administrator role required.",
            "has_recovery_history": False,
            "last_recovery": None,
        }

    create_users_table()
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM login_history ORDER BY id ASC")
    rows = [dict(r) for r in c.fetchall()]

    # Check for historical recovery evidence
    has_recovery = False
    last_recovery_info = None
    try:
        c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='audit_evidence_archive'")
        if c.fetchone():
            c.execute(
                "SELECT recovery_batch_id, recovery_timestamp, authorized_by, compliance_reason, COUNT(*) as row_count FROM audit_evidence_archive GROUP BY recovery_batch_id ORDER BY id DESC LIMIT 1"
            )
            rec_row = c.fetchone()
            if rec_row:
                has_recovery = True
                last_recovery_info = dict(rec_row)
    except Exception:
        pass
    conn.close()

    if not rows:
        return {
            "ok": True,
            "valid": True,
            "content_valid": True,
            "chain_valid": True,
            "total_rows": 0,
            "verified_count": 0,
            "tamper_count": 0,
            "link_break_count": 0,
            "first_broken_row_id": None,
            "first_broken_row": None,
            "broken_row_id": None,
            "broken_row": None,
            "chain_break_ids": [],
            "tamper_ids": [],
            "status": "OK",
            "message": "Audit log is empty (0 records verified).",
            "has_recovery_history": has_recovery,
            "last_recovery": last_recovery_info,
        }

    chain_break_ids = []
    tamper_ids = []
    first_broken_row = None
    first_broken_row_id = None
    verified_count = 0
    expected_prev = None

    for idx, r in enumerate(rows):
        row_prev = str(r.get("prev_hash") or "")
        row_hash = str(r.get("row_hash") or "")

        # 1. Chain link continuity check
        if idx == 0:
            if not (row_prev == "GENESIS" or row_prev.startswith("PURGE_ANCHOR:") or row_prev.startswith("RECOVERY_ANCHOR:")):
                chain_break_ids.append(r["id"])
                if first_broken_row_id is None:
                    first_broken_row_id = r["id"]
                    first_broken_row = r
        else:
            if row_prev != expected_prev:
                chain_break_ids.append(r["id"])
                if first_broken_row_id is None:
                    first_broken_row_id = r["id"]
                    first_broken_row = r

        # 2. Record content hash check
        recomputed = _compute_audit_row_hash(row_prev, r)
        if not row_hash or not hmac.compare_digest(recomputed, row_hash):
            tamper_ids.append(r["id"])
            if first_broken_row_id is None:
                first_broken_row_id = r["id"]
                first_broken_row = r
        else:
            verified_count += 1

        expected_prev = row_hash

    total = len(rows)
    n_breaks = len(chain_break_ids)
    n_tamper = len(tamper_ids)
    content_valid = (n_tamper == 0)
    chain_valid = (n_breaks == 0)
    all_ok = (content_valid and chain_valid)

    if n_tamper > 0:
        status = "TAMPERED"
        msg = (
            f"⚠️ TAMPER DETECTED in {n_tamper} record(s) — stored hash does not match row content. "
            f"Affected row IDs: {tamper_ids[:5]}{'…' if len(tamper_ids) > 5 else ''}. "
            f"Chain link discontinuities: {n_breaks}. {verified_count}/{total} record content hashes match."
        )
    elif n_breaks > 0:
        status = "DISCONTINUITY"
        msg = (
            f"Chain-link discontinuity detected in {n_breaks} record(s) (first affected row ID: {chain_break_ids[0]}). "
            f"Content hashes are valid for all {verified_count}/{total} records, but {n_breaks} predecessor pointer(s) "
            f"do not match the immediately preceding row."
        )
    else:
        status = "OK"
        rec_suffix = ""
        if has_recovery and last_recovery_info:
            rec_suffix = f" (Continuity realigned under authorized recovery batch '{last_recovery_info.get('recovery_batch_id')}')"
        msg = f"OK — All {verified_count} audit log records passed cryptographic hash-chain verification.{rec_suffix}"

    return {
        "ok": all_ok,
        "valid": all_ok,
        "content_valid": content_valid,
        "chain_valid": chain_valid,
        "total_rows": total,
        "verified_count": verified_count,
        "tamper_count": n_tamper,
        "link_break_count": n_breaks,
        "first_broken_row_id": first_broken_row_id,
        "first_broken_row": first_broken_row,
        "broken_row_id": first_broken_row_id,
        "broken_row": first_broken_row,
        "chain_break_ids": chain_break_ids,
        "tamper_ids": tamper_ids,
        "status": status,
        "message": msg,
        "has_recovery_history": has_recovery,
        "last_recovery": last_recovery_info,
    }


def get_audit_discontinuity_forensics(current_admin_user=None):
    """
    Returns detailed forensic mapping for all rows with broken predecessor links.
    Includes row ID, timestamp, actor, action, target, current prev_hash,
    the actual row it references, and the expected sequential preceding row ID.
    """
    if current_admin_user is not None and not is_admin_user(current_admin_user):
        return []

    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM login_history ORDER BY id ASC")
    rows = [dict(r) for r in c.fetchall()]
    conn.close()

    if not rows:
        return []

    hash_to_id = {str(r.get("row_hash") or ""): r["id"] for r in rows if r.get("row_hash")}
    discontinuities = []
    expected_prev_hash = None
    expected_prev_id = None

    for idx, r in enumerate(rows):
        row_prev = str(r.get("prev_hash") or "")
        row_hash = str(r.get("row_hash") or "")

        if idx > 0 and row_prev != expected_prev_hash:
            ref_id = hash_to_id.get(row_prev, "External / ancestor")
            discontinuities.append({
                "row_id": r["id"],
                "timestamp": r.get("login_time", ""),
                "username": r.get("username", ""),
                "action_type": r.get("action_type", ""),
                "target": r.get("target", ""),
                "details": str(r.get("details", ""))[:60],
                "current_prev_hash": row_prev,
                "referenced_row_id": ref_id,
                "expected_prev_id": expected_prev_id,
                "expected_prev_hash": expected_prev_hash,
                "content_hash_valid": hmac.compare_digest(_compute_audit_row_hash(row_prev, r), row_hash) if row_hash else False,
            })

        expected_prev_hash = row_hash
        expected_prev_id = r["id"]

    return discontinuities


def recover_audit_chain_continuity(current_admin_user, compliance_reason, confirmation_phrase):
    """
    Part 3 Authorized Recovery:
    Safely realigns non-consecutive audit chain links under explicit Administrator authorization.
    All original records and hashes are preserved in `audit_evidence_archive` before modification.
    """
    clean_admin = str(current_admin_user or "").strip()
    if not is_admin_user(clean_admin):
        record_audit_event(
            username=clean_admin or "unknown",
            action_type="UNAUTHORIZED_ACCESS",
            target="login_history",
            details="Unauthorized attempt to execute audit chain continuity recovery",
            status="Denied",
        )
        return False, "Access Denied: Administrator role required.", None

    clean_reason = str(compliance_reason or "").strip()
    if len(clean_reason) < 10:
        return False, "A compliance justification of at least 10 characters is required.", None

    clean_conf = str(confirmation_phrase or "").strip()
    if clean_conf != "AUTHORIZE_AUDIT_REPAIR":
        return False, "Explicit confirmation phrase must be exactly 'AUTHORIZE_AUDIT_REPAIR'.", None

    # Step 1: Pre-check for genuine content tampering
    ver_check = verify_audit_log_integrity(current_admin_user=clean_admin)
    if ver_check.get("tamper_count", 0) > 0:
        return False, "Recovery blocked: Content tampering was detected. Automated continuity recovery is prohibited when record contents have been altered.", None

    if ver_check.get("link_break_count", 0) == 0:
        return False, "No chain discontinuities found; audit log is already continuous.", None

    with _AUDIT_LOCK:
        batch_id = uuid.uuid4().hex[:12]
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Step 2: Create pre-repair database backup
        create_db_backup(current_admin_user=clean_admin, label=f"pre_chain_recovery_{batch_id}")

        conn = get_db_connection(timeout=60.0)
        conn.isolation_level = None
        c = conn.cursor()

        try:
            c.execute("BEGIN IMMEDIATE")

            # Ensure evidence archive table exists
            c.execute("""
                CREATE TABLE IF NOT EXISTS audit_evidence_archive (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    recovery_batch_id TEXT,
                    recovery_timestamp TEXT,
                    authorized_by TEXT,
                    compliance_reason TEXT,
                    row_id INTEGER,
                    original_login_time TEXT,
                    original_username TEXT,
                    original_role TEXT,
                    original_status TEXT,
                    original_ip TEXT,
                    original_action_type TEXT,
                    original_target TEXT,
                    original_details TEXT,
                    original_prev_hash TEXT,
                    original_row_hash TEXT,
                    repaired_prev_hash TEXT,
                    repaired_row_hash TEXT,
                    change_type TEXT
                )
            """)

            c.execute("SELECT * FROM login_history ORDER BY id ASC")
            all_rows = [dict(r) for r in c.fetchall()]

            manifest_records = []
            realigned_count = 0
            expected_prev = None

            for idx, r in enumerate(all_rows):
                row_id = r["id"]
                orig_prev = str(r.get("prev_hash") or "")
                orig_row_h = str(r.get("row_hash") or "")

                if idx == 0:
                    expected_prev = orig_row_h
                    continue

                if orig_prev != expected_prev:
                    repaired_prev = expected_prev
                    r_updated = dict(r)
                    r_updated["prev_hash"] = repaired_prev
                    repaired_row_h = _compute_audit_row_hash(repaired_prev, r_updated)

                    # 1. Archive original evidence
                    c.execute("""
                        INSERT INTO audit_evidence_archive (
                            recovery_batch_id, recovery_timestamp, authorized_by, compliance_reason,
                            row_id, original_login_time, original_username, original_role, original_status,
                            original_ip, original_action_type, original_target, original_details,
                            original_prev_hash, original_row_hash, repaired_prev_hash, repaired_row_hash, change_type
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'REALIGNED_PREDECESSOR')
                    """, (
                        batch_id, now_str, clean_admin, clean_reason,
                        row_id, r.get("login_time"), r.get("username"), r.get("role"), r.get("status"),
                        r.get("ip_address"), r.get("action_type"), r.get("target"), r.get("details"),
                        orig_prev, orig_row_h, repaired_prev, repaired_row_h
                    ))

                    # 2. Update login_history
                    c.execute(
                        "UPDATE login_history SET prev_hash = ?, row_hash = ? WHERE id = ?",
                        (repaired_prev, repaired_row_h, row_id)
                    )

                    manifest_records.append({
                        "batch_id": batch_id,
                        "timestamp": now_str,
                        "authorized_by": clean_admin,
                        "row_id": row_id,
                        "action_type": r.get("action_type"),
                        "target": r.get("target"),
                        "original_prev_hash": orig_prev,
                        "repaired_prev_hash": repaired_prev,
                        "original_row_hash": orig_row_h,
                        "repaired_row_hash": repaired_row_h,
                    })

                    realigned_count += 1
                    expected_prev = repaired_row_h
                else:
                    expected_prev = orig_row_h

            # Step 3: Record an immutable audit log entry documenting the recovery
            audit_prev = expected_prev
            c.execute("""
                INSERT INTO login_history (
                    username, role, login_time, status, ip_address, action_type, target, details, prev_hash, row_hash, is_immutable
                ) VALUES (?, 'Administrator', ?, 'Success', '127.0.0.1', 'AUDIT_CHAIN_RECOVERY', 'login_history', ?, ?, '', 1)
            """, (
                clean_admin, now_str,
                f"Authorized audit chain continuity recovery executed (Batch: {batch_id}). Realigned {realigned_count} records. Pre-repair backup created. Reason: {clean_reason}",
                audit_prev
            ))
            recovery_audit_id = c.lastrowid
            recovery_dict = {
                "id": recovery_audit_id,
                "username": clean_admin,
                "role": "Administrator",
                "login_time": now_str,
                "status": "Success",
                "ip_address": "127.0.0.1",
                "action_type": "AUDIT_CHAIN_RECOVERY",
                "target": "login_history",
                "details": f"Authorized audit chain continuity recovery executed (Batch: {batch_id}). Realigned {realigned_count} records. Pre-repair backup created. Reason: {clean_reason}",
                "is_immutable": 1,
            }
            rec_row_h = _compute_audit_row_hash(audit_prev, recovery_dict)
            c.execute("UPDATE login_history SET row_hash = ? WHERE id = ?", (rec_row_h, recovery_audit_id))

            c.execute("COMMIT")
            conn.close()

            manifest_csv = export_audit_recovery_manifest_csv(batch_id=batch_id)
            return True, f"Successfully executed authorized chain continuity recovery (Batch: {batch_id}). Realigned {realigned_count} records. All original evidence archived.", manifest_csv

        except Exception as e:
            try:
                c.execute("ROLLBACK")
            except Exception:
                pass
            try:
                conn.close()
            except Exception:
                pass
            return False, f"Recovery failed due to error: {str(e)}", None


def export_audit_recovery_manifest_csv(batch_id=None):
    """Exports cryptographic evidence archive of chain continuity repairs as a CSV."""
    conn = get_db_connection()
    c = conn.cursor()
    try:
        c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='audit_evidence_archive'")
        if not c.fetchone():
            conn.close()
            return "recovery_batch_id,recovery_timestamp,authorized_by,compliance_reason,row_id,original_prev_hash,repaired_prev_hash,original_row_hash,repaired_row_hash\n"

        if batch_id:
            c.execute("SELECT * FROM audit_evidence_archive WHERE recovery_batch_id = ? ORDER BY id ASC", (str(batch_id),))
        else:
            c.execute("SELECT * FROM audit_evidence_archive ORDER BY id ASC")
        rows = c.fetchall()
        conn.close()

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow([
            "recovery_batch_id", "recovery_timestamp", "authorized_by", "compliance_reason",
            "row_id", "original_login_time", "original_username", "original_action_type", "original_target",
            "original_prev_hash", "repaired_prev_hash", "original_row_hash", "repaired_row_hash", "change_type"
        ])
        for r in rows:
            writer.writerow([
                sanitize_csv_cell(r["recovery_batch_id"]),
                sanitize_csv_cell(r["recovery_timestamp"]),
                sanitize_csv_cell(r["authorized_by"]),
                sanitize_csv_cell(r["compliance_reason"]),
                r["row_id"],
                sanitize_csv_cell(r["original_login_time"]),
                sanitize_csv_cell(r["original_username"]),
                sanitize_csv_cell(r["original_action_type"]),
                sanitize_csv_cell(r["original_target"]),
                r["original_prev_hash"],
                r["repaired_prev_hash"],
                r["original_row_hash"],
                r["repaired_row_hash"],
                sanitize_csv_cell(r["change_type"]),
            ])
        return output.getvalue()
    except Exception:
        conn.close()
        return "error\nFailed to export recovery manifest\n"




def get_login_history(
    limit=500,
    action_type=None,
    username=None,
    status=None,
    start_date=None,
    end_date=None,
    exclude_test_accounts=False,
    current_admin_user=None,
):
    """Retrieves audit trail with optional filtering, date-range, and test-account exclusion, sorted newest first."""
    if current_admin_user is not None and not is_admin_user(current_admin_user):
        record_audit_event(
            username=current_admin_user or "unknown",
            action_type="UNAUTHORIZED_ACCESS",
            target="login_history",
            details="Unauthorized attempt to read audit logs",
            status="Denied",
        )
        return []
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
    if start_date:
        s_str = str(start_date).strip()[:10] + " 00:00:00"
        query += " AND login_time >= ?"
        params.append(s_str)
    if end_date:
        e_str = str(end_date).strip()[:10] + " 23:59:59"
        query += " AND login_time <= ?"
        params.append(e_str)
    query += " ORDER BY id DESC LIMIT ?"
    params.append(int(limit))
    c.execute(query, params)
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    if exclude_test_accounts:
        rows = [
            r for r in rows
            if not is_test_account(r.get("username", "")) and not is_test_account(r.get("target", ""))
        ]
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
    Part 3 Privacy: Even Administrators CANNOT open or read another user's private analysis_history record.
    """
    clean_user = str(username).strip() if username else ""
    if not record_id or not clean_user:
        return None
    try:
        create_users_table()
        conn = get_db_connection()
        c = conn.cursor()
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
                details="Blocked attempt to read/view a private analysis record not owned by user",
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
    Retrieves PDF report bytes for a record only after verifying record ownership
    in the data-access layer. Returns None if unauthorized (including for admins).
    """
    rec = get_analysis_record(record_id, username=username)
    if not rec:
        return None
    return rec.get("pdf") or b""


class _PurgeAuditResult(tuple):
    """2-tuple (success, message) that also exposes .csv_data, .archive_path, and .purged_count."""
    def __new__(cls, success, message, csv_data="", archive_path="", purged_count=0):
        instance = super().__new__(cls, (bool(success), str(message)))
        instance.csv_data = csv_data
        instance.archive_path = archive_path
        instance.purged_count = purged_count
        return instance


def purge_audit_history(older_than_days=90, reason="", current_admin_user=None, ip="127.0.0.1"):
    """
    Part 2.4: Purges audit entries ONLY older than N days (N >= retention setting, default 90).
    Requires a typed reason, forces an automatic CSV export archive first, blocks 'purge all',
    and writes an immutable LOG_PURGE record that can NEVER be purged.
    """
    if not is_admin_user(current_admin_user):
        record_audit_event(
            username=current_admin_user or "unknown",
            action_type="UNAUTHORIZED_ACCESS",
            target="login_history",
            details="Unauthorized attempt to purge audit log",
            status="Denied",
            ip=ip,
        )
        return _PurgeAuditResult(False, "Access Denied: Administrator role required.")

    min_retention = int(get_platform_setting("audit_retention_days", 90))
    if older_than_days is None:
        return _PurgeAuditResult(
            False,
            f"Policy Safeguard: 'Purge All' is strictly blocked. You may only purge records older than the retention window (>= {min_retention} days).",
        )
    try:
        days_val = int(older_than_days)
    except Exception:
        return _PurgeAuditResult(False, "Invalid retention days value.")

    if days_val < min_retention or days_val <= 0:
        return _PurgeAuditResult(
            False,
            f"Policy Safeguard: Retention days ({days_val}) must be at least the configured platform retention setting ({min_retention} days). 'Purge All' is blocked.",
        )

    clean_reason = str(reason or "").strip()
    if len(clean_reason) < 5:
        return _PurgeAuditResult(
            False,
            "Policy Safeguard: A descriptive reason (minimum 5 characters) is required to purge historical audit logs.",
        )

    create_users_table()
    cutoff_dt = datetime.now() - timedelta(days=days_val)
    cutoff_str = cutoff_dt.strftime("%Y-%m-%d %H:%M:%S")

    conn = get_db_connection()
    c = conn.cursor()
    # Select eligible non-immutable rows older than cutoff_str
    c.execute(
        """
        SELECT * FROM login_history
        WHERE login_time < ? AND COALESCE(is_immutable, 0) = 0 AND action_type != 'LOG_PURGE'
        ORDER BY id ASC
        """,
        (cutoff_str,),
    )
    to_purge = [dict(r) for r in c.fetchall()]

    # Force automatic CSV export before any purge
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Event ID", "Timestamp", "Username", "Role", "Action Type", "Status / Outcome", "IP Address", "Target", "Details", "Row Hash"])
    for l in to_purge:
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
            sanitize_csv_cell(l.get("row_hash", "")),
        ])
    csv_content = output.getvalue()
    os.makedirs(BACKUPS_DIR, exist_ok=True)
    archive_fn = f"audit_archive_pre_purge_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    archive_path = os.path.join(BACKUPS_DIR, archive_fn)
    try:
        with open(archive_path, "w", encoding="utf-8", newline="") as f:
            f.write(csv_content)
    except Exception:
        pass

    purged_count = len(to_purge)
    if purged_count > 0:
        earliest_ts = to_purge[0].get("login_time", "")
        latest_ts = to_purge[-1].get("login_time", "")
        date_range_str = f"{earliest_ts} to {latest_ts}"
        ids_to_del = [r["id"] for r in to_purge]
        placeholders = ",".join("?" for _ in ids_to_del)
        c.execute(f"DELETE FROM login_history WHERE id IN ({placeholders})", ids_to_del)
        anchor_tok = "PURGE_ANCHOR:" + hashlib.sha256(f"{current_admin_user}|{cutoff_str}|{purged_count}".encode("utf-8")).hexdigest()[:24]
        _reanchor_audit_hash_chain_after_purge(conn, purge_anchor_token=anchor_tok)
    else:
        date_range_str = f"before {cutoff_str} (0 matching records)"

    conn.commit()
    conn.close()

    # Write immutable purge record that can NEVER be purged
    record_audit_event(
        username=current_admin_user,
        action_type="LOG_PURGE",
        target=f"older_than_{days_val}d",
        details=f"Purged {purged_count} rows ({date_range_str}) | Reason: {clean_reason[:120]} | Archive: {archive_fn}",
        status="Audit Retention Purge",
        ip=ip,
        is_immutable=1,
    )
    return _PurgeAuditResult(
        True,
        f"Purged {purged_count} eligible audit record(s) older than {days_val} days. Immutable purge record written and CSV archive saved ({archive_fn}).",
        csv_data=csv_content,
        archive_path=archive_path,
        purged_count=purged_count,
    )


def clear_login_history(current_admin_user=None, older_than_days=None, reason=""):
    """
    Wrapper enforcing Part 2.4 audit log protection: 'purge all' (older_than_days=None) is blocked.
    Delegates to purge_audit_history.
    """
    return purge_audit_history(
        older_than_days=older_than_days,
        reason=reason,
        current_admin_user=current_admin_user,
    )


# ---------------------------------------------------------------------------
# AUTHENTICATION, LOCKOUT & USER MANAGEMENT (Parts 2.1, 2.2, 2.3, 2.5)
# ---------------------------------------------------------------------------
def check_account_lockout(username, ip="127.0.0.1"):
    """
    Checks whether (username, ip) or username is currently locked out due to failed logins.
    Returns (is_locked: bool, seconds_remaining: int, locked_until_str: str).
    """
    if not username:
        return False, 0, ""
    create_users_table()
    clean_u = str(username).strip()
    clean_ip = str(ip or "127.0.0.1").strip()
    conn = get_db_connection()
    c = conn.cursor()
    c.execute(
        "SELECT ip_address, failure_count, locked_until FROM account_lockouts WHERE username = ? AND ip_address IN (?, '*')",
        (clean_u, clean_ip),
    )
    rows = c.fetchall()
    now = datetime.now()
    for r in rows:
        lu = r["locked_until"]
        if lu:
            try:
                lu_dt = datetime.strptime(lu, "%Y-%m-%d %H:%M:%S")
                rem = (lu_dt - now).total_seconds()
                if rem > 0:
                    conn.close()
                    return True, int(rem), lu
                else:
                    # Expired lockout — reset it
                    c.execute(
                        "UPDATE account_lockouts SET failure_count = 0, locked_until = '' WHERE username = ? AND ip_address = ?",
                        (clean_u, r["ip_address"]),
                    )
                    conn.commit()
            except Exception:
                pass
    conn.close()
    return False, 0, ""


def _record_failed_login_attempt(username, ip="127.0.0.1"):
    """Increments failure count for (username, ip) and triggers lockout if threshold reached."""
    clean_u = str(username or "").strip()
    clean_ip = str(ip or "127.0.0.1").strip()
    if not clean_u:
        return False, 0
    threshold = int(get_platform_setting("lockout_threshold", 5))
    duration_min = int(get_platform_setting("lockout_duration_minutes", 15))
    now_dt = datetime.now()
    now_str = now_dt.strftime("%Y-%m-%d %H:%M:%S")

    conn = get_db_connection()
    c = conn.cursor()
    c.execute(
        "SELECT failure_count, last_failed_at, locked_until FROM account_lockouts WHERE username = ? AND ip_address = ?",
        (clean_u, clean_ip),
    )
    row = c.fetchone()
    new_count = 1
    if row:
        # Reset counter if previous failure was longer ago than lockout window
        last_str = row["last_failed_at"]
        if last_str:
            try:
                last_dt = datetime.strptime(last_str, "%Y-%m-%d %H:%M:%S")
                if (now_dt - last_dt).total_seconds() <= duration_min * 60:
                    new_count = int(row["failure_count"] or 0) + 1
            except Exception:
                new_count = int(row["failure_count"] or 0) + 1
        else:
            new_count = int(row["failure_count"] or 0) + 1

    locked_until_str = ""
    just_locked = False
    if new_count >= threshold:
        locked_until_str = (now_dt + timedelta(minutes=duration_min)).strftime("%Y-%m-%d %H:%M:%S")
        just_locked = True

    c.execute(
        """
        INSERT INTO account_lockouts (username, ip_address, failure_count, last_failed_at, locked_until)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(username, ip_address) DO UPDATE SET
            failure_count = excluded.failure_count,
            last_failed_at = excluded.last_failed_at,
            locked_until = excluded.locked_until
        """,
        (clean_u, clean_ip, new_count, now_str, locked_until_str),
    )
    conn.commit()
    conn.close()
    return just_locked, new_count


def clear_account_lockout(username, ip=None):
    """Clears failed login counters and lockout state for username."""
    if not username:
        return
    create_users_table()
    conn = get_db_connection()
    c = conn.cursor()
    if ip:
        c.execute("DELETE FROM account_lockouts WHERE username = ? AND ip_address = ?", (str(username).strip(), str(ip).strip()))
    else:
        c.execute("DELETE FROM account_lockouts WHERE username = ?", (str(username).strip(),))
    conn.commit()
    conn.close()


def signup_user(username, password, role=None, ip="127.0.0.1"):
    """
    Self-registration with server-side enforcement of registration toggle,
    default role setting, and strict rejection of forged Administrator roles.
    """
    create_users_table()
    clean_user = str(username or "").strip()
    if not clean_user:
        return False, "Username is required."
    if not password or len(str(password)) < 4:
        return False, "Password must be at least 4 characters."

    # Enforce registration_enabled platform setting (except for built-in Student_Demo)
    reg_enabled = str(get_platform_setting("registration_enabled", "true")).lower() in ("true", "1", "yes")
    if not reg_enabled and clean_user != "Student_Demo":
        record_audit_event(
            username=clean_user,
            action_type="REGISTRATION",
            target=clean_user,
            details="Self-registration blocked because registration is disabled in Platform Settings",
            status="Denied",
            role="Unknown",
            ip=ip,
        )
        return False, "New account registration is currently disabled by the platform administrator."

    # Part 2.1 & Part 5.3: Self-registration can NEVER create an Administrator; forged admin role fails!
    default_role = get_platform_setting("default_role", "Student")
    if default_role not in ("Student", "Researcher"):
        default_role = "Student"

    if role is None or str(role).strip() == "":
        clean_role = default_role
    else:
        raw_r = str(role).strip()
        low_r = raw_r.lower()
        if low_r in ("student", "student (demo access)"):
            clean_role = "Student"
        elif low_r == "researcher":
            clean_role = "Researcher"
        else:
            # Forged or unpermitted role (e.g. Administrator, Admin, Superuser) -> fail & audit log!
            record_audit_event(
                username=clean_user,
                action_type="UNAUTHORIZED_ACCESS",
                target=clean_user,
                details=f"Blocked self-registration attempt with forbidden role '{raw_r}'",
                status="Denied: Forged Role",
                role="Unknown",
                ip=ip,
            )
            return False, f"Registration denied: Role '{raw_r}' is not permitted for self-registration."

    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT username FROM users WHERE username = ?", (clean_user,))
    existing = c.fetchone()
    if existing:
        conn.close()
        return False, "Username already exists. Please choose another."

    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    c.execute(
        "INSERT INTO users (username, password, role, created_at, status, must_change_password) VALUES (?, ?, ?, ?, 'Active', 0)",
        (clean_user, hash_password(password), clean_role, now_str),
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
        ip=ip,
    )
    return True, "Account created successfully!"


def login_user(username, password, ip="127.0.0.1"):
    """
    Authenticates user with failed-login lockout protection (Part 2.5),
    gradual lossless PBKDF2 hash upgrade (Part 2.6), and forced password reset flag (Part 2.2).
    """
    create_users_table()
    clean_user = str(username or "").strip()
    clean_ip = str(ip or "127.0.0.1").strip()
    if not clean_user or password is None:
        return None

    # 1. Check active lockout before verifying credentials
    is_locked, rem_sec, locked_until = check_account_lockout(clean_user, clean_ip)
    if is_locked:
        record_audit_event(
            username=clean_user,
            action_type="LOGIN_LOCKOUT",
            target=clean_user,
            details=f"Login blocked during active lockout (until {locked_until})",
            status="Failed: Account Locked",
            role="Unknown",
            ip=clean_ip,
        )
        return None

    conn = get_db_connection()
    c = conn.cursor()
    c.execute(
        "SELECT username, password, role, theme_preference, status, created_at, COALESCE(must_change_password, 0) as must_change_password FROM users WHERE username = ?",
        (clean_user,),
    )
    user = c.fetchone()
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    if user and verify_password(password, user["password"]):
        stored_hash = user["password"]
        role = user["role"] if user["role"] else "Student"
        status = user["status"] if "status" in user.keys() and user["status"] else "Active"
        created_at = user["created_at"] if "created_at" in user.keys() and user["created_at"] else "2026-03-01 00:00:00"
        must_change = bool(user["must_change_password"])
        theme = user["theme_preference"] if ("theme_preference" in user.keys() and user["theme_preference"]) else "System"

        # Part 2.6: Gradual lossless hash upgrade if user had a legacy SHA-256 hash
        hash_upgraded = False
        if is_legacy_hash(stored_hash):
            new_strong_hash = hash_password_strong(password)
            c.execute("UPDATE users SET password = ? WHERE username = ?", (new_strong_hash, clean_user))
            hash_upgraded = True

        if status == "Disabled":
            conn.commit()
            conn.close()
            record_audit_event(
                username=clean_user,
                action_type="LOGIN",
                target=clean_user,
                details="Login denied: Account is deactivated by an administrator",
                status="Failed: Account Disabled",
                role=role,
                ip=clean_ip,
            )
            return {
                "username": user["username"],
                "role": role,
                "status": "Disabled",
                "created_at": created_at,
                "disabled": True,
            }

        # Clear any failed login attempts and update last_login timestamp
        c.execute("UPDATE users SET last_login = ? WHERE username = ?", (now_str, clean_user))
        conn.commit()
        conn.close()
        clear_account_lockout(clean_user, clean_ip)

        if hash_upgraded:
            record_audit_event(
                username=clean_user,
                action_type="PASSWORD_HASH_UPGRADE",
                target=clean_user,
                details="Legacy SHA-256 credential hash transparently upgraded to PBKDF2-HMAC-SHA256",
                status="Success",
                role=role,
                ip=clean_ip,
            )

        record_audit_event(
            username=clean_user,
            action_type="LOGIN",
            target=clean_user,
            details="User authenticated successfully",
            status="Success",
            role=role,
            ip=clean_ip,
        )
        return {
            "username": user["username"],
            "role": role,
            "theme_preference": theme,
            "status": "Active",
            "created_at": created_at,
            "last_login": now_str,
            "must_change_password": must_change,
        }
    else:
        conn.close()
        just_locked, fail_cnt = _record_failed_login_attempt(clean_user, clean_ip)
        if just_locked:
            dur_min = int(get_platform_setting("lockout_duration_minutes", 15))
            record_audit_event(
                username=clean_user,
                action_type="LOGIN_LOCKOUT",
                target=clean_user,
                details=f"Account locked for {dur_min} minutes after {fail_cnt} consecutive failed login attempts",
                status="Failed: Lockout Triggered",
                role="Unknown",
                ip=clean_ip,
            )
        else:
            record_audit_event(
                username=clean_user,
                action_type="LOGIN",
                target=clean_user,
                details=f"Invalid credentials supplied (attempt {fail_cnt})",
                status="Failed: Invalid Credentials",
                role="Unknown",
                ip=clean_ip,
            )
        return None


def get_user_created_at(username):
    """Fetch the real registration timestamp (created_at) for `username` from the users table."""
    if not username:
        return ""
    create_users_table()
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT created_at FROM users WHERE username = ?", (str(username).strip(),))
    row = c.fetchone()
    conn.close()
    if row and row["created_at"]:
        return str(row["created_at"])
    return ""


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


def get_all_users(current_admin_user=None):
    """Retrieves all registered users with metadata, last_login, and analysis counts (never includes password hashes)."""
    if current_admin_user is not None and not is_admin_user(current_admin_user):
        record_audit_event(
            username=current_admin_user or "unknown",
            action_type="UNAUTHORIZED_ACCESS",
            target="users",
            details="Unauthorized attempt to list all registered user accounts",
            status="Denied",
        )
        return []
    create_users_table()
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("""
        SELECT u.username, u.role, u.theme_preference, u.created_at, u.status,
               COALESCE(u.must_change_password, 0) as must_change_password,
               COALESCE(u.last_login, '') as last_login,
               COUNT(ah.id) as analysis_count
        FROM users u
        LEFT JOIN analysis_history ah ON u.username = ah.username
        GROUP BY u.username, u.role, u.theme_preference, u.created_at, u.status, u.must_change_password, u.last_login
        ORDER BY u.created_at DESC, u.username ASC
    """)
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    return rows


def toggle_user_status(username, new_status, current_admin_user=None, ip="127.0.0.1"):
    """Enables or disables a user account with self-lockout and last-admin safeguards."""
    clean_user = str(username or "").strip()
    clean_admin = str(current_admin_user or "").strip()
    if not is_admin_user(clean_admin):
        record_audit_event(
            username=clean_admin or "unknown",
            action_type="UNAUTHORIZED_ACCESS",
            target=clean_user,
            details="Unauthorized attempt to modify user account status",
            status="Denied",
            ip=ip,
        )
        return False, "Access Denied: Administrator role required."
    if clean_user == clean_admin and new_status == "Disabled":
        return False, "Self-lockout safeguard: You cannot deactivate your own currently active Administrator account."
    if new_status not in ("Active", "Disabled"):
        return False, "Invalid account status."
    create_users_table()
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT role, status FROM users WHERE username = ?", (clean_user,))
    row = c.fetchone()
    if not row:
        conn.close()
        return False, f"User '{clean_user}' not found."
    old_status = row["status"] or "Active"
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
        username=clean_admin,
        action_type="STATUS_CHANGE",
        target=clean_user,
        details=f"Account status of '{clean_user}' changed from '{old_status}' to '{new_status}'",
        status="Success",
        ip=ip,
    )
    return True, f"Account '{clean_user}' is now {new_status}."


def bulk_update_user_status(usernames, new_status, current_admin_user=None, ip="127.0.0.1"):
    """Part 4.5: Bulk enable/disable user accounts while respecting self-lockout and last-admin safeguards."""
    clean_admin = str(current_admin_user or "").strip()
    if not is_admin_user(clean_admin):
        record_audit_event(
            username=clean_admin or "unknown",
            action_type="UNAUTHORIZED_ACCESS",
            target="bulk_users",
            details="Unauthorized attempt to execute bulk status change",
            status="Denied",
            ip=ip,
        )
        return False, "Access Denied: Administrator role required.", 0
    if not usernames:
        return False, "No users selected for bulk action.", 0
    updated = 0
    skipped = []
    for u in usernames:
        ok, msg = toggle_user_status(u, new_status, current_admin_user=clean_admin, ip=ip)
        if ok:
            updated += 1
        else:
            skipped.append(f"{u} ({msg})")
    summary_msg = f"Updated {updated} account(s) to '{new_status}'."
    if skipped:
        summary_msg += f" Skipped {len(skipped)}: " + "; ".join(skipped[:3])
    return updated > 0, summary_msg, updated


def update_user_role(username, new_role, current_admin_user=None, confirm_username=None, ip="127.0.0.1"):
    """
    Part 2.1: Updates user role with strict guardrails:
    - Admin cannot demote their own account.
    - Last remaining active Administrator can never be demoted.
    - Granting Administrator requires second explicit confirmation (typing the username).
    - Only permitted roles (Student, Researcher, Administrator) allowed.
    """
    clean_user = str(username or "").strip()
    clean_admin = str(current_admin_user or "").strip()
    clean_new_role = str(new_role or "").strip()
    if not is_admin_user(clean_admin):
        record_audit_event(
            username=clean_admin or "unknown",
            action_type="UNAUTHORIZED_ACCESS",
            target=clean_user,
            details=f"Unauthorized attempt to modify academic role to '{clean_new_role}'",
            status="Denied",
            ip=ip,
        )
        return False, "Access Denied: Administrator role required."

    if clean_new_role not in ("Student", "Researcher", "Administrator"):
        return False, f"Invalid role '{clean_new_role}'. Permitted roles are Student, Researcher, and Administrator."

    create_users_table()
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT role, status FROM users WHERE username = ?", (clean_user,))
    row = c.fetchone()
    if not row:
        conn.close()
        return False, f"User '{clean_user}' not found."

    old_role = row["role"]
    # Self-demotion safeguard
    if clean_user == clean_admin and clean_new_role != "Administrator":
        conn.close()
        return False, "Self-lockout safeguard: You cannot demote your own Administrator account."

    # Last active admin safeguard
    if old_role == "Administrator" and clean_new_role != "Administrator":
        c.execute("SELECT COUNT(*) FROM users WHERE role = 'Administrator' AND status != 'Disabled'")
        active_admins = c.fetchone()[0]
        if active_admins <= 1:
            conn.close()
            return False, "Safeguard: Cannot demote the only remaining active Administrator account."

    # Second explicit confirmation required when granting Administrator role
    if clean_new_role == "Administrator" and old_role != "Administrator":
        if confirm_username is not None and str(confirm_username).strip() != clean_user:
            conn.close()
            return False, f"Confirmation required: Please type the exact username '{clean_user}' to grant Administrator privileges."

    c.execute("UPDATE users SET role = ? WHERE username = ?", (clean_new_role, clean_user))
    conn.commit()
    conn.close()
    record_audit_event(
        username=clean_admin,
        action_type="ROLE_CHANGE",
        target=clean_user,
        details=f"Role for '{clean_user}' changed from '{old_role}' to '{clean_new_role}'",
        status="Success",
        ip=ip,
    )
    return True, f"Role for '{clean_user}' updated from '{old_role}' to '{clean_new_role}'."


def get_user_role_history(username, current_admin_user=None):
    """Part 4.5: Returns per-user role-change and status-change history from login_history."""
    if current_admin_user is not None and not is_admin_user(current_admin_user):
        return []
    create_users_table()
    clean_u = str(username or "").strip()
    conn = get_db_connection()
    c = conn.cursor()
    c.execute(
        """
        SELECT id, login_time, username as actor, action_type, status, target, details, ip_address
        FROM login_history
        WHERE target = ? AND action_type IN ('ROLE_CHANGE', 'LEGACY_ROLE_MIGRATION', 'REGISTRATION', 'STATUS_CHANGE', 'PASSWORD_RESET')
        ORDER BY id DESC
        """,
        (clean_u,),
    )
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    return rows


class _ResetPasswordResult(tuple):
    """
    Hybrid 2-tuple (success, message) return object that also exposes
    .temp_password (for one-time admin display) and .must_change_password.
    """
    def __new__(cls, success, message, temp_password="", must_change_password=True):
        instance = super().__new__(cls, (bool(success), str(message)))
        instance.temp_password = temp_password
        instance.must_change_password = must_change_password
        return instance


def admin_reset_password(username, new_password=None, current_admin_user=None, ip="127.0.0.1"):
    """
    Part 2.2: Safer Reset Password.
    Generates a random 14-character temporary password via secrets (if new_password is None),
    stores ONLY its PBKDF2 hash, sets must_change_password = 1, and logs the action without the password.
    """
    # Support calling admin_reset_password(username, current_admin_user="admin") or (username, "admin")
    if current_admin_user is None and new_password is not None and is_admin_user(new_password):
        current_admin_user = new_password
        new_password = None

    clean_user = str(username or "").strip()
    clean_admin = str(current_admin_user or "").strip()
    if not is_admin_user(clean_admin):
        record_audit_event(
            username=clean_admin or "unknown",
            action_type="UNAUTHORIZED_ACCESS",
            target=clean_user,
            details="Unauthorized attempt to reset user password",
            status="Denied",
            ip=ip,
        )
        return _ResetPasswordResult(False, "Access Denied: Administrator role required.", temp_password="")

    if new_password is None or str(new_password).strip() == "":
        temp_pw = generate_temp_password(14)
    else:
        temp_pw = str(new_password)
        if len(temp_pw) < 4:
            return _ResetPasswordResult(False, "Password must be at least 4 characters.", temp_password="")

    try:
        create_users_table()
        conn = get_db_connection()
        c = conn.cursor()
        c.execute("SELECT username FROM users WHERE username = ?", (clean_user,))
        if not c.fetchone():
            conn.close()
            return _ResetPasswordResult(False, f"User '{clean_user}' not found.", temp_password="")
        c.execute(
            "UPDATE users SET password = ?, must_change_password = 1 WHERE username = ?",
            (hash_password_strong(temp_pw), clean_user),
        )
        conn.commit()
        conn.close()
        clear_account_lockout(clean_user)
        record_audit_event(
            username=clean_admin,
            action_type="PASSWORD_RESET",
            target=clean_user,
            details=f"One-time temporary password issued for '{clean_user}' (must_change_password=1)",
            status="Success",
            ip=ip,
        )
        return _ResetPasswordResult(
            True,
            f"Temporary password generated for '{clean_user}'. User must change password at next login.",
            temp_password=temp_pw,
            must_change_password=True,
        )
    except Exception as e:
        return _ResetPasswordResult(False, str(e), temp_password="")


def change_user_password(username, current_password, new_password, ip="127.0.0.1"):
    """
    Allows a user (especially one with must_change_password=1) to set a new password
    after verifying their current/temporary password. Clears must_change_password = 0.
    """
    clean_u = str(username or "").strip()
    if not clean_u or not current_password or not new_password:
        return False, "Current and new passwords are required."
    if len(str(new_password)) < 6:
        return False, "New password must be at least 6 characters."
    if str(new_password) == str(current_password):
        return False, "New password must be different from the temporary/current password."

    create_users_table()
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT password, role FROM users WHERE username = ?", (clean_u,))
    row = c.fetchone()
    if not row or not verify_password(current_password, row["password"]):
        conn.close()
        record_audit_event(
            username=clean_u,
            action_type="PASSWORD_CHANGE",
            target=clean_u,
            details="Password change failed: current password verification failed",
            status="Failed",
            ip=ip,
        )
        return False, "Current/temporary password is incorrect."

    c.execute(
        "UPDATE users SET password = ?, must_change_password = 0 WHERE username = ?",
        (hash_password_strong(new_password), clean_u),
    )
    conn.commit()
    conn.close()
    record_audit_event(
        username=clean_u,
        action_type="PASSWORD_CHANGE",
        target=clean_u,
        details="User updated password and cleared must_change_password flag",
        status="Success",
        role=row["role"],
        ip=ip,
    )
    return True, "Password updated successfully."


def delete_user_account(username, current_admin_user=None, confirm_username=None, mode="delete_all", ip="127.0.0.1"):
    """
    Part 2.3: Permanently deletes user account and associated data (or anonymizes) with safeguards:
    - Admin cannot delete their own account.
    - Last remaining Administrator cannot be deleted.
    - Typed username confirmation verified when confirm_username is provided.
    - Audit trail entries in login_history are preserved with username as text.
    """
    clean_user = str(username or "").strip()
    clean_admin = str(current_admin_user or "").strip()
    if not is_admin_user(clean_admin):
        record_audit_event(
            username=clean_admin or "unknown",
            action_type="UNAUTHORIZED_ACCESS",
            target=clean_user,
            details="Unauthorized attempt to delete user account",
            status="Denied",
            ip=ip,
        )
        return False, "Access Denied: Administrator role required."
    if clean_user == clean_admin:
        return False, "Self-lockout safeguard: You cannot delete your own currently active Administrator account."
    if confirm_username is not None and str(confirm_username).strip() != clean_user:
        return False, f"Confirmation failed: You must type the exact username '{clean_user}' to confirm deletion."

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
            c.execute("SELECT COUNT(*) FROM users WHERE role = 'Administrator' AND status != 'Disabled'")
            cnt = c.fetchone()[0]
            if cnt <= 1:
                conn.close()
                return False, "Safeguard: Cannot delete the only remaining active Administrator account."

        if mode == "anonymize":
            anon_id = "anon_" + hashlib.sha256(clean_user.encode("utf-8")).hexdigest()[:8]
            c.execute("UPDATE analysis_history SET username = ? WHERE username = ?", (anon_id, clean_user))
            c.execute("UPDATE upload_history SET username = ? WHERE username = ?", (anon_id, clean_user))
            for tbl in ("projects", "project_papers", "paper_metadata", "tags", "paper_tags", "research_notes", "saved_comparisons", "paper_chats", "activity_log"):
                try:
                    c.execute(f"UPDATE {tbl} SET user_id = ? WHERE user_id = ?", (anon_id, clean_user))
                except Exception:
                    pass
            c.execute("DELETE FROM users WHERE username = ?", (clean_user,))
            c.execute("DELETE FROM account_lockouts WHERE username = ?", (clean_user,))
            detail_msg = f"Account '{clean_user}' deleted and records anonymized as '{anon_id}' (audit trail preserved)"
        else:
            # Default: delete_all (deletes user's papers, analyses, projects, notes, chats, uploads; preserves login_history)
            c.execute("DELETE FROM analysis_history WHERE username = ?", (clean_user,))
            c.execute("DELETE FROM upload_history WHERE username = ?", (clean_user,))
            for tbl in ("project_papers", "projects", "paper_metadata", "paper_tags", "tags", "research_notes", "saved_comparisons", "paper_chats", "activity_log"):
                try:
                    c.execute(f"DELETE FROM {tbl} WHERE user_id = ?", (clean_user,))
                except Exception:
                    pass
            c.execute("DELETE FROM users WHERE username = ?", (clean_user,))
            c.execute("DELETE FROM account_lockouts WHERE username = ?", (clean_user,))
            detail_msg = f"Account '{clean_user}' and all associated analyses, projects, notes, and chats permanently deleted (audit trail preserved)"

        conn.commit()
        conn.close()
        record_audit_event(
            username=clean_admin,
            action_type="USER_DELETE",
            target=clean_user,
            details=detail_msg,
            status="Success",
            ip=ip,
        )
        return True, f"User account '{clean_user}' deleted ({mode})."
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
        c.execute("INSERT INTO users (username, password, role, theme_preference, created_at, status, must_change_password) VALUES (?, ?, 'Administrator', 'System', ?, 'Active', 0)", (u, hash_password(password), now_str))
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
# PLATFORM SETTINGS MODULE (Part 1.6)
# ---------------------------------------------------------------------------
def get_platform_settings():
    """Returns all platform settings as a dict merged with DEFAULT_PLATFORM_SETTINGS."""
    create_users_table()
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT key, value, updated_at, updated_by FROM app_settings")
    rows = c.fetchall()
    conn.close()
    result = dict(DEFAULT_PLATFORM_SETTINGS)
    for r in rows:
        result[r["key"]] = r["value"]
    return result


def get_platform_settings_with_meta():
    """Returns all platform settings with value, updated_at, updated_by, and spec metadata."""
    create_users_table()
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT key, value, updated_at, updated_by FROM app_settings")
    rows = {r["key"]: dict(r) for r in c.fetchall()}
    conn.close()
    out = {}
    for k, default_val in DEFAULT_PLATFORM_SETTINGS.items():
        row = rows.get(k, {})
        out[k] = {
            "key": k,
            "value": row.get("value", default_val),
            "updated_at": row.get("updated_at", ""),
            "updated_by": row.get("updated_by", "system"),
            "spec": PLATFORM_SETTINGS_SPECS.get(k, {}),
        }
    return out


def get_platform_setting(key, default=None):
    """Returns a single platform setting value from app_settings."""
    if default is None:
        default = DEFAULT_PLATFORM_SETTINGS.get(key)
    try:
        create_users_table()
        conn = get_db_connection()
        c = conn.cursor()
        c.execute("SELECT value FROM app_settings WHERE key = ?", (str(key),))
        row = c.fetchone()
        conn.close()
        if row and row["value"] is not None:
            return row["value"]
    except Exception:
        pass
    return default


def validate_platform_setting(key, value):
    """
    Validates a platform setting key and value against PLATFORM_SETTINGS_SPECS.
    Rejects unknown keys, out-of-range numbers, and invalid enum/format values.
    Returns (is_valid: bool, normalized_str_value: str, error_message: str).
    """
    clean_key = str(key or "").strip()
    if clean_key not in PLATFORM_SETTINGS_SPECS:
        return False, "", f"Unknown or unpermitted setting key '{clean_key}'."

    spec = PLATFORM_SETTINGS_SPECS[clean_key]
    stype = spec.get("type")

    if stype == "int":
        try:
            if isinstance(value, bool):
                return False, "", f"Setting '{clean_key}' must be an integer."
            ival = int(str(value).strip())
        except Exception:
            return False, "", f"Setting '{clean_key}' must be a valid integer."
        min_v = spec.get("min", 1)
        max_v = spec.get("max", 10000)
        if ival < min_v or ival > max_v:
            return False, "", f"Setting '{clean_key}' must be between {min_v} and {max_v} (got {ival})."
        return True, str(ival), ""

    elif stype == "bool":
        sval = str(value).strip().lower()
        if sval in ("true", "1", "yes", "on"):
            return True, "true", ""
        elif sval in ("false", "0", "no", "off"):
            return True, "false", ""
        return False, "", f"Setting '{clean_key}' must be a boolean (true/false)."

    elif stype == "enum":
        sval = str(value or "").strip()
        options = spec.get("options", [])
        if sval not in options:
            return False, "", f"Setting '{clean_key}' must be one of {options} (got '{sval}')."
        return True, sval, ""

    elif stype == "formats":
        if isinstance(value, (list, tuple, set)):
            parts = [str(p).strip().upper().lstrip(".") for p in value if str(p).strip()]
        else:
            parts = [p.strip().upper().lstrip(".") for p in str(value or "").split(",") if p.strip()]
        allowed_set = set(spec.get("options", ["PDF", "DOCX", "TXT"]))
        if not parts:
            return False, "", "At least one file format (PDF, DOCX, or TXT) must be enabled."
        invalid = [p for p in parts if p not in allowed_set]
        if invalid:
            return False, "", f"Unsupported file format(s): {', '.join(invalid)}. Allowed: PDF, DOCX, TXT."
        deduped = []
        for p in ("PDF", "DOCX", "TXT"):
            if p in parts:
                deduped.append(p)
        return True, ",".join(deduped), ""

    elif stype == "str":
        sval = re.sub(r"[\r\n\t]+", " ", str(value if value is not None else "")).strip()
        max_len = spec.get("max_len", 280)
        if len(sval) > max_len:
            return False, "", f"Setting '{clean_key}' exceeds maximum length of {max_len} characters."
        return True, sval, ""

    return False, "", f"Unsupported setting specification for '{clean_key}'."


def update_platform_setting(key, value, current_admin_user=None, ip="127.0.0.1"):
    """
    Validates and updates a single platform setting in app_settings,
    logging old and new values in login_history.
    """
    clean_admin = str(current_admin_user or "").strip()
    if not is_admin_user(clean_admin):
        record_audit_event(
            username=clean_admin or "unknown",
            action_type="UNAUTHORIZED_ACCESS",
            target=f"app_settings:{key}",
            details="Unauthorized attempt to modify platform settings",
            status="Denied",
            ip=ip,
        )
        return False, "Access Denied: Administrator role required."

    ok, norm_val, err_msg = validate_platform_setting(key, value)
    if not ok:
        return False, err_msg

    create_users_table()
    old_val = get_platform_setting(key, "")
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn = get_db_connection()
    c = conn.cursor()
    c.execute(
        """
        INSERT INTO app_settings (key, value, updated_at, updated_by)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(key) DO UPDATE SET
            value = excluded.value,
            updated_at = excluded.updated_at,
            updated_by = excluded.updated_by
        """,
        (str(key).strip(), norm_val, now_str, clean_admin),
    )
    conn.commit()
    conn.close()

    if str(old_val) != str(norm_val):
        record_audit_event(
            username=clean_admin,
            action_type="SETTINGS_UPDATE",
            target=str(key).strip(),
            details=f"Setting '{key}' changed from '{old_val}' to '{norm_val}'",
            status="Success",
            ip=ip,
        )
    return True, f"Setting '{key}' updated to '{norm_val}'."


def update_platform_settings_bulk(settings_dict, current_admin_user=None, ip="127.0.0.1"):
    """
    Validates all settings in settings_dict first; if all are valid, saves them
    and writes audit entries for every changed setting.
    """
    clean_admin = str(current_admin_user or "").strip()
    if not is_admin_user(clean_admin):
        record_audit_event(
            username=clean_admin or "unknown",
            action_type="UNAUTHORIZED_ACCESS",
            target="app_settings",
            details="Unauthorized attempt to bulk-update platform settings",
            status="Denied",
            ip=ip,
        )
        return False, "Access Denied: Administrator role required."

    if not isinstance(settings_dict, dict) or not settings_dict:
        return False, "No settings provided."

    validated = {}
    for k, v in settings_dict.items():
        ok, norm_val, err_msg = validate_platform_setting(k, v)
        if not ok:
            return False, err_msg
        validated[k] = norm_val

    changed_keys = []
    for k, norm_val in validated.items():
        old_val = get_platform_setting(k, "")
        ok, msg = update_platform_setting(k, norm_val, current_admin_user=clean_admin, ip=ip)
        if not ok:
            return False, msg
        if str(old_val) != str(norm_val):
            changed_keys.append(k)

    if changed_keys:
        return True, f"Updated {len(changed_keys)} platform setting(s): {', '.join(changed_keys)}."
    return True, "Platform settings verified (no values changed)."


# ---------------------------------------------------------------------------
# APPLICATION ERROR LOG & PROCESSING EVENTS MODULE (Part 1.1)
# ---------------------------------------------------------------------------
def sanitize_error_message(message, max_len=300):
    """
    Part 1.1: Sanitizes exception messages for app_errors and processing_events.
    - Strips Windows and POSIX file paths and OS usernames.
    - Strips potential password/hash/secret tokens.
    - Truncates strictly to max_len (default 300 chars).
    - NEVER stores paper text, file contents, passwords, or secrets.
    """
    if message is None:
        return "Unknown error"
    s = str(message)
    # Strip Windows paths like C:\Users\username\...\file.py -> file.py
    s = re.sub(r"[A-Za-z]:\\(?:[^\\\s:\"<>|]+\\)*([^\\\s:\"<>|]+)", r"\1", s)
    # Strip POSIX paths like /home/username/.../file.py -> file.py
    s = re.sub(r"/(?:Users|home|var|tmp|opt|etc)/(?:[^/\s:\"<>|]+/)*([^/\s:\"<>|]+)", r"\1", s)
    # Redact anything looking like a password hash or secret key=value
    s = re.sub(r"pbkdf2_sha256\$\d+\$[A-Za-z0-9_\-+/=]+\$[A-Za-z0-9_\-+/=]+", "[REDACTED_HASH]", s)
    s = re.sub(r"(?i)(password|passwd|secret|token|api_key)\s*[:=]\s*['\"]?[^\s'\";,)]+", r"\1=[REDACTED]", s)
    s = re.sub(r"\b[a-fA-F0-9]{64}\b", "[REDACTED_HEX]", s)
    s = re.sub(r"\s+", " ", s).strip()
    if len(s) > max_len:
        s = s[: max_len - 3] + "..."
    return s or "Application error"


def compute_stack_hash(stack_info=""):
    """Computes a privacy-safe 16-char hash of sanitized stack frame locations."""
    if not stack_info:
        return "no_stack"
    clean_stack = sanitize_error_message(stack_info, max_len=1000)
    return hashlib.sha256(clean_stack.encode("utf-8")).hexdigest()[:16]


def log_app_error(error_type, message, page="Unknown", role="Unknown", user_id=None, stack_info="", stack_text=None, username=None):
    """
    Part 1.1: Logs an application exception into app_errors without exposing paths,
    usernames, secrets, or document contents.
    """
    try:
        create_users_table()
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        clean_type = sanitize_error_message(error_type or "Exception", max_len=80)
        clean_msg = sanitize_error_message(message or "Application error", max_len=300)
        clean_page = sanitize_error_message(page or "Unknown", max_len=80)
        clean_role = sanitize_error_message(role or "Unknown", max_len=40)
        eff_uid = user_id if user_id is not None else username
        clean_uid = str(eff_uid).strip()[:60] if eff_uid else None
        raw_stack = stack_text if stack_text is not None else stack_info
        shash = compute_stack_hash(raw_stack or f"{clean_type}:{clean_page}:{clean_msg}")

        conn = get_db_connection()
        c = conn.cursor()
        c.execute(
            """
            INSERT INTO app_errors (timestamp, user_id, role, page, error_type, message_short, stack_hash)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (now_str, clean_uid, clean_role, clean_page, clean_type, clean_msg, shash),
        )
        err_id = c.lastrowid
        conn.commit()
        conn.close()
        return err_id
    except Exception:
        return None


def get_app_errors(limit=200, start_date=None, end_date=None, error_type=None, page=None, current_admin_user=None):
    """Retrieves recent application errors for the System Health view."""
    if current_admin_user is not None and not is_admin_user(current_admin_user):
        return []
    create_users_table()
    conn = get_db_connection()
    c = conn.cursor()
    query = "SELECT id, timestamp, user_id, role, page, error_type, message_short, stack_hash FROM app_errors WHERE 1=1"
    params = []
    if start_date:
        query += " AND timestamp >= ?"
        params.append(str(start_date).strip()[:10] + " 00:00:00")
    if end_date:
        query += " AND timestamp <= ?"
        params.append(str(end_date).strip()[:10] + " 23:59:59")
    if error_type and error_type != "All Types":
        query += " AND error_type = ?"
        params.append(str(error_type).strip())
    if page and page != "All Pages":
        query += " AND page = ?"
        params.append(str(page).strip())
    query += " ORDER BY id DESC LIMIT ?"
    params.append(int(limit))
    c.execute(query, params)
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    return rows


def get_app_error_counts():
    """Returns count of application errors in the last 1h, 24h, 7d, and all-time."""
    create_users_table()
    now = datetime.now()
    cut_1h = (now - timedelta(hours=1)).strftime("%Y-%m-%d %H:%M:%S")
    cut_24h = (now - timedelta(hours=24)).strftime("%Y-%m-%d %H:%M:%S")
    cut_7d = (now - timedelta(days=7)).strftime("%Y-%m-%d %H:%M:%S")
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM app_errors WHERE timestamp >= ?", (cut_1h,))
    e_1h = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM app_errors WHERE timestamp >= ?", (cut_24h,))
    e_24h = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM app_errors WHERE timestamp >= ?", (cut_7d,))
    e_7d = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM app_errors")
    e_total = c.fetchone()[0]
    conn.close()
    return {
        "errors_1h": e_1h,
        "errors_24h": e_24h,
        "errors_7d": e_7d,
        "total_errors": e_total,
    }


def log_processing_event(
    user_id=None,
    file_type="PDF",
    file_size_kb=0.0,
    stage="analysis",
    status="success",
    failure_reason="",
    duration_ms=0.0,
    username=None,
):
    """
    Part 1.1: Logs every extraction/analysis/report run into processing_events.
    status must be 'success' or 'failed'. Never stores paper text or private filenames.
    """
    try:
        create_users_table()
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        eff_uid = user_id if user_id is not None else username
        clean_uid = str(eff_uid or "anonymous").strip()[:60]
        clean_ft = str(file_type or "UNKNOWN").strip().upper().lstrip(".")[:16]
        if clean_ft in ("APPLICATION/PDF",):
            clean_ft = "PDF"
        elif "WORD" in clean_ft or clean_ft == "DOC":
            clean_ft = "DOCX"
        elif "TEXT" in clean_ft:
            clean_ft = "TXT"
        clean_stage = str(stage or "analysis").strip()[:40]
        norm_status = "failed" if str(status).strip().lower() in ("failed", "error", "failure", "false") else "success"
        clean_reason = sanitize_error_message(failure_reason, max_len=160) if norm_status == "failed" else ""
        conn = get_db_connection()
        c = conn.cursor()
        c.execute(
            """
            INSERT INTO processing_events (timestamp, user_id, file_type, file_size_kb, stage, status, failure_reason, duration_ms)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                now_str,
                clean_uid,
                clean_ft,
                round(float(file_size_kb or 0.0), 2),
                clean_stage,
                norm_status,
                clean_reason,
                round(float(duration_ms or 0.0), 2),
            ),
        )
        ev_id = c.lastrowid
        conn.commit()
        conn.close()
        return ev_id
    except Exception:
        return None


def get_processing_events(
    limit=200,
    status_filter=None,
    status=None,
    start_date=None,
    end_date=None,
    exclude_test_accounts=False,
    current_admin_user=None,
):
    """Retrieves processing events (without private filenames or paper text)."""
    if current_admin_user is not None and not is_admin_user(current_admin_user):
        return []
    create_users_table()
    eff_status = status if status is not None else status_filter
    conn = get_db_connection()
    c = conn.cursor()
    query = "SELECT id, timestamp, user_id, file_type, file_size_kb, stage, status, failure_reason, duration_ms FROM processing_events WHERE 1=1"
    params = []
    if eff_status and eff_status in ("success", "failed"):
        query += " AND status = ?"
        params.append(eff_status)
    if start_date:
        query += " AND timestamp >= ?"
        params.append(str(start_date).strip()[:10] + " 00:00:00")
    if end_date:
        query += " AND timestamp <= ?"
        params.append(str(end_date).strip()[:10] + " 23:59:59")
    query += " ORDER BY id DESC LIMIT ?"
    params.append(int(limit))
    c.execute(query, params)
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    if exclude_test_accounts:
        rows = [r for r in rows if not is_test_account(r.get("user_id", ""))]
    return rows


def get_processing_stats(days=None, start_date=None, end_date=None, exclude_test_accounts=False):
    """
    Part 1.2 & Part 1.4: Computes aggregate processing statistics (succeeded vs failed,
    by file type, by day, average duration, failure reasons, and uploads per role).
    """
    create_users_table()
    conn = get_db_connection()
    c = conn.cursor()
    query = "SELECT id, timestamp, user_id, file_type, file_size_kb, stage, status, failure_reason, duration_ms FROM processing_events WHERE 1=1"
    params = []
    if days is not None and not start_date:
        cut_str = (datetime.now() - timedelta(days=int(days))).strftime("%Y-%m-%d %H:%M:%S")
        query += " AND timestamp >= ?"
        params.append(cut_str)
    if start_date:
        query += " AND timestamp >= ?"
        params.append(str(start_date).strip()[:10] + " 00:00:00")
    if end_date:
        query += " AND timestamp <= ?"
        params.append(str(end_date).strip()[:10] + " 23:59:59")
    c.execute(query, params)
    events = [dict(r) for r in c.fetchall()]

    # Map username -> role for role breakdown
    c.execute("SELECT username, role FROM users")
    user_roles = {r["username"]: r["role"] for r in c.fetchall()}
    conn.close()

    if exclude_test_accounts:
        events = [e for e in events if not is_test_account(e.get("user_id", ""))]

    total = len(events)
    succeeded = sum(1 for e in events if e.get("status") == "success")
    failed = sum(1 for e in events if e.get("status") == "failed")
    success_rate = round((succeeded / total) * 100.0, 1) if total > 0 else 100.0

    durations = [float(e.get("duration_ms") or 0.0) for e in events if float(e.get("duration_ms") or 0.0) > 0]
    avg_duration_ms = round(sum(durations) / len(durations), 1) if durations else 0.0

    by_file_type = {"PDF": 0, "DOCX": 0, "TXT": 0}
    by_day = {}
    by_reason = {}
    by_role = {"Student": 0, "Researcher": 0, "Administrator": 0}

    for e in events:
        ft = str(e.get("file_type") or "PDF").upper().lstrip(".")
        if ft not in by_file_type:
            by_file_type[ft] = 0
        by_file_type[ft] += 1

        day_str = str(e.get("timestamp") or "")[:10]
        if day_str:
            if day_str not in by_day:
                by_day[day_str] = {"success": 0, "failed": 0, "total": 0}
            by_day[day_str]["total"] += 1
            if e.get("status") == "failed":
                by_day[day_str]["failed"] += 1
            else:
                by_day[day_str]["success"] += 1

        if e.get("status") == "failed":
            reason = str(e.get("failure_reason") or "Unspecified processing failure").strip()
            by_reason[reason] = by_reason.get(reason, 0) + 1

        uid = e.get("user_id", "")
        urole = user_roles.get(uid, "Student")
        if urole not in by_role:
            by_role[urole] = 0
        by_role[urole] += 1

    return {
        "total": total,
        "succeeded": succeeded,
        "failed": failed,
        "success_rate": success_rate,
        "avg_duration_ms": avg_duration_ms,
        "by_file_type": by_file_type,
        "by_day": dict(sorted(by_day.items())),
        "by_reason": dict(sorted(by_reason.items(), key=lambda x: x[1], reverse=True)),
        "by_role": by_role,
    }


# ---------------------------------------------------------------------------
# TEST / DEMO ACCOUNT CLEANUP & LEGACY ROLE MIGRATION (Parts 4.1 & 4.2)
# ---------------------------------------------------------------------------
TEST_ACCOUNT_PATTERNS = [
    r"^audit_user_",
    r"^qa_user_",
    r"^reg_tester_",
    r"^test_cleanup_user$",
    r"^testuser",
    r"^test_",
    r"^e2e_",
    r"^stu_[a-z]_",
    r"^res_[a-z]_",
    r"^res_ui_",
    r"^Student_Demo$",
    r"^Teacher_Demo$",
    r"^demo_",
    r"^tmp_",
]


def is_test_account(username):
    """Returns True if username matches known test/demo account patterns."""
    if not username:
        return False
    u = str(username).strip()
    for pat in TEST_ACCOUNT_PATTERNS:
        if re.search(pat, u, flags=re.IGNORECASE):
            return True
    return False


def detect_test_accounts(current_admin_user=None):
    """Part 4.1: Detects all registered test/demo accounts (never includes active Administrators)."""
    users = get_all_users(current_admin_user=current_admin_user)
    return [
        u for u in users
        if is_test_account(u.get("username", "")) and u.get("role") != "Administrator"
    ]


def cleanup_test_accounts(usernames, action="disable", confirm_text="", current_admin_user=None, ip="127.0.0.1"):
    """
    Part 4.1: Disables or deletes selected test/demo accounts after explicit confirmation.
    Never runs automatically. Logs TEST_ACCOUNT_CLEANUP in login_history.
    """
    clean_admin = str(current_admin_user or "").strip()
    if not is_admin_user(clean_admin):
        record_audit_event(
            username=clean_admin or "unknown",
            action_type="UNAUTHORIZED_ACCESS",
            target="test_accounts",
            details="Unauthorized attempt to clean up test accounts",
            status="Denied",
            ip=ip,
        )
        return False, "Access Denied: Administrator role required.", 0

    if str(confirm_text or "").strip() != "CONFIRM":
        return False, "Confirmation required: Please type 'CONFIRM' to execute test account cleanup.", 0

    if not usernames:
        return False, "No test accounts selected.", 0

    processed = 0
    for u in usernames:
        clean_u = str(u).strip()
        if not clean_u or clean_u == clean_admin:
            continue
        if action == "delete":
            ok, _ = delete_user_account(clean_u, current_admin_user=clean_admin, confirm_username=clean_u, mode="delete_all", ip=ip)
            if ok:
                processed += 1
        else:
            ok, _ = toggle_user_status(clean_u, "Disabled", current_admin_user=clean_admin, ip=ip)
            if ok:
                processed += 1

    record_audit_event(
        username=clean_admin,
        action_type="TEST_ACCOUNT_CLEANUP",
        target=f"{processed}_accounts",
        details=f"Test account cleanup ({action}) executed on {processed} account(s): {', '.join(str(x) for x in usernames[:8])}",
        status="Success",
        ip=ip,
    )
    verb = "deleted" if action == "delete" else "disabled"
    return True, f"Successfully {verb} {processed} test/demo account(s).", processed


def get_legacy_accounts(current_admin_user=None):
    """Part 4.2: Lists accounts whose role is not Student, Researcher, or Administrator."""
    users = get_all_users(current_admin_user=current_admin_user)
    return [
        u for u in users
        if u.get("role") not in ("Student", "Researcher", "Administrator")
    ]


def migrate_legacy_roles(role_mapping=None, current_admin_user=None, confirm=False, ip="127.0.0.1"):
    """
    Part 4.2: Migrates accounts with legacy roles (e.g. Evaluator, Faculty) to Student or Researcher.
    Requires explicit admin confirmation and logs each change (old role -> new role) in login_history.
    """
    clean_admin = str(current_admin_user or "").strip()
    if not is_admin_user(clean_admin):
        record_audit_event(
            username=clean_admin or "unknown",
            action_type="UNAUTHORIZED_ACCESS",
            target="legacy_roles",
            details="Unauthorized attempt to migrate legacy roles",
            status="Denied",
            ip=ip,
        )
        return False, "Access Denied: Administrator role required.", 0

    if not confirm:
        return False, "Confirmation required: Please confirm the legacy role migration before executing.", 0

    legacy_users = get_legacy_accounts()
    if not legacy_users:
        return True, "No legacy accounts remain to migrate.", 0

    mapping = role_mapping or {}
    migrated = 0
    conn = get_db_connection()
    c = conn.cursor()
    for u in legacy_users:
        uname = u["username"]
        old_role = u["role"]
        target_role = mapping.get(uname)
        if target_role not in ("Student", "Researcher"):
            # Sensible default based on legacy role name
            target_role = "Researcher" if str(old_role).lower() in ("evaluator", "faculty", "reviewer", "professor") else "Student"
        c.execute("UPDATE users SET role = ? WHERE username = ?", (target_role, uname))
        migrated += 1
        record_audit_event(
            username=clean_admin,
            action_type="LEGACY_ROLE_MIGRATION",
            target=uname,
            details=f"Legacy role for '{uname}' migrated from '{old_role}' to '{target_role}'",
            status="Success",
            ip=ip,
        )
    conn.commit()
    conn.close()
    return True, f"Migrated {migrated} legacy account(s) to canonical roles.", migrated


# ---------------------------------------------------------------------------
# ANALYSIS HISTORY MODULE (Part 2.7 & Part 3 Privacy Enforced)
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
    clean_domain = normalize_discipline(_unescape_val(domain))
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


def get_user_history(username, requester_username=None):
    """
    Retrieves analysis history for `username`.
    Part 2.7 & Part 3: If requester_username is supplied and does not match `username`,
    access is denied and logged (even if requester_username is an Administrator).
    """
    clean_owner = str(username or "").strip()
    if requester_username is not None and str(requester_username).strip() != clean_owner:
        record_audit_event(
            username=str(requester_username).strip() or "unknown",
            action_type="UNAUTHORIZED_ACCESS",
            target=f"analysis_history:{clean_owner}",
            details=f"Blocked attempt by '{requester_username}' to list private analysis history of '{clean_owner}'",
            status="Denied",
        )
        return []
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
        (clean_owner,)
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
            "domain": normalize_discipline(_unescape_val(row_dict.get("domain", "General Academic"))),
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


def get_all_analyses_summary(exclude_test_accounts=False, start_date=None, end_date=None, current_admin_user=None):
    """
    Part 1.4 & Part 3 Privacy: Returns ONLY aggregate-safe metadata (id, username, role, domain, score, grade, created_at).
    NEVER returns private filenames, display titles, extracted text, results_json, or PDF report bytes.
    """
    if current_admin_user is not None and not is_admin_user(current_admin_user):
        return []
    try:
        create_users_table()
        conn = get_db_connection()
        c = conn.cursor()
        query = """
            SELECT ah.id, ah.username, COALESCE(u.role, 'Student') as role,
                   ah.domain, ah.score, ah.grade, ah.created_at
            FROM analysis_history ah
            LEFT JOIN users u ON ah.username = u.username
            WHERE 1=1
        """
        params = []
        if start_date:
            query += " AND ah.created_at >= ?"
            params.append(str(start_date).strip()[:10] + " 00:00:00")
        if end_date:
            query += " AND ah.created_at <= ?"
            params.append(str(end_date).strip()[:10] + " 23:59:59")
        query += " ORDER BY ah.id DESC"
        c.execute(query, params)
        rows = []
        for r in c.fetchall():
            d = dict(r)
            d["domain"] = normalize_discipline(d.get("domain"))
            rows.append(d)
        conn.close()
        if exclude_test_accounts:
            rows = [r for r in rows if not is_test_account(r.get("username", ""))]
        return rows
    except Exception:
        return []


# ---------------------------------------------------------------------------
# UPLOAD HISTORY MODULE (Part 3 Privacy — Masked Filenames for Admins)
# ---------------------------------------------------------------------------
def mask_filename(filename):
    """
    Part 3: Masks a private user filename as 'abc….ext' (first 3 chars + ellipsis + extension)
    so Administrators see upload telemetry without private paper titles/filenames.
    """
    if not filename:
        return "doc….pdf"
    clean = os.path.basename(str(filename).strip())
    stem, ext = os.path.splitext(clean)
    ext = ext if ext else ".pdf"
    prefix = stem[:3] if len(stem) >= 3 else (stem or "doc")
    return f"{prefix}…{ext}"


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


def get_upload_history(
    username=None,
    limit=250,
    viewer_username=None,
    mask_filenames=None,
    start_date=None,
    end_date=None,
    exclude_test_accounts=False,
):
    """
    Part 3: Retrieves upload history.
    - When called for the Admin view (username=None or mask_filenames=True), filenames are masked as 'abc….pdf'.
    - Full filenames are ONLY returned when a user queries their own personal upload history
      (username is specified and viewer_username == username or mask_filenames is explicitly False).
    """
    create_users_table()
    conn = get_db_connection()
    c = conn.cursor()
    query = "SELECT * FROM upload_history WHERE 1=1"
    params = []
    if username:
        query += " AND username = ?"
        params.append(str(username).strip())
    if start_date:
        query += " AND upload_time >= ?"
        params.append(str(start_date).strip()[:10] + " 00:00:00")
    if end_date:
        query += " AND upload_time <= ?"
        params.append(str(end_date).strip()[:10] + " 23:59:59")
    query += " ORDER BY id DESC LIMIT ?"
    params.append(int(limit))
    c.execute(query, params)
    raw_rows = [dict(r) for r in c.fetchall()]
    conn.close()

    if exclude_test_accounts:
        raw_rows = [r for r in raw_rows if not is_test_account(r.get("username", ""))]

    # Determine whether to mask filenames: default True when username is None (Admin global view)
    if mask_filenames is None:
        should_mask = (username is None) or (viewer_username is not None and str(viewer_username).strip() != str(username).strip())
    else:
        should_mask = bool(mask_filenames)

    rows = []
    for r in raw_rows:
        orig_fn = r.get("filename", "")
        masked_fn = mask_filename(orig_fn)
        r["masked_filename"] = masked_fn
        if should_mask and (viewer_username is None or str(viewer_username).strip() != str(r.get("username", "")).strip()):
            r["filename"] = masked_fn
        rows.append(r)
    return rows


# ---------------------------------------------------------------------------
# SAVED PAPERS (INSTITUTIONAL SHARED REPOSITORY) MODULE (Part 4.3 & 4.4)
# ---------------------------------------------------------------------------
def compute_repository_content_hash(title="", file_bytes=None):
    """Computes SHA-256 content hash for repository paper deduplication."""
    if file_bytes and len(file_bytes) > 0:
        data = file_bytes if isinstance(file_bytes, (bytes, bytearray)) else str(file_bytes).encode("utf-8")
        return hashlib.sha256(data).hexdigest()
    norm_title = re.sub(r"\s+", " ", str(title or "").strip().lower())
    return hashlib.sha256(norm_title.encode("utf-8")).hexdigest()


def check_repository_duplicate(title="", file_bytes=None):
    """
    Part 4.3: Checks if a paper with the same SHA-256 content hash or normalized title
    already exists in saved_papers. Returns list of matching duplicate dicts.
    """
    create_users_table()
    norm_title = re.sub(r"\s+", " ", str(title or "").strip().lower())
    chash = compute_repository_content_hash(title=title, file_bytes=file_bytes)
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT id, paper_id, title, authors, domain, uploaded_by, uploaded_at, filename, score, grade, content_hash FROM saved_papers ORDER BY id DESC")
    matches = []
    for r in c.fetchall():
        d = dict(r)
        r_title = re.sub(r"\s+", " ", str(d.get("title") or "").strip().lower())
        r_hash = str(d.get("content_hash") or "")
        if (chash and r_hash and chash == r_hash) or (norm_title and r_title == norm_title):
            matches.append(d)
    conn.close()
    return matches


def save_repository_paper(
    title,
    authors,
    domain,
    uploaded_by,
    filename,
    file_bytes,
    pdf_report_bytes,
    score,
    grade,
    results_json=None,
    is_public=1,
    allow_duplicate=True,
):
    create_users_table()
    clean_title = title.strip() if title else filename.strip()
    clean_domain = normalize_discipline(domain.strip() if domain else "General Academic")
    chash = compute_repository_content_hash(title=clean_title, file_bytes=file_bytes)

    if not allow_duplicate:
        dups = check_repository_duplicate(title=clean_title, file_bytes=file_bytes)
        if dups:
            return None

    conn = get_db_connection()
    c = conn.cursor()
    paper_id = f"LIB-{uuid.uuid4().hex[:8].upper()}"
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    c.execute(
        """
        INSERT INTO saved_papers (
            paper_id, title, authors, domain, uploaded_by, uploaded_at,
            filename, file_bytes, pdf_report_bytes, score, grade, results_json, is_public, content_hash
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            paper_id,
            clean_title,
            authors.strip() if authors else "Institutional Authors",
            clean_domain,
            uploaded_by.strip(),
            now_str,
            filename.strip(),
            file_bytes,
            pdf_report_bytes,
            float(score),
            grade,
            results_json,
            int(is_public),
            chash,
        )
    )
    conn.commit()
    conn.close()
    record_audit_event(
        username=uploaded_by,
        action_type="REPOSITORY_UPLOAD",
        target=paper_id,
        details=f"Manuscript '{clean_title}' added to institutional repository (domain={clean_domain})",
        status="Success"
    )
    return paper_id


def get_saved_papers():
    create_users_table()
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM saved_papers ORDER BY id DESC")
    rows = []
    for r in c.fetchall():
        d = dict(r)
        d["domain"] = normalize_discipline(d.get("domain"))
        rows.append(d)
    conn.close()
    return rows


def get_saved_paper(paper_id):
    create_users_table()
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM saved_papers WHERE paper_id = ? OR id = ?", (paper_id, str(paper_id)))
    row = c.fetchone()
    conn.close()
    if not row:
        return None
    d = dict(row)
    d["domain"] = normalize_discipline(d.get("domain"))
    return d


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


def find_repository_duplicates():
    """
    Part 4.3: Finds duplicate papers in saved_papers grouped by normalized title or content_hash.
    Returns a list of duplicate groups, each containing 'keep' (newest entry) and 'duplicates' (older entries).
    """
    create_users_table()
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT id, paper_id, title, authors, domain, uploaded_by, uploaded_at, filename, score, grade, content_hash FROM saved_papers ORDER BY id DESC")
    rows = [dict(r) for r in c.fetchall()]
    conn.close()

    groups = {}
    for r in rows:
        norm_title = re.sub(r"\s+", " ", str(r.get("title") or "").strip().lower())
        key = norm_title or str(r.get("content_hash") or r["id"])
        groups.setdefault(key, []).append(r)

    dup_groups = []
    for key, items in groups.items():
        if len(items) > 1:
            # items are already sorted newest first (ORDER BY id DESC)
            dup_groups.append({
                "title": items[0].get("title"),
                "count": len(items),
                "keep": items[0],
                "duplicates": items[1:],
            })
    return dup_groups


def remove_duplicate_repository_papers(current_admin_user=None, confirm=False, ip="127.0.0.1"):
    """
    Part 4.3: Removes older duplicate entries in saved_papers (keeping the newest per group)
    after explicit administrator confirmation, and logs REPOSITORY_DEDUPLICATE.
    """
    clean_admin = str(current_admin_user or "").strip()
    if not is_admin_user(clean_admin):
        record_audit_event(
            username=clean_admin or "unknown",
            action_type="UNAUTHORIZED_ACCESS",
            target="saved_papers",
            details="Unauthorized attempt to deduplicate institutional repository",
            status="Denied",
            ip=ip,
        )
        return False, "Access Denied: Administrator role required.", 0

    if not confirm:
        return False, "Confirmation required: Please confirm duplicate removal before executing.", 0

    dup_groups = find_repository_duplicates()
    if not dup_groups:
        return True, "No duplicate repository papers found.", 0

    ids_to_remove = []
    titles_summary = []
    for g in dup_groups:
        dups = g["duplicates"]
        ids_to_remove.extend(d["id"] for d in dups)
        titles_summary.append(f"'{g['title']}' (removed {len(dups)}, kept ID {g['keep']['paper_id']})")

    conn = get_db_connection()
    c = conn.cursor()
    placeholders = ",".join("?" for _ in ids_to_remove)
    c.execute(f"DELETE FROM saved_papers WHERE id IN ({placeholders})", ids_to_remove)
    conn.commit()
    conn.close()

    record_audit_event(
        username=clean_admin,
        action_type="REPOSITORY_DEDUPLICATE",
        target=f"{len(ids_to_remove)}_duplicates",
        details=f"Removed {len(ids_to_remove)} duplicate repository paper(s): " + "; ".join(titles_summary[:5]),
        status="Success",
        ip=ip,
    )
    return True, f"Removed {len(ids_to_remove)} duplicate paper(s) from the institutional repository (newest copy of each kept).", len(ids_to_remove)


# ---------------------------------------------------------------------------
# DEPENDENCY STATUS, SYSTEM HEALTH, STORAGE & BACKUP MODULE (Parts 1.2, 1.3, 1.5)
# ---------------------------------------------------------------------------
REQUIRED_DEPENDENCIES = [
    ("streamlit", "streamlit", True, "Core Web Application Framework"),
    ("plotly", "plotly", True, "Interactive Analytics & Visualization Engine"),
    ("pandas", "pandas", True, "Tabular Data & Telemetry Processing"),
    ("pdfplumber", "pdfplumber", True, "Primary PDF Layout & Span Extraction"),
    ("python-docx", "docx", True, "Microsoft Word (.docx) Manuscript Parser"),
    ("reportlab", "reportlab", True, "Primary PDF Report Generator"),
    ("fpdf2", "fpdf", False, "Fallback PDF Report Generator (fpdf / fpdf2)"),
    ("kaleido", "kaleido", False, "Static Chart Image Export Engine"),
    ("textblob", "textblob", True, "Sentiment & Lexical Complexity Heuristics"),
    ("nltk", "nltk", True, "Natural Language Tokenization & Lexicon"),
    ("scikit-learn", "sklearn", True, "TF-IDF & Cosine Similarity Engine"),
    ("numpy", "numpy", True, "Numerical Array & Matrix Computation"),
    ("matplotlib", "matplotlib", False, "Auxiliary Plotting Support"),
    ("wordcloud", "wordcloud", False, "Lexical Cloud Visualization"),
    ("seaborn", "seaborn", False, "Statistical Plotting Palette Support"),
    ("wheel", "wheel", False, "Python Package Build Archive Support"),
]


def check_dependencies():
    """
    Part 1.2(c): Checks each dependency in requirements.txt and core stack,
    returning installed version, status (OK / Missing), and whether required or optional.
    """
    results = []
    for pkg_name, import_name, is_req, purpose in REQUIRED_DEPENDENCIES:
        ver = None
        try:
            ver = importlib.metadata.version(pkg_name)
        except Exception:
            try:
                mod = __import__(import_name)
                ver = getattr(mod, "__version__", "Installed")
            except Exception:
                ver = None
        results.append({
            "package": pkg_name,
            "import_name": import_name,
            "version": ver if ver else "Not Installed",
            "status": "OK" if ver else "Missing",
            "required": is_req,
            "type_label": "Required" if is_req else "Optional",
            "purpose": purpose,
        })
    return results


def list_db_backups():
    """Part 1.5: Lists all SQLite backup files in backups/ with timestamp, size, and integrity check."""
    os.makedirs(BACKUPS_DIR, exist_ok=True)
    backups = []
    for fname in sorted(os.listdir(BACKUPS_DIR), reverse=True):
        if not fname.endswith(".db"):
            continue
        fpath = os.path.join(BACKUPS_DIR, fname)
        if not os.path.isfile(fpath):
            continue
        size_b = os.path.getsize(fpath)
        mtime = datetime.fromtimestamp(os.path.getmtime(fpath)).strftime("%Y-%m-%d %H:%M:%S")
        if size_b > 1024 * 1024:
            size_str = f"{size_b / (1024 * 1024):.2f} MB"
        elif size_b > 1024:
            size_str = f"{size_b / 1024:.1f} KB"
        else:
            size_str = f"{size_b} B"

        integrity = "ok"
        bconn = None
        try:
            bconn = sqlite3.connect(fpath, timeout=5)
            bc = bconn.cursor()
            bc.execute("PRAGMA quick_check")
            res = bc.fetchone()
            integrity = res[0] if res else "unknown"
        except Exception:
            integrity = "error"
        finally:
            if bconn is not None:
                try:
                    bconn.close()
                except Exception:
                    pass

        backups.append({
            "filename": fname,
            "created_at": mtime,
            "size_bytes": size_b,
            "size_formatted": size_str,
            "integrity": integrity,
        })
    backups.sort(key=lambda x: (x["created_at"], x["filename"]), reverse=True)
    return backups


def get_last_backup_info():
    """Returns metadata about the most recent database backup and whether a backup is overdue (>7 days)."""
    backups = list_db_backups()
    if not backups:
        return {
            "last_backup_time": "Never",
            "last_backup_filename": "",
            "backup_count": 0,
            "overdue_7d": True,
        }
    latest = backups[0]
    overdue = False
    try:
        dt = datetime.strptime(latest["created_at"], "%Y-%m-%d %H:%M:%S")
        overdue = (datetime.now() - dt).total_seconds() > 7 * 86400
    except Exception:
        overdue = True
    return {
        "last_backup_time": latest["created_at"],
        "last_backup_filename": latest["filename"],
        "backup_count": len(backups),
        "overdue_7d": overdue,
    }


def create_db_backup(current_admin_user=None, label="", ip="127.0.0.1", created_by=None):
    """
    Part 1.5: Creates a timestamped copy of users.db in backups/ using sqlite3.Connection.backup,
    verifies PRAGMA integrity_check on the backup, applies keep-last-N retention, and logs DB_BACKUP_CREATE.
    """
    if current_admin_user is None and created_by is not None:
        current_admin_user = created_by
    clean_admin = str(current_admin_user or "").strip()
    if not is_admin_user(clean_admin):
        record_audit_event(
            username=clean_admin or "unknown",
            action_type="UNAUTHORIZED_ACCESS",
            target="backups",
            details="Unauthorized attempt to create database backup",
            status="Denied",
            ip=ip,
        )
        return False, "Access Denied: Administrator role required.", None

    try:
        create_users_table()
        os.makedirs(BACKUPS_DIR, exist_ok=True)
        now = datetime.now()
        safe_label = re.sub(r"[^A-Za-z0-9_\-]", "", str(label or "").strip())[:24]
        suffix = f"_{safe_label}" if safe_label else ""
        fname = f"paperiq_backup_{now.strftime('%Y%m%d_%H%M%S_%f')[:19]}{suffix}.db"
        dest_path = os.path.join(BACKUPS_DIR, fname)

        src_conn = get_db_connection()
        dest_conn = sqlite3.connect(dest_path)
        with dest_conn:
            src_conn.backup(dest_conn)
        dest_conn.close()
        src_conn.close()

        # Verify integrity of backup file
        vconn = sqlite3.connect(dest_path)
        vc = vconn.cursor()
        vc.execute("PRAGMA integrity_check")
        integ = vc.fetchone()[0]
        vconn.close()

        size_b = os.path.getsize(dest_path)
        record_audit_event(
            username=clean_admin,
            action_type="DB_BACKUP_CREATE",
            target=fname,
            details=f"Database backup '{fname}' created ({size_b} bytes, integrity={integ})",
            status="Success",
            ip=ip,
        )

        # Apply configured keep-last-N retention
        keep_n = int(get_platform_setting("backup_retention_count", 10))
        apply_backup_retention(keep_last_n=keep_n, current_admin_user=clean_admin, ip=ip, silent_if_none=True)

        return True, f"Backup '{fname}' created and verified (integrity: {integ}).", fname
    except Exception as e:
        return False, f"Backup failed: {sanitize_error_message(e)}", None


def get_backup_bytes(filename, current_admin_user=None):
    """Returns raw bytes of a backup file in backups/ for admin download."""
    if not is_admin_user(current_admin_user):
        return None
    clean_fn = os.path.basename(str(filename or "").strip())
    if not clean_fn.endswith(".db"):
        return None
    fpath = os.path.join(BACKUPS_DIR, clean_fn)
    if not os.path.isfile(fpath):
        return None
    with open(fpath, "rb") as f:
        return f.read()


def delete_db_backup(filename, confirm_filename=None, current_admin_user=None, ip="127.0.0.1"):
    """Part 1.5: Deletes a backup file from backups/ after typed confirmation and logs DB_BACKUP_DELETE."""
    clean_admin = str(current_admin_user or "").strip()
    if not is_admin_user(clean_admin):
        record_audit_event(
            username=clean_admin or "unknown",
            action_type="UNAUTHORIZED_ACCESS",
            target=str(filename),
            details="Unauthorized attempt to delete database backup",
            status="Denied",
            ip=ip,
        )
        return False, "Access Denied: Administrator role required."

    clean_fn = os.path.basename(str(filename or "").strip())
    if confirm_filename is not None and str(confirm_filename).strip() != clean_fn:
        return False, f"Confirmation failed: Please type the exact filename '{clean_fn}' to delete this backup."

    fpath = os.path.join(BACKUPS_DIR, clean_fn)
    if not os.path.isfile(fpath):
        return False, f"Backup file '{clean_fn}' not found."

    try:
        os.remove(fpath)
        record_audit_event(
            username=clean_admin,
            action_type="DB_BACKUP_DELETE",
            target=clean_fn,
            details=f"Database backup '{clean_fn}' deleted by administrator",
            status="Success",
            ip=ip,
        )
        return True, f"Backup '{clean_fn}' deleted."
    except Exception as e:
        return False, str(e)


def apply_backup_retention(keep_last_n=10, current_admin_user=None, ip="127.0.0.1", silent_if_none=False):
    """Part 1.5: Keeps the newest N backups in backups/ and removes older ones with audit logging."""
    clean_admin = str(current_admin_user or "").strip()
    if not is_admin_user(clean_admin):
        return False, "Access Denied: Administrator role required.", 0
    keep_n = max(1, int(keep_last_n))
    backups = list_db_backups()
    if len(backups) <= keep_n:
        return True, f"Backup count ({len(backups)}) is within retention limit (keep last {keep_n}).", 0

    to_delete = backups[keep_n:]
    removed = 0
    for b in to_delete:
        fpath = os.path.join(BACKUPS_DIR, b["filename"])
        try:
            if os.path.isfile(fpath):
                os.remove(fpath)
                removed += 1
        except Exception:
            pass
    if removed > 0 or not silent_if_none:
        record_audit_event(
            username=clean_admin,
            action_type="DB_BACKUP_RETENTION",
            target=f"keep_last_{keep_n}",
            details=f"Backup retention policy applied (kept newest {keep_n}, removed {removed} older backup(s))",
            status="Success",
            ip=ip,
        )
    return True, f"Retention policy applied: kept newest {keep_n} backup(s), removed {removed} older backup(s).", removed


def compute_system_status_badge():
    """
    Part 1.3: Computes real System Status badge ('Healthy' / 'Degraded' / 'Error')
    from DB check + recent error count + processing failure rate + dependency status,
    with a concise 1-line reason.
    """
    create_users_table()
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("PRAGMA integrity_check")
    integ = c.fetchone()[0]
    conn.close()

    deps = check_dependencies()
    missing_req = [d["package"] for d in deps if d["required"] and d["status"] != "OK"]
    err_counts = get_app_error_counts()
    proc_7d = get_processing_stats(days=7)

    if integ != "ok":
        return "Error", f"SQLite integrity check reported '{integ}'."
    if missing_req:
        return "Error", f"Missing required runtime dependencies: {', '.join(missing_req)}."
    if err_counts["errors_1h"] >= 5:
        return "Error", f"{err_counts['errors_1h']} application errors recorded in the last hour."

    reasons = []
    if err_counts["errors_24h"] > 0:
        reasons.append(f"{err_counts['errors_24h']} app error(s) in last 24h")
    if proc_7d["total"] >= 3 and proc_7d["success_rate"] < 75.0:
        reasons.append(f"7d processing success rate is {proc_7d['success_rate']}%")

    if reasons:
        return "Degraded", "Degraded: " + "; ".join(reasons) + "."

    return "Healthy", f"All core subsystems nominal (DB integrity ok, 0 errors in 24h, {proc_7d['success_rate']}% 7d processing success)."


def get_system_stats(exclude_test_accounts=False):
    """Returns 100% real database and operational metrics for the Admin Dashboard."""
    create_users_table()
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT username, role, status FROM users")
    all_u = [dict(r) for r in c.fetchall()]
    test_u_count = sum(1 for u in all_u if is_test_account(u["username"]) and u["role"] != "Administrator")

    if exclude_test_accounts:
        filtered_u = [u for u in all_u if not is_test_account(u["username"]) or u["role"] == "Administrator"]
    else:
        filtered_u = all_u

    total_users = len(filtered_u)
    student_count = sum(1 for u in filtered_u if u["role"] == "Student")
    researcher_count = sum(1 for u in filtered_u if u["role"] == "Researcher")
    admin_count = sum(1 for u in filtered_u if u["role"] == "Administrator")
    legacy_count = total_users - (student_count + researcher_count + admin_count)
    active_users = sum(1 for u in filtered_u if u["status"] != "Disabled")
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

    err_counts = get_app_error_counts()
    proc_7d = get_processing_stats(days=7, exclude_test_accounts=exclude_test_accounts)
    binfo = get_last_backup_info()
    sys_status, sys_reason = compute_system_status_badge()

    return {
        "total_users": total_users,
        "student_count": student_count,
        "researcher_count": researcher_count,
        "admin_count": admin_count,
        "legacy_count": legacy_count,
        "test_account_count": test_u_count,
        "active_users": active_users,
        "disabled_users": disabled_users,
        "saved_papers_count": saved_papers_count,
        "analysis_count": analysis_count,
        "audit_count": audit_count,
        "upload_count": upload_count,
        "db_size_bytes": db_size,
        "db_size_formatted": db_size_str,
        "errors_24h": err_counts["errors_24h"],
        "errors_7d": err_counts["errors_7d"],
        "processing_success_rate_7d": proc_7d["success_rate"],
        "processing_total_7d": proc_7d["total"],
        "processing_failed_7d": proc_7d["failed"],
        "last_backup_time": binfo["last_backup_time"],
        "last_backup_filename": binfo["last_backup_filename"],
        "backup_count": binfo["backup_count"],
        "backup_overdue_7d": binfo["overdue_7d"],
        "system_status": sys_status,
        "system_status_reason": sys_reason,
    }


def get_system_health():
    """Runs real-time diagnostic checks on SQLite database, error tables, processing events, and dependencies."""
    create_users_table()
    t0 = time.perf_counter()
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT 1")
    c.fetchone()
    latency_ms = (time.perf_counter() - t0) * 1000.0

    c.execute("PRAGMA integrity_check")
    integrity_res = c.fetchone()[0]

    tables = [
        "users",
        "analysis_history",
        "login_history",
        "saved_papers",
        "upload_history",
        "app_errors",
        "processing_events",
        "app_settings",
    ]
    table_counts = {}
    for t in tables:
        try:
            c.execute(f"SELECT COUNT(*) FROM {t}")
            table_counts[t] = c.fetchone()[0]
        except Exception:
            table_counts[t] = 0

    c.execute("PRAGMA page_count")
    page_count = c.fetchone()[0]
    c.execute("PRAGMA page_size")
    page_size = c.fetchone()[0]
    conn.close()

    db_size = os.path.getsize(DB_PATH) if os.path.exists(DB_PATH) else 0
    sys_status, sys_reason = compute_system_status_badge()
    err_counts = get_app_error_counts()
    proc_7d = get_processing_stats(days=7)

    return {
        "status": sys_status,
        "status_reason": sys_reason,
        "integrity": integrity_res,
        "latency_ms": round(latency_ms, 2),
        "db_size_bytes": db_size,
        "page_count": page_count,
        "page_size": page_size,
        "table_counts": table_counts,
        "error_counts": err_counts,
        "processing_7d": proc_7d,
        "password_scheme": f"PBKDF2-HMAC-SHA256 ({PBKDF2_ITERATIONS:,} iterations, per-user 16B CSPRNG salt)",
    }


def get_storage_detailed_stats():
    """
    Part 1.5: Returns detailed storage breakdown:
    - DB size, WAL/SHM size, integrity
    - Report storage size & count (PDF blobs in analysis_history and saved_papers)
    - Per-table row counts and approximate byte sizes
    - Orphaned-record counts across child tables
    """
    create_users_table()
    run_researcher_migrations()
    conn = get_db_connection()
    c = conn.cursor()

    c.execute("PRAGMA integrity_check")
    integrity = c.fetchone()[0]

    # Report storage size & count
    c.execute("SELECT COUNT(*), COALESCE(SUM(LENGTH(pdf_data)), 0) FROM analysis_history WHERE pdf_data IS NOT NULL AND LENGTH(pdf_data) > 0")
    ah_rep_cnt, ah_rep_bytes = c.fetchone()
    c.execute("SELECT COUNT(*), COALESCE(SUM(LENGTH(pdf_report_bytes)), 0), COALESCE(SUM(LENGTH(file_bytes)), 0) FROM saved_papers")
    sp_cnt, sp_rep_bytes, sp_file_bytes = c.fetchone()

    total_report_count = int(ah_rep_cnt or 0) + int(sp_cnt or 0)
    total_report_bytes = int(ah_rep_bytes or 0) + int(sp_rep_bytes or 0)

    # Per-table row counts and approximate byte sizes
    all_tables = [
        ("users", "SELECT COUNT(*), COALESCE(SUM(LENGTH(username)+LENGTH(password)+LENGTH(role)), 0) FROM users"),
        ("analysis_history", "SELECT COUNT(*), COALESCE(SUM(LENGTH(COALESCE(pdf_data, x'')) + LENGTH(COALESCE(results_json, '')) + LENGTH(COALESCE(filename, ''))), 0) FROM analysis_history"),
        ("saved_papers", "SELECT COUNT(*), COALESCE(SUM(LENGTH(COALESCE(file_bytes, x'')) + LENGTH(COALESCE(pdf_report_bytes, x'')) + LENGTH(COALESCE(results_json, ''))), 0) FROM saved_papers"),
        ("login_history", "SELECT COUNT(*), COALESCE(SUM(LENGTH(COALESCE(username, '')) + LENGTH(COALESCE(details, '')) + LENGTH(COALESCE(row_hash, ''))), 0) FROM login_history"),
        ("upload_history", "SELECT COUNT(*), COALESCE(SUM(LENGTH(COALESCE(username, '')) + LENGTH(COALESCE(filename, ''))), 0) FROM upload_history"),
        ("app_errors", "SELECT COUNT(*), COALESCE(SUM(LENGTH(COALESCE(message_short, '')) + LENGTH(COALESCE(error_type, ''))), 0) FROM app_errors"),
        ("processing_events", "SELECT COUNT(*), COALESCE(SUM(LENGTH(COALESCE(user_id, '')) + LENGTH(COALESCE(failure_reason, ''))), 0) FROM processing_events"),
        ("app_settings", "SELECT COUNT(*), COALESCE(SUM(LENGTH(COALESCE(key, '')) + LENGTH(COALESCE(value, ''))), 0) FROM app_settings"),
        ("projects", "SELECT COUNT(*), COALESCE(SUM(LENGTH(COALESCE(name, '')) + LENGTH(COALESCE(description, ''))), 0) FROM projects"),
        ("paper_metadata", "SELECT COUNT(*), COALESCE(SUM(LENGTH(COALESCE(title, '')) + LENGTH(COALESCE(research_profile_json, ''))), 0) FROM paper_metadata"),
        ("research_notes", "SELECT COUNT(*), COALESCE(SUM(LENGTH(COALESCE(note_text, ''))), 0) FROM research_notes"),
        ("saved_comparisons", "SELECT COUNT(*), COALESCE(SUM(LENGTH(COALESCE(matrix_json, '')) + LENGTH(COALESCE(synthesis_json, ''))), 0) FROM saved_comparisons"),
        ("paper_chats", "SELECT COUNT(*), COALESCE(SUM(LENGTH(COALESCE(question, '')) + LENGTH(COALESCE(answer, ''))), 0) FROM paper_chats"),
    ]
    table_breakdown = []
    for tname, q in all_tables:
        try:
            c.execute(q)
            rcnt, rbytes = c.fetchone()
            bval = int(rbytes or 0) + int(rcnt or 0) * 64  # include row header overhead estimate
            table_breakdown.append({
                "table": tname,
                "rows": int(rcnt or 0),
                "approx_bytes": bval,
                "approx_size": f"{bval / (1024*1024):.2f} MB" if bval >= 1024 * 1024 else f"{bval / 1024:.1f} KB",
            })
        except Exception:
            pass

    # Orphaned record checks (records pointing to deleted users or deleted projects/analyses)
    orphans = {}
    c.execute("SELECT COUNT(*) FROM analysis_history WHERE username NOT IN (SELECT username FROM users) AND username NOT LIKE 'anon_%'")
    orphans["analysis_history_without_user"] = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM upload_history WHERE username NOT IN (SELECT username FROM users) AND username NOT LIKE 'anon_%'")
    orphans["upload_history_without_user"] = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM project_papers WHERE project_id NOT IN (SELECT id FROM projects)")
    orphans["project_papers_without_project"] = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM paper_metadata WHERE user_id NOT IN (SELECT username FROM users) AND user_id NOT LIKE 'anon_%'")
    orphans["paper_metadata_without_user"] = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM research_notes WHERE user_id NOT IN (SELECT username FROM users) AND user_id NOT LIKE 'anon_%'")
    orphans["research_notes_without_user"] = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM paper_chats WHERE user_id NOT IN (SELECT username FROM users) AND user_id NOT LIKE 'anon_%'")
    orphans["paper_chats_without_user"] = c.fetchone()[0]
    conn.close()

    total_orphans = sum(orphans.values())
    db_size = os.path.getsize(DB_PATH) if os.path.exists(DB_PATH) else 0
    wal_size = os.path.getsize(DB_PATH + "-wal") if os.path.exists(DB_PATH + "-wal") else 0

    return {
        "db_size_bytes": db_size,
        "wal_size_bytes": wal_size,
        "integrity": integrity,
        "report_count": total_report_count,
        "report_bytes": total_report_bytes,
        "report_size_formatted": f"{total_report_bytes / (1024*1024):.2f} MB" if total_report_bytes >= 1024 * 1024 else f"{total_report_bytes / 1024:.1f} KB",
        "repository_file_bytes": int(sp_file_bytes or 0),
        "table_breakdown": table_breakdown,
        "orphans": orphans,
        "total_orphans": total_orphans,
    }


def clean_orphaned_records(current_admin_user=None, confirm=False, ip="127.0.0.1"):
    """Part 1.5: Cleans orphaned rows across child tables after admin confirmation and logs ORPHAN_CLEANUP."""
    clean_admin = str(current_admin_user or "").strip()
    if not is_admin_user(clean_admin):
        record_audit_event(
            username=clean_admin or "unknown",
            action_type="UNAUTHORIZED_ACCESS",
            target="orphan_cleanup",
            details="Unauthorized attempt to clean orphaned database records",
            status="Denied",
            ip=ip,
        )
        return False, "Access Denied: Administrator role required.", 0

    if not confirm:
        return False, "Confirmation required before removing orphaned records.", 0

    create_users_table()
    run_researcher_migrations()
    conn = get_db_connection()
    c = conn.cursor()
    removed = 0
    queries = [
        "DELETE FROM analysis_history WHERE username NOT IN (SELECT username FROM users) AND username NOT LIKE 'anon_%'",
        "DELETE FROM upload_history WHERE username NOT IN (SELECT username FROM users) AND username NOT LIKE 'anon_%'",
        "DELETE FROM project_papers WHERE project_id NOT IN (SELECT id FROM projects)",
        "DELETE FROM paper_metadata WHERE user_id NOT IN (SELECT username FROM users) AND user_id NOT LIKE 'anon_%'",
        "DELETE FROM research_notes WHERE user_id NOT IN (SELECT username FROM users) AND user_id NOT LIKE 'anon_%'",
        "DELETE FROM paper_chats WHERE user_id NOT IN (SELECT username FROM users) AND user_id NOT LIKE 'anon_%'",
    ]
    for q in queries:
        c.execute(q)
        removed += max(0, c.rowcount)
    conn.commit()
    conn.close()

    record_audit_event(
        username=clean_admin,
        action_type="ORPHAN_CLEANUP",
        target="users.db",
        details=f"Orphaned-record cleanup executed: removed {removed} orphaned row(s)",
        status="Success",
        ip=ip,
    )
    return True, f"Orphaned-record cleanup complete: {removed} orphaned row(s) removed.", removed


def preview_old_reports(older_than_days=90):
    """Part 1.5: Previews count and size of generated PDF report blobs older than N days."""
    create_users_table()
    days_val = max(1, int(older_than_days))
    cutoff_str = (datetime.now() - timedelta(days=days_val)).strftime("%Y-%m-%d %H:%M:%S")
    conn = get_db_connection()
    c = conn.cursor()
    c.execute(
        """
        SELECT COUNT(*), COALESCE(SUM(LENGTH(pdf_data)), 0)
        FROM analysis_history
        WHERE created_at < ? AND pdf_data IS NOT NULL AND LENGTH(pdf_data) > 0
        """,
        (cutoff_str,),
    )
    cnt, bsize = c.fetchone()
    conn.close()
    bval = int(bsize or 0)
    return {
        "older_than_days": days_val,
        "cutoff_date": cutoff_str,
        "count": int(cnt or 0),
        "bytes": bval,
        "size_formatted": f"{bval / (1024*1024):.2f} MB" if bval >= 1024 * 1024 else f"{bval / 1024:.1f} KB",
    }


def cleanup_old_reports(older_than_days=90, current_admin_user=None, confirm=False, ip="127.0.0.1"):
    """
    Part 1.5: Cleans up generated PDF report blobs older than N days after confirmation,
    reclaiming storage while preserving analysis score summaries, and logs REPORT_STORAGE_CLEANUP.
    """
    clean_admin = str(current_admin_user or "").strip()
    if not is_admin_user(clean_admin):
        record_audit_event(
            username=clean_admin or "unknown",
            action_type="UNAUTHORIZED_ACCESS",
            target="analysis_history.pdf_data",
            details="Unauthorized attempt to clean old report storage",
            status="Denied",
            ip=ip,
        )
        return False, "Access Denied: Administrator role required.", 0

    if not confirm:
        return False, "Confirmation required: Please confirm the report cleanup preview before executing.", 0

    days_val = max(1, int(older_than_days))
    prev = preview_old_reports(days_val)
    cutoff_str = prev["cutoff_date"]

    conn = get_db_connection()
    c = conn.cursor()
    c.execute(
        """
        UPDATE analysis_history
        SET pdf_data = NULL
        WHERE created_at < ? AND pdf_data IS NOT NULL AND LENGTH(pdf_data) > 0
        """,
        (cutoff_str,),
    )
    cleaned = max(0, c.rowcount)
    conn.commit()
    conn.close()

    record_audit_event(
        username=clean_admin,
        action_type="REPORT_STORAGE_CLEANUP",
        target=f"older_than_{days_val}d",
        details=f"Cleaned {cleaned} PDF report blob(s) older than {days_val} days ({prev['size_formatted']} reclaimed)",
        status="Success",
        ip=ip,
    )
    return True, f"Cleaned {cleaned} generated report blob(s) older than {days_val} days ({prev['size_formatted']} reclaimed).", cleaned


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
# CSV EXPORT UTILITIES (FORMULA-INJECTION SAFE & AUDIT-LOGGED)
# ---------------------------------------------------------------------------
def sanitize_csv_cell(val):
    """Prevents spreadsheet formula injection by escaping dangerous leading characters."""
    if val is None:
        return ""
    s = str(val)
    if s and s[0] in ("=", "+", "-", "@", "\t", "\r"):
        s = "'" + s
    return s


def export_users_csv(usernames=None, current_admin_user=None):
    """Generates sanitized CSV export of registered user accounts (never includes passwords/hashes)."""
    users = get_all_users()
    if usernames is not None:
        uset = set(str(x).strip() for x in usernames)
        users = [u for u in users if u.get("username") in uset]
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Username", "Academic Role", "Status", "Created At", "Last Login", "Theme Preference", "Analyses Count"])
    for u in users:
        writer.writerow([
            sanitize_csv_cell(u.get("username")),
            sanitize_csv_cell(u.get("role")),
            sanitize_csv_cell(u.get("status", "Active")),
            sanitize_csv_cell(u.get("created_at", "")),
            sanitize_csv_cell(u.get("last_login", "") or "Never"),
            sanitize_csv_cell(u.get("theme_preference", "System")),
            sanitize_csv_cell(u.get("analysis_count", 0)),
        ])
    if current_admin_user and is_admin_user(current_admin_user):
        record_audit_event(
            username=current_admin_user,
            action_type="DATA_EXPORT",
            target="users.csv",
            details=f"Exported {len(users)} user account record(s) to CSV",
            status="Success",
        )
    return output.getvalue()


def export_audit_csv(limit=1000, start_date=None, end_date=None, current_admin_user=None):
    """Generates sanitized CSV export of security audit logs."""
    logs = get_login_history(limit=limit, start_date=start_date, end_date=end_date)
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Event ID", "Timestamp", "Username", "Role", "Action Type", "Status / Outcome", "IP Address", "Target", "Details", "Row Hash"])
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
            sanitize_csv_cell(l.get("row_hash", "")),
        ])
    if current_admin_user and is_admin_user(current_admin_user):
        record_audit_event(
            username=current_admin_user,
            action_type="DATA_EXPORT",
            target="audit_log.csv",
            details=f"Exported {len(logs)} audit log record(s) to CSV",
            status="Success",
        )
    return output.getvalue()


def export_repository_csv(current_admin_user=None):
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
    if current_admin_user and is_admin_user(current_admin_user):
        record_audit_event(
            username=current_admin_user,
            action_type="DATA_EXPORT",
            target="repository.csv",
            details=f"Exported {len(papers)} institutional repository record(s) to CSV",
            status="Success",
        )
    return output.getvalue()


def export_upload_history_csv(limit=500, exclude_test_accounts=False, current_admin_user=None):
    """
    Part 3: Generates sanitized CSV export of upload activity with masked filenames ('abc….pdf').
    Never exports private user filenames or document titles.
    """
    uploads = get_upload_history(
        username=None,
        limit=limit,
        mask_filenames=True,
        exclude_test_accounts=exclude_test_accounts,
    )
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Event ID", "Upload Timestamp", "Username", "Masked Filename", "Format", "Size (KB)", "Target Scope", "Status"])
    for u in uploads:
        writer.writerow([
            sanitize_csv_cell(u.get("id")),
            sanitize_csv_cell(u.get("upload_time")),
            sanitize_csv_cell(u.get("username")),
            sanitize_csv_cell(u.get("masked_filename") or mask_filename(u.get("filename", ""))),
            sanitize_csv_cell(u.get("file_type")),
            sanitize_csv_cell(u.get("file_size_kb")),
            sanitize_csv_cell(u.get("target", "Personal")),
            sanitize_csv_cell(u.get("status", "Processed")),
        ])
    if current_admin_user and is_admin_user(current_admin_user):
        record_audit_event(
            username=current_admin_user,
            action_type="DATA_EXPORT",
            target="upload_history.csv",
            details=f"Exported {len(uploads)} masked upload telemetry record(s) to CSV",
            status="Success",
        )
    return output.getvalue()


def export_audit_logs_csv(limit=1000, start_date=None, end_date=None, current_admin_user=None):
    """Alias for export_audit_csv."""
    return export_audit_csv(limit=limit, start_date=start_date, end_date=end_date, current_admin_user=current_admin_user)


def export_analytics_summary_csv(exclude_test_accounts=False, start_date=None, end_date=None, current_admin_user=None):
    """
    Part 1.4 & Part 3: Exports aggregate-only research activity summary to CSV.
    Strictly excludes private filenames, titles, paper text, and results_json.
    """
    rows = get_all_analyses_summary(
        exclude_test_accounts=exclude_test_accounts,
        start_date=start_date,
        end_date=end_date,
        current_admin_user=current_admin_user,
    )
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Record ID", "Username", "Role", "Canonical Discipline", "Score", "Grade", "Created At"])
    for r in rows:
        writer.writerow([
            sanitize_csv_cell(r.get("id")),
            sanitize_csv_cell(r.get("username")),
            sanitize_csv_cell(r.get("role", "Student")),
            sanitize_csv_cell(r.get("domain")),
            sanitize_csv_cell(r.get("score")),
            sanitize_csv_cell(r.get("grade", "")),
            sanitize_csv_cell(r.get("created_at", "")),
        ])
    if current_admin_user and is_admin_user(current_admin_user):
        record_audit_event(
            username=current_admin_user,
            action_type="DATA_EXPORT",
            target="analytics_summary.csv",
            details=f"Exported {len(rows)} aggregate research activity record(s) to CSV",
            status="Success",
        )
    return output.getvalue()



# ---------------------------------------------------------------------------
# RESEARCHER WORKSPACE MIGRATIONS & OWNERSHIP-ENFORCED DATA ACCESS LAYER
# ---------------------------------------------------------------------------

def backup_database(backup_path=None):
    """Create a non-destructive backup of users.db before schema migrations."""
    import shutil
    target = backup_path or (DB_PATH + ".bak")
    if os.path.exists(DB_PATH):
        shutil.copy2(DB_PATH, target)
    return target


def _ensure_table_columns(cursor, table_name, required_columns):
    """Idempotently add any missing columns to an existing SQLite table."""
    cursor.execute(f"PRAGMA table_info({table_name})")
    existing = {row["name"] for row in cursor.fetchall()}
    for col_name, col_def in required_columns:
        if col_name not in existing:
            try:
                cursor.execute(f"ALTER TABLE {table_name} ADD COLUMN {col_name} {col_def}")
            except Exception:
                pass


def run_researcher_migrations(conn=None):
    """
    Idempotent, non-destructive migration that creates/updates all Researcher workspace tables:
    - projects(id, user_id, name, description, created_at, updated_at)
    - project_papers(project_id, analysis_id, user_id, created_at)
    - paper_metadata(analysis_id, user_id, title, authors, year, journal, keywords_json, topics_json, domain, research_profile_json, created_at, updated_at)
    - tags(id, user_id, name, created_at)
    - paper_tags(analysis_id, tag_id, user_id, created_at)
    - research_notes(id, user_id, analysis_id, project_id, note_text, created_at, updated_at)
    - activity_log(id, user_id, event_type, title, details, analysis_id, project_id, created_at)
    - saved_comparisons(id, user_id, title, paper_ids_json, matrix_json, synthesis_json, project_id, created_at, updated_at)
    - paper_chats(id, user_id, scope_key, question, answer, evidence_json, created_at)
    Can be called multiple times safely without losing existing data.
    """
    own_conn = False
    if conn is None:
        conn = get_db_connection()
        own_conn = True

    c = conn.cursor()
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # 1. projects
    c.execute("""
        CREATE TABLE IF NOT EXISTS projects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            name TEXT NOT NULL,
            description TEXT DEFAULT '',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    """)
    _ensure_table_columns(c, "projects", [
        ("user_id", "TEXT DEFAULT ''"),
        ("name", "TEXT DEFAULT ''"),
        ("description", "TEXT DEFAULT ''"),
        ("created_at", f"TEXT DEFAULT '{now_str}'"),
        ("updated_at", f"TEXT DEFAULT '{now_str}'"),
    ])

    # 2. project_papers (many-to-many)
    c.execute("""
        CREATE TABLE IF NOT EXISTS project_papers (
            project_id INTEGER NOT NULL,
            analysis_id TEXT NOT NULL,
            user_id TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL DEFAULT '',
            updated_at TEXT NOT NULL DEFAULT '',
            PRIMARY KEY (project_id, analysis_id)
        )
    """)
    _ensure_table_columns(c, "project_papers", [
        ("user_id", "TEXT DEFAULT ''"),
        ("created_at", f"TEXT DEFAULT '{now_str}'"),
        ("updated_at", f"TEXT DEFAULT '{now_str}'"),
    ])

    # 3. paper_metadata
    c.execute("""
        CREATE TABLE IF NOT EXISTS paper_metadata (
            analysis_id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            title TEXT DEFAULT '',
            authors TEXT DEFAULT '',
            year TEXT DEFAULT '',
            journal TEXT DEFAULT '',
            keywords_json TEXT DEFAULT '[]',
            topics_json TEXT DEFAULT '[]',
            domain TEXT DEFAULT '',
            research_profile_json TEXT DEFAULT '{}',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    """)
    _ensure_table_columns(c, "paper_metadata", [
        ("user_id", "TEXT DEFAULT ''"),
        ("title", "TEXT DEFAULT ''"),
        ("authors", "TEXT DEFAULT ''"),
        ("year", "TEXT DEFAULT ''"),
        ("journal", "TEXT DEFAULT ''"),
        ("keywords_json", "TEXT DEFAULT '[]'"),
        ("topics_json", "TEXT DEFAULT '[]'"),
        ("domain", "TEXT DEFAULT ''"),
        ("research_profile_json", "TEXT DEFAULT '{}'"),
        ("created_at", f"TEXT DEFAULT '{now_str}'"),
        ("updated_at", f"TEXT DEFAULT '{now_str}'"),
    ])

    # 4. tags & paper_tags
    c.execute("""
        CREATE TABLE IF NOT EXISTS tags (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            name TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            UNIQUE(user_id, name)
        )
    """)
    _ensure_table_columns(c, "tags", [
        ("user_id", "TEXT DEFAULT ''"),
        ("name", "TEXT DEFAULT ''"),
        ("created_at", f"TEXT DEFAULT '{now_str}'"),
        ("updated_at", f"TEXT DEFAULT '{now_str}'"),
    ])

    c.execute("""
        CREATE TABLE IF NOT EXISTS paper_tags (
            analysis_id TEXT NOT NULL,
            tag_id INTEGER NOT NULL,
            user_id TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL DEFAULT '',
            updated_at TEXT NOT NULL DEFAULT '',
            PRIMARY KEY (analysis_id, tag_id)
        )
    """)
    _ensure_table_columns(c, "paper_tags", [
        ("user_id", "TEXT DEFAULT ''"),
        ("created_at", f"TEXT DEFAULT '{now_str}'"),
        ("updated_at", f"TEXT DEFAULT '{now_str}'"),
    ])

    # 5. research_notes
    c.execute("""
        CREATE TABLE IF NOT EXISTS research_notes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            analysis_id TEXT NOT NULL,
            project_id INTEGER DEFAULT NULL,
            note_text TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    """)
    _ensure_table_columns(c, "research_notes", [
        ("user_id", "TEXT DEFAULT ''"),
        ("analysis_id", "TEXT DEFAULT ''"),
        ("project_id", "INTEGER DEFAULT NULL"),
        ("note_text", "TEXT DEFAULT ''"),
        ("created_at", f"TEXT DEFAULT '{now_str}'"),
        ("updated_at", f"TEXT DEFAULT '{now_str}'"),
    ])

    # 6. activity_log (for Researcher Dashboard timeline)
    c.execute("""
        CREATE TABLE IF NOT EXISTS activity_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            event_type TEXT NOT NULL,
            title TEXT NOT NULL,
            details TEXT DEFAULT '',
            analysis_id TEXT DEFAULT '',
            project_id INTEGER DEFAULT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    """)
    _ensure_table_columns(c, "activity_log", [
        ("user_id", "TEXT DEFAULT ''"),
        ("event_type", "TEXT DEFAULT ''"),
        ("title", "TEXT DEFAULT ''"),
        ("details", "TEXT DEFAULT ''"),
        ("analysis_id", "TEXT DEFAULT ''"),
        ("project_id", "INTEGER DEFAULT NULL"),
        ("created_at", f"TEXT DEFAULT '{now_str}'"),
        ("updated_at", f"TEXT DEFAULT '{now_str}'"),
    ])

    # 7. saved_comparisons
    c.execute("""
        CREATE TABLE IF NOT EXISTS saved_comparisons (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            title TEXT NOT NULL,
            paper_ids_json TEXT NOT NULL DEFAULT '[]',
            matrix_json TEXT NOT NULL DEFAULT '{}',
            synthesis_json TEXT NOT NULL DEFAULT '{}',
            project_id INTEGER DEFAULT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    """)
    _ensure_table_columns(c, "saved_comparisons", [
        ("user_id", "TEXT DEFAULT ''"),
        ("title", "TEXT DEFAULT ''"),
        ("paper_ids_json", "TEXT DEFAULT '[]'"),
        ("matrix_json", "TEXT DEFAULT '{}'"),
        ("synthesis_json", "TEXT DEFAULT '{}'"),
        ("project_id", "INTEGER DEFAULT NULL"),
        ("created_at", f"TEXT DEFAULT '{now_str}'"),
        ("updated_at", f"TEXT DEFAULT '{now_str}'"),
    ])

    # 8. paper_chats (per-user, per-paper/project Ask PaperIQ chat persistence)
    c.execute("""
        CREATE TABLE IF NOT EXISTS paper_chats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            scope_key TEXT NOT NULL,
            question TEXT NOT NULL,
            answer TEXT NOT NULL,
            evidence_json TEXT DEFAULT '[]',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    """)
    _ensure_table_columns(c, "paper_chats", [
        ("user_id", "TEXT DEFAULT ''"),
        ("scope_key", "TEXT DEFAULT ''"),
        ("question", "TEXT DEFAULT ''"),
        ("answer", "TEXT DEFAULT ''"),
        ("evidence_json", "TEXT DEFAULT '[]'"),
        ("created_at", f"TEXT DEFAULT '{now_str}'"),
        ("updated_at", f"TEXT DEFAULT '{now_str}'"),
    ])

    if own_conn:
        conn.commit()
        conn.close()
    return True


def _resolve_canonical_analysis_id(record_or_analysis_id, user_id):
    """Resolve either numeric id or string analysis_id to the canonical analysis_id owned by user_id."""
    if not record_or_analysis_id or not user_id:
        return None
    clean_u = str(user_id).strip()
    conn = get_db_connection()
    c = conn.cursor()
    c.execute(
        "SELECT id, analysis_id FROM analysis_history WHERE (id = ? OR analysis_id = ?) AND username = ?",
        (record_or_analysis_id, str(record_or_analysis_id), clean_u),
    )
    row = c.fetchone()
    conn.close()
    if not row:
        return None
    return row["analysis_id"] or f"ANL-{row['id']}"


def verify_project_ownership(project_id, user_id):
    """Strictly verify that project_id belongs to user_id."""
    if not project_id or not user_id:
        return False
    try:
        conn = get_db_connection()
        c = conn.cursor()
        c.execute(
            "SELECT id FROM projects WHERE id = ? AND user_id = ?",
            (int(project_id), str(user_id).strip()),
        )
        row = c.fetchone()
        conn.close()
        return row is not None
    except Exception:
        return False


def verify_note_ownership(note_id, user_id):
    """Strictly verify that research note belongs to user_id."""
    if not note_id or not user_id:
        return False
    try:
        conn = get_db_connection()
        c = conn.cursor()
        c.execute(
            "SELECT id FROM research_notes WHERE id = ? AND user_id = ?",
            (int(note_id), str(user_id).strip()),
        )
        row = c.fetchone()
        conn.close()
        return row is not None
    except Exception:
        return False


def verify_tag_ownership(tag_id, user_id):
    """Strictly verify that tag belongs to user_id."""
    if not tag_id or not user_id:
        return False
    try:
        conn = get_db_connection()
        c = conn.cursor()
        c.execute(
            "SELECT id FROM tags WHERE id = ? AND user_id = ?",
            (int(tag_id), str(user_id).strip()),
        )
        row = c.fetchone()
        conn.close()
        return row is not None
    except Exception:
        return False


def verify_comparison_ownership(comp_id, user_id):
    """Strictly verify that saved comparison belongs to user_id."""
    if not comp_id or not user_id:
        return False
    try:
        conn = get_db_connection()
        c = conn.cursor()
        c.execute(
            "SELECT id FROM saved_comparisons WHERE id = ? AND user_id = ?",
            (int(comp_id), str(user_id).strip()),
        )
        row = c.fetchone()
        conn.close()
        return row is not None
    except Exception:
        return False


def log_research_activity(user_id, event_type, title, details="", analysis_id="", project_id=None):
    """Record a user-scoped research activity event for the Researcher Dashboard timeline."""
    if not user_id:
        return None
    create_users_table()
    clean_u = str(user_id).strip()
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn = get_db_connection()
    c = conn.cursor()
    c.execute(
        """
        INSERT INTO activity_log (user_id, event_type, title, details, analysis_id, project_id, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            clean_u,
            _unescape_val(str(event_type)),
            _unescape_val(str(title)),
            _unescape_val(str(details or "")),
            str(analysis_id or ""),
            int(project_id) if project_id is not None else None,
            now_str,
            now_str,
        ),
    )
    conn.commit()
    row_id = c.lastrowid
    conn.close()
    return row_id


def get_research_activity(user_id, limit=25):
    """Retrieve the most recent research activity events strictly for user_id."""
    if not user_id:
        return []
    create_users_table()
    clean_u = str(user_id).strip()
    conn = get_db_connection()
    c = conn.cursor()
    c.execute(
        """
        SELECT id, user_id, event_type, title, details, analysis_id, project_id, created_at
        FROM activity_log
        WHERE user_id = ?
        ORDER BY id DESC
        LIMIT ?
        """,
        (clean_u, int(limit)),
    )
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    for r in rows:
        r["title"] = _unescape_val(r.get("title", ""))
        r["details"] = _unescape_val(r.get("details", ""))
    return rows


# --- Projects & Project-Papers (Many-to-Many) ---

def create_project(user_id, name, description=""):
    """Create a new research project owned by user_id."""
    if not user_id or not name or not str(name).strip():
        return False, "Project name is required.", None
    create_users_table()
    clean_u = str(user_id).strip()
    clean_name = _unescape_val(str(name).strip())
    clean_desc = _unescape_val(str(description or "").strip())
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    conn = get_db_connection()
    c = conn.cursor()
    c.execute(
        "SELECT id FROM projects WHERE user_id = ? AND LOWER(name) = LOWER(?)",
        (clean_u, clean_name),
    )
    existing = c.fetchone()
    if existing:
        conn.close()
        return False, f"A project named '{clean_name}' already exists.", existing["id"]

    c.execute(
        """
        INSERT INTO projects (user_id, name, description, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        (clean_u, clean_name, clean_desc, now_str, now_str),
    )
    conn.commit()
    proj_id = c.lastrowid
    conn.close()
    log_research_activity(clean_u, "project_created", f"Created project '{clean_name}'", clean_desc, project_id=proj_id)
    return True, f"Project '{clean_name}' created.", proj_id


def get_user_projects(user_id):
    """Return all projects owned by user_id with paper counts and assigned analysis_ids."""
    if not user_id:
        return []
    create_users_table()
    clean_u = str(user_id).strip()
    conn = get_db_connection()
    c = conn.cursor()
    c.execute(
        """
        SELECT p.id, p.user_id, p.name, p.description, p.created_at, p.updated_at
        FROM projects p
        WHERE p.user_id = ?
        ORDER BY p.updated_at DESC, p.id DESC
        """,
        (clean_u,),
    )
    projects = [dict(r) for r in c.fetchall()]
    for p in projects:
        p["name"] = _unescape_val(p.get("name", ""))
        p["description"] = _unescape_val(p.get("description", ""))
        c.execute(
            """
            SELECT pp.analysis_id
            FROM project_papers pp
            INNER JOIN analysis_history ah
              ON (ah.analysis_id = pp.analysis_id OR CAST(ah.id AS TEXT) = pp.analysis_id)
             AND ah.username = ?
            WHERE pp.project_id = ? AND pp.user_id = ?
            """,
            (clean_u, p["id"], clean_u),
        )
        a_ids = [r["analysis_id"] for r in c.fetchall()]
        p["paper_ids"] = a_ids
        p["paper_count"] = len(a_ids)
    conn.close()
    return projects


def _looks_like_id(val):
    if isinstance(val, int) and not isinstance(val, bool):
        return True
    s = str(val or "").strip()
    return s.isdigit() or s.startswith("ANL-")


def _swap_if_user_first(a, b):
    """If `a` is username and `b` is numeric/ANL ID, return (id=b, user_id=a); else (id=a, user_id=b)."""
    if not _looks_like_id(a) and _looks_like_id(b):
        return b, a
    return a, b


def register_user(username, email_or_password, password=None, role="Student"):
    """Register a user account (alias supporting optional email parameter)."""
    pw = password if password is not None else email_or_password
    return signup_user(username=username, password=pw, role=role)


def save_user_analysis(
    username,
    filename,
    paper_title=None,
    overall_score=0.0,
    structure_score=0.0,
    clarity_score=0.0,
    coherence_score=0.0,
    citation_score=0.0,
    readability_score=0.0,
    summary="",
    feedback=None,
    extracted_text="",
    sections=None,
    metrics=None,
    domain="Interdisciplinary",
    pdf_bytes=b"",
):
    """Save a full researcher/student analysis into `analysis_history` and return its integer record ID."""
    results_payload = {
        "title": _unescape_val(paper_title or filename),
        "paper_title": _unescape_val(paper_title or filename),
        "overall_score": float(overall_score or 0.0),
        "structure_score": float(structure_score or 0.0),
        "clarity_score": float(clarity_score or 0.0),
        "coherence_score": float(coherence_score or 0.0),
        "citation_score": float(citation_score or 0.0),
        "readability_score": float(readability_score or 0.0),
        "summary": _unescape_val(summary or ""),
        "feedback": feedback or [],
        "extracted_text": _unescape_val(extracted_text or ""),
        "sections": sections or {},
        "metrics": metrics or {},
        "domain": _unescape_val(domain or "Interdisciplinary"),
    }
    rec_id, _, _ = save_analysis_record(
        username=username,
        filename=filename,
        domain=domain or "Interdisciplinary",
        score=float(overall_score or 0.0),
        pdf_bytes=pdf_bytes or b"",
        results_json=json.dumps(results_payload),
        display_title=paper_title or filename,
        dimension_scores={
            "Language Quality": float(clarity_score or overall_score or 0.0),
            "Structural Coherence": float(structure_score or overall_score or 0.0),
            "Argumentation": float(coherence_score or overall_score or 0.0),
            "Academic Style": float(citation_score or overall_score or 0.0),
            "Readability": float(readability_score or overall_score or 0.0),
        },
    )
    return rec_id


def delete_user_analysis(username_or_id, id_or_username):
    """Delete an analysis record owned by user."""
    rec_id, clean_u = _swap_if_user_first(username_or_id, id_or_username)
    ok, _ = delete_analysis_record(rec_id, clean_u)
    return ok


def clear_all_user_analyses(username):
    """Delete all analyses owned by `username`."""
    ok, _ = clear_user_history(username)
    return ok


def get_project_by_id(arg1, arg2):
    """Fetch a single project only if owned by user_id."""
    project_id, user_id = _swap_if_user_first(arg1, arg2)
    if not verify_project_ownership(project_id, user_id):
        return None
    for p in get_user_projects(user_id):
        if int(p["id"]) == int(project_id):
            return p
    return None


def rename_project(arg1, arg2, new_name, new_description=None):
    """Rename or update description of a project owned by user_id."""
    project_id, user_id = _swap_if_user_first(arg1, arg2)
    clean_u = str(user_id or "").strip()
    if not verify_project_ownership(project_id, clean_u):
        record_audit_event(clean_u or "unknown", "UNAUTHORIZED_ACCESS", f"project_id={project_id}", "Unauthorized project rename attempt", status="Denied")
        return False, "Access Denied: You do not own this project."
    if not new_name or not str(new_name).strip():
        return False, "Project name cannot be empty."
    clean_name = _unescape_val(str(new_name).strip())
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn = get_db_connection()
    c = conn.cursor()
    if new_description is not None:
        clean_desc = _unescape_val(str(new_description).strip())
        c.execute(
            "UPDATE projects SET name = ?, description = ?, updated_at = ? WHERE id = ? AND user_id = ?",
            (clean_name, clean_desc, now_str, int(project_id), clean_u),
        )
    else:
        c.execute(
            "UPDATE projects SET name = ?, updated_at = ? WHERE id = ? AND user_id = ?",
            (clean_name, now_str, int(project_id), clean_u),
        )
    conn.commit()
    conn.close()
    return True, f"Project updated to '{clean_name}'."


def delete_project(arg1, arg2, delete_papers=False):
    """
    Delete a project owned by user_id.
    By default (delete_papers=False), papers remain intact in the user's Research Library.
    If delete_papers=True, papers assigned to this project (and owned by user_id) are also deleted.
    """
    project_id, user_id = _swap_if_user_first(arg1, arg2)
    clean_u = str(user_id or "").strip()
    if not verify_project_ownership(project_id, clean_u):
        record_audit_event(clean_u or "unknown", "UNAUTHORIZED_ACCESS", f"project_id={project_id}", "Unauthorized project delete attempt", status="Denied")
        return False, "Access Denied: You do not own this project."

    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT name FROM projects WHERE id = ? AND user_id = ?", (int(project_id), clean_u))
    prow = c.fetchone()
    proj_name = prow["name"] if prow else f"Project #{project_id}"

    if delete_papers:
        c.execute(
            "SELECT analysis_id FROM project_papers WHERE project_id = ? AND user_id = ?",
            (int(project_id), clean_u),
        )
        a_ids = [r["analysis_id"] for r in c.fetchall()]
        conn.close()
        for aid in a_ids:
            delete_analysis_record(aid, clean_u)
        conn = get_db_connection()
        c = conn.cursor()

    c.execute("DELETE FROM project_papers WHERE project_id = ? AND user_id = ?", (int(project_id), clean_u))
    c.execute("DELETE FROM research_notes WHERE project_id = ? AND user_id = ?", (int(project_id), clean_u))
    c.execute("DELETE FROM projects WHERE id = ? AND user_id = ?", (int(project_id), clean_u))
    conn.commit()
    conn.close()
    log_research_activity(clean_u, "project_deleted", f"Deleted project '{proj_name}'", "Papers retained in library" if not delete_papers else "Project and papers deleted")
    return True, f"Project '{proj_name}' deleted." + (" Papers remain in your Research Library." if not delete_papers else " Assigned papers were also deleted.")


def assign_paper_to_project(arg1, arg2, arg3):
    """Link a paper owned by user_id to a project owned by user_id. Supports (user_id, project_id, analysis_id) or (project_id, analysis_id, user_id)."""
    if not _looks_like_id(arg1):
        user_id, project_id, analysis_id = arg1, arg2, arg3
    else:
        project_id, analysis_id, user_id = arg1, arg2, arg3
    clean_u = str(user_id or "").strip()
    if not verify_project_ownership(project_id, clean_u):
        record_audit_event(clean_u or "unknown", "UNAUTHORIZED_ACCESS", f"project_id={project_id}", "Unauthorized project assignment attempt", status="Denied")
        return False
    canonical_aid = _resolve_canonical_analysis_id(analysis_id, clean_u)
    if not canonical_aid:
        record_audit_event(clean_u or "unknown", "UNAUTHORIZED_ACCESS", f"analysis_id={analysis_id}", "Unauthorized paper assignment attempt", status="Denied")
        return False

    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn = get_db_connection()
    c = conn.cursor()
    c.execute(
        """
        INSERT OR IGNORE INTO project_papers (project_id, analysis_id, user_id, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        (int(project_id), canonical_aid, clean_u, now_str, now_str),
    )
    c.execute("UPDATE projects SET updated_at = ? WHERE id = ? AND user_id = ?", (now_str, int(project_id), clean_u))
    conn.commit()
    conn.close()
    return True


def remove_paper_from_project(arg1, arg2, arg3):
    """Unlink a paper from a project (paper stays in library)."""
    if not _looks_like_id(arg1):
        user_id, project_id, analysis_id = arg1, arg2, arg3
    else:
        project_id, analysis_id, user_id = arg1, arg2, arg3
    clean_u = str(user_id or "").strip()
    if not verify_project_ownership(project_id, clean_u):
        return False
    canonical_aid = _resolve_canonical_analysis_id(analysis_id, clean_u) or str(analysis_id)
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn = get_db_connection()
    c = conn.cursor()
    c.execute(
        "DELETE FROM project_papers WHERE project_id = ? AND analysis_id = ? AND user_id = ?",
        (int(project_id), canonical_aid, clean_u),
    )
    c.execute("UPDATE projects SET updated_at = ? WHERE id = ? AND user_id = ?", (now_str, int(project_id), clean_u))
    conn.commit()
    conn.close()
    return True


def set_paper_projects(arg1, arg2, arg3):
    """Replace the set of projects associated with analysis_id for user_id. Supports (user_id, analysis_id, project_ids) or (analysis_id, project_ids, user_id)."""
    if isinstance(arg3, (list, tuple, set)):
        user_id, analysis_id, project_ids = arg1, arg2, arg3
    else:
        analysis_id, project_ids, user_id = arg1, arg2, arg3
    clean_u = str(user_id or "").strip()
    canonical_aid = _resolve_canonical_analysis_id(analysis_id, clean_u)
    if not canonical_aid:
        return False
    valid_pids = []
    for pid in (project_ids or []):
        if verify_project_ownership(pid, clean_u):
            valid_pids.append(int(pid))
        else:
            return False

    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("DELETE FROM project_papers WHERE analysis_id = ? AND user_id = ?", (canonical_aid, clean_u))
    for pid in valid_pids:
        c.execute(
            "INSERT OR IGNORE INTO project_papers (project_id, analysis_id, user_id, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
            (pid, canonical_aid, clean_u, now_str, now_str),
        )
        c.execute("UPDATE projects SET updated_at = ? WHERE id = ? AND user_id = ?", (now_str, pid, clean_u))
    conn.commit()
    conn.close()
    return True


# --- Paper Metadata & Tags ---

def upsert_paper_metadata(
    analysis_id=None,
    user_id=None,
    title="",
    authors="",
    year="",
    journal="",
    keywords=None,
    topics=None,
    domain="",
    research_profile=None,
    username=None,
):
    """Create or update researcher metadata and structured research profile for an analysis owned by user_id."""
    if username and not user_id:
        user_id = username
    if analysis_id is not None and user_id is not None and not _looks_like_id(analysis_id) and _looks_like_id(user_id):
        analysis_id, user_id = user_id, analysis_id
    clean_u = str(user_id or "").strip()
    canonical_aid = _resolve_canonical_analysis_id(analysis_id, clean_u)
    if not canonical_aid:
        record_audit_event(clean_u or "unknown", "UNAUTHORIZED_ACCESS", f"analysis_id={analysis_id}", "Unauthorized metadata update attempt", status="Denied")
        return False

    create_users_table()
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    kw_json = json.dumps([_unescape_val(str(k).strip()) for k in (keywords or []) if str(k).strip()])
    top_json = json.dumps([_unescape_val(str(t).strip()) for t in (topics or []) if str(t).strip()])
    prof_json = json.dumps(research_profile or {})

    clean_title = _unescape_val(str(title or "").strip())
    clean_authors = _unescape_val(str(authors or "").strip())
    clean_year = _unescape_val(str(year or "").strip())
    clean_journal = _unescape_val(str(journal or "").strip())
    clean_domain = _unescape_val(str(domain or "").strip())

    conn = get_db_connection()
    c = conn.cursor()
    c.execute(
        "SELECT analysis_id, created_at, research_profile_json FROM paper_metadata WHERE analysis_id = ? AND user_id = ?",
        (canonical_aid, clean_u),
    )
    existing = c.fetchone()
    if existing:
        if research_profile is None and existing["research_profile_json"]:
            prof_json = existing["research_profile_json"]
        c.execute(
            """
            UPDATE paper_metadata
            SET title = ?, authors = ?, year = ?, journal = ?, keywords_json = ?, topics_json = ?,
                domain = ?, research_profile_json = ?, updated_at = ?
            WHERE analysis_id = ? AND user_id = ?
            """,
            (
                clean_title,
                clean_authors,
                clean_year,
                clean_journal,
                kw_json,
                top_json,
                clean_domain,
                prof_json,
                now_str,
                canonical_aid,
                clean_u,
            ),
        )
    else:
        c.execute(
            """
            INSERT INTO paper_metadata (
                analysis_id, user_id, title, authors, year, journal,
                keywords_json, topics_json, domain, research_profile_json, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                canonical_aid,
                clean_u,
                clean_title,
                clean_authors,
                clean_year,
                clean_journal,
                kw_json,
                top_json,
                clean_domain,
                prof_json,
                now_str,
                now_str,
            ),
        )
    if clean_title:
        c.execute(
            "UPDATE analysis_history SET display_title = ? WHERE analysis_id = ? AND username = ?",
            (clean_title, canonical_aid, clean_u),
        )
    if clean_domain:
        c.execute(
            "UPDATE analysis_history SET domain = ? WHERE analysis_id = ? AND username = ?",
            (clean_domain, canonical_aid, clean_u),
        )
    conn.commit()
    conn.close()
    return True


def get_paper_metadata(arg1, arg2):
    """Fetch paper_metadata strictly for (analysis_id, user_id)."""
    analysis_id, user_id = _swap_if_user_first(arg1, arg2)
    clean_u = str(user_id or "").strip()
    canonical_aid = _resolve_canonical_analysis_id(analysis_id, clean_u)
    if not canonical_aid:
        return None
    create_users_table()
    conn = get_db_connection()
    c = conn.cursor()
    c.execute(
        "SELECT * FROM paper_metadata WHERE analysis_id = ? AND user_id = ?",
        (canonical_aid, clean_u),
    )
    row = c.fetchone()
    conn.close()
    if not row:
        return None
    d = dict(row)
    try:
        d["keywords"] = json.loads(d.get("keywords_json") or "[]")
    except Exception:
        d["keywords"] = []
    try:
        d["topics"] = json.loads(d.get("topics_json") or "[]")
    except Exception:
        d["topics"] = []
    try:
        d["research_profile"] = json.loads(d.get("research_profile_json") or "{}")
    except Exception:
        d["research_profile"] = {}
    d["title"] = _unescape_val(d.get("title", ""))
    d["authors"] = _unescape_val(d.get("authors", ""))
    d["year"] = _unescape_val(d.get("year", ""))
    d["journal"] = _unescape_val(d.get("journal", ""))
    d["domain"] = _unescape_val(d.get("domain", ""))
    return d


def set_paper_tags(arg1, arg2, arg3):
    """Assign user-owned tags to a paper owned by user_id. Supports (user_id, analysis_id, tag_names) or (analysis_id, tag_names, user_id)."""
    if isinstance(arg3, (list, tuple, set)):
        user_id, analysis_id, tag_names = arg1, arg2, arg3
    else:
        analysis_id, tag_names, user_id = arg1, arg2, arg3
    clean_u = str(user_id or "").strip()
    canonical_aid = _resolve_canonical_analysis_id(analysis_id, clean_u)
    if not canonical_aid:
        return False

    create_users_table()
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cleaned_tags = []
    for t in (tag_names or []):
        ts = _unescape_val(str(t).strip())
        if ts and ts.lower() not in [x.lower() for x in cleaned_tags]:
            cleaned_tags.append(ts)

    conn = get_db_connection()
    c = conn.cursor()
    c.execute("DELETE FROM paper_tags WHERE analysis_id = ? AND user_id = ?", (canonical_aid, clean_u))
    for t_name in cleaned_tags:
        c.execute("SELECT id FROM tags WHERE user_id = ? AND LOWER(name) = LOWER(?)", (clean_u, t_name))
        t_row = c.fetchone()
        if t_row:
            tag_id = t_row["id"]
        else:
            c.execute(
                "INSERT INTO tags (user_id, name, created_at, updated_at) VALUES (?, ?, ?, ?)",
                (clean_u, t_name, now_str, now_str),
            )
            tag_id = c.lastrowid
        c.execute(
            "INSERT OR IGNORE INTO paper_tags (analysis_id, tag_id, user_id, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
            (canonical_aid, tag_id, clean_u, now_str, now_str),
        )
    conn.commit()
    conn.close()
    return True


def get_paper_tags(arg1, arg2):
    """Return tag names assigned to analysis_id for user_id."""
    analysis_id, user_id = _swap_if_user_first(arg1, arg2)
    clean_u = str(user_id or "").strip()
    canonical_aid = _resolve_canonical_analysis_id(analysis_id, clean_u)
    if not canonical_aid:
        return []
    create_users_table()
    conn = get_db_connection()
    c = conn.cursor()
    c.execute(
        """
        SELECT t.name
        FROM paper_tags pt
        INNER JOIN tags t ON t.id = pt.tag_id AND t.user_id = ?
        WHERE pt.analysis_id = ? AND pt.user_id = ?
        ORDER BY t.name ASC
        """,
        (clean_u, canonical_aid, clean_u),
    )
    tags = [_unescape_val(r["name"]) for r in c.fetchall()]
    conn.close()
    return tags


def get_user_tags(user_id):
    """Return all tags created by user_id."""
    if not user_id:
        return []
    create_users_table()
    clean_u = str(user_id).strip()
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT id, name, created_at FROM tags WHERE user_id = ? ORDER BY name ASC", (clean_u,))
    rows = [{"id": r["id"], "name": _unescape_val(r["name"]), "created_at": r["created_at"]} for r in c.fetchall()]
    conn.close()
    return rows


# --- Research Notes ---

def add_research_note(user_id, analysis_id, note_text, project_id=None):
    """Add a researcher note to a paper (and/or project) owned by user_id."""
    clean_u = str(user_id or "").strip()
    if not clean_u or not note_text or not str(note_text).strip():
        return False, "Note text cannot be empty.", None

    canonical_aid = ""
    if analysis_id:
        canonical_aid = _resolve_canonical_analysis_id(analysis_id, clean_u)
        if not canonical_aid:
            record_audit_event(clean_u, "UNAUTHORIZED_ACCESS", f"analysis_id={analysis_id}", "Unauthorized note creation attempt", status="Denied")
            return False, "Access Denied: You can only add notes to your own papers.", None

    if project_id is not None and not verify_project_ownership(project_id, clean_u):
        record_audit_event(clean_u, "UNAUTHORIZED_ACCESS", f"project_id={project_id}", "Unauthorized project note creation attempt", status="Denied")
        return False, "Access Denied: You do not own this project.", None

    create_users_table()
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    clean_note = _unescape_val(str(note_text).strip())
    conn = get_db_connection()
    c = conn.cursor()
    c.execute(
        """
        INSERT INTO research_notes (user_id, analysis_id, project_id, note_text, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (clean_u, canonical_aid, int(project_id) if project_id is not None else None, clean_note, now_str, now_str),
    )
    conn.commit()
    note_id = c.lastrowid
    conn.close()
    log_research_activity(clean_u, "note_added", "Added research note", clean_note[:80], analysis_id=canonical_aid, project_id=project_id)
    return True, "Research note saved.", note_id


def update_research_note(arg1, arg2, note_text):
    """Update an existing research note owned by user_id."""
    note_id, user_id = _swap_if_user_first(arg1, arg2)
    clean_u = str(user_id or "").strip()
    if not verify_note_ownership(note_id, clean_u):
        record_audit_event(clean_u or "unknown", "UNAUTHORIZED_ACCESS", f"note_id={note_id}", "Unauthorized note update attempt", status="Denied")
        return False
    if not note_text or not str(note_text).strip():
        return False
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    clean_note = _unescape_val(str(note_text).strip())
    conn = get_db_connection()
    c = conn.cursor()
    c.execute(
        "UPDATE research_notes SET note_text = ?, updated_at = ? WHERE id = ? AND user_id = ?",
        (clean_note, now_str, int(note_id), clean_u),
    )
    conn.commit()
    conn.close()
    return True


def delete_research_note(arg1, arg2):
    """Delete a research note owned by user_id."""
    note_id, user_id = _swap_if_user_first(arg1, arg2)
    clean_u = str(user_id or "").strip()
    if not verify_note_ownership(note_id, clean_u):
        record_audit_event(clean_u or "unknown", "UNAUTHORIZED_ACCESS", f"note_id={note_id}", "Unauthorized note deletion attempt", status="Denied")
        return False
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("DELETE FROM research_notes WHERE id = ? AND user_id = ?", (int(note_id), clean_u))
    conn.commit()
    conn.close()
    return True


def get_research_notes(user_id, analysis_id=None, project_id=None):
    """Return research notes strictly filtered by user_id (and optional analysis_id or project_id)."""
    if not user_id:
        return []
    create_users_table()
    clean_u = str(user_id).strip()
    conn = get_db_connection()
    c = conn.cursor()
    query = "SELECT id, user_id, analysis_id, project_id, note_text, created_at, updated_at FROM research_notes WHERE user_id = ?"
    params = [clean_u]
    if analysis_id is not None:
        canonical_aid = _resolve_canonical_analysis_id(analysis_id, clean_u)
        if not canonical_aid:
            conn.close()
            return []
        query += " AND analysis_id = ?"
        params.append(canonical_aid)
    if project_id is not None:
        if not verify_project_ownership(project_id, clean_u):
            conn.close()
            return []
        query += " AND project_id = ?"
        params.append(int(project_id))
    query += " ORDER BY id DESC"
    c.execute(query, params)
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    for r in rows:
        r["note_text"] = _unescape_val(r.get("note_text", ""))
    return rows


# --- Saved Comparisons & Paper Chats ---

def save_comparison_record(user_id, title, paper_ids, matrix_data, synthesis_data=None, project_id=None):
    """Save a multi-paper comparison record owned by user_id."""
    if not user_id:
        return False, "Authentication required.", None
    clean_u = str(user_id).strip()
    for pid in (paper_ids or []):
        if pid and not str(pid).startswith("UPLOAD-") and not verify_analysis_ownership(pid, clean_u):
            return False, "Access Denied: Cannot save comparison referencing another user's paper.", None
    if project_id is not None and not verify_project_ownership(project_id, clean_u):
        return False, "Access Denied: Invalid project ownership.", None

    create_users_table()
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    clean_title = _unescape_val(str(title or "Manuscript Comparison").strip())
    conn = get_db_connection()
    c = conn.cursor()
    c.execute(
        """
        INSERT INTO saved_comparisons (user_id, title, paper_ids_json, matrix_json, synthesis_json, project_id, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            clean_u,
            clean_title,
            json.dumps(list(paper_ids or [])),
            json.dumps(matrix_data or {}),
            json.dumps(synthesis_data or {}),
            int(project_id) if project_id is not None else None,
            now_str,
            now_str,
        ),
    )
    conn.commit()
    comp_id = c.lastrowid
    conn.close()
    log_research_activity(clean_u, "compared", f"Compared manuscripts: {clean_title}", f"{len(paper_ids or [])} papers", project_id=project_id)
    return True, "Comparison saved.", comp_id


def get_user_comparisons(user_id, project_id=None):
    """Fetch saved comparisons strictly owned by user_id."""
    if not user_id:
        return []
    create_users_table()
    clean_u = str(user_id).strip()
    conn = get_db_connection()
    c = conn.cursor()
    query = "SELECT * FROM saved_comparisons WHERE user_id = ?"
    params = [clean_u]
    if project_id is not None:
        query += " AND project_id = ?"
        params.append(int(project_id))
    query += " ORDER BY id DESC"
    c.execute(query, params)
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    for r in rows:
        r["title"] = _unescape_val(r.get("title", ""))
        try:
            r["paper_ids"] = json.loads(r.get("paper_ids_json") or "[]")
        except Exception:
            r["paper_ids"] = []
        try:
            parsed_m = json.loads(r.get("matrix_json") or "{}")
            r["matrix"] = parsed_m
            r["matrix_json"] = parsed_m
        except Exception:
            r["matrix"] = {}
            r["matrix_json"] = {}
        try:
            r["synthesis"] = json.loads(r.get("synthesis_json") or "{}")
        except Exception:
            r["synthesis"] = {}
    return rows


def delete_comparison_record(arg1, arg2):
    """Delete a saved comparison strictly owned by user_id."""
    comp_id, user_id = _swap_if_user_first(arg1, arg2)
    clean_u = str(user_id or "").strip()
    if not verify_comparison_ownership(comp_id, clean_u):
        record_audit_event(clean_u or "unknown", "UNAUTHORIZED_ACCESS", f"comp_id={comp_id}", "Unauthorized comparison delete attempt", status="Denied")
        return False
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("DELETE FROM saved_comparisons WHERE id = ? AND user_id = ?", (int(comp_id), clean_u))
    conn.commit()
    conn.close()
    return True


def save_paper_chat_turn(user_id=None, scope_key="", question="", answer="", evidence=None, citations=None, analysis_id=None, username=None):
    """Save a question/answer turn in Ask PaperIQ strictly scoped to user_id and scope_key."""
    u = username or user_id
    if not u or not scope_key:
        return None
    create_users_table()
    clean_u = str(u).strip()
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    ev_list = citations if citations is not None else (evidence or [])
    conn = get_db_connection()
    c = conn.cursor()
    c.execute(
        """
        INSERT INTO paper_chats (user_id, scope_key, question, answer, evidence_json, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            clean_u,
            str(scope_key),
            _unescape_val(str(question)),
            _unescape_val(str(answer)),
            json.dumps(ev_list),
            now_str,
            now_str,
        ),
    )
    conn.commit()
    chat_id = c.lastrowid
    conn.close()
    return chat_id


def get_paper_chat_history(user_id, scope_key):
    """Retrieve Ask PaperIQ chat turns strictly for (user_id, scope_key)."""
    if not user_id or not scope_key:
        return []
    create_users_table()
    clean_u = str(user_id).strip()
    conn = get_db_connection()
    c = conn.cursor()
    c.execute(
        "SELECT id, user_id, scope_key, question, answer, evidence_json, created_at FROM paper_chats WHERE user_id = ? AND scope_key = ? ORDER BY id ASC",
        (clean_u, str(scope_key)),
    )
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    for r in rows:
        r["question"] = _unescape_val(r.get("question", ""))
        r["answer"] = _unescape_val(r.get("answer", ""))
        try:
            ev = json.loads(r.get("evidence_json") or "[]")
            r["evidence"] = ev
            r["citations"] = ev
        except Exception:
            r["evidence"] = []
            r["citations"] = []
    return rows


def clear_paper_chat_history(user_id, scope_key):
    """Clear Ask PaperIQ chat turns for (user_id, scope_key)."""
    if not user_id or not scope_key:
        return False
    clean_u = str(user_id).strip()
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("DELETE FROM paper_chats WHERE user_id = ? AND scope_key = ?", (clean_u, str(scope_key)))
    conn.commit()
    conn.close()
    return True


def get_single_analysis_for_user(arg1, arg2):
    """Strictly fetch a single analysis record only if owned by user_id (guards against ID tampering)."""
    record_or_analysis_id, user_id = _swap_if_user_first(arg1, arg2)
    clean_u = str(user_id or "").strip()
    if not clean_u or not verify_analysis_ownership(record_or_analysis_id, clean_u):
        if clean_u and record_or_analysis_id:
            record_audit_event(clean_u, "UNAUTHORIZED_ACCESS", f"analysis_id={record_or_analysis_id}", "ID tampering or cross-account read blocked", status="Denied")
        return None
    for item in get_researcher_library(clean_u):
        if str(item.get("id")) == str(record_or_analysis_id) or str(item.get("analysis_id")) == str(record_or_analysis_id):
            return item
    return None


_BACKFILL_COMPLETED = False


class _RefreshResult(dict):
    """Hybrid return type supporting both dict access (.get('ok'), .get('title')) and 3-tuple unpacking (ok, msg, meta)."""

    def __iter__(self):
        yield bool(self.get("ok", False))
        yield str(self.get("message", ""))
        yield self.get("meta")


def refresh_paper_metadata(arg1, arg2):
    """
    TASK 2 & 3 — Re-derive canonical title, authors, venue/journal, year, keywords,
    research profile, real sections (excluding Preamble/Keywords), 5 distinct
    Researcher Manuscript Quality scores, and normalized summary limitation labels
    for an existing analysis record owned by user_id.
    Supports both `res.get("ok")` dict access and `ok, msg, meta = refresh_paper_metadata(...)`.
    """
    record_or_analysis_id, user_id = _swap_if_user_first(arg1, arg2)
    clean_u = str(user_id or "").strip()
    if not clean_u or not verify_analysis_ownership(record_or_analysis_id, clean_u):
        return _RefreshResult(
            ok=False,
            message="Access Denied: You can only refresh metadata for your own papers.",
            meta=None,
        )

    canonical_aid = _resolve_canonical_analysis_id(record_or_analysis_id, clean_u)
    if not canonical_aid:
        return _RefreshResult(ok=False, message="Analysis record not found.", meta=None)

    conn = get_db_connection()
    c = conn.cursor()
    c.execute(
        "SELECT id, analysis_id, filename, original_filename, display_title, domain, score, results_json FROM analysis_history WHERE analysis_id = ? AND username = ?",
        (canonical_aid, clean_u),
    )
    row = c.fetchone()
    if not row:
        conn.close()
        return _RefreshResult(ok=False, message="Analysis record not found.", meta=None)

    res_obj = {}
    if row["results_json"]:
        try:
            res_obj = json.loads(row["results_json"])
        except Exception:
            res_obj = {}

    extracted_txt = _unescape_val(res_obj.get("extracted_text") or res_obj.get("full_text") or "")
    if not extracted_txt or len(extracted_txt.strip()) < 40:
        conn.close()
        return _RefreshResult(
            ok=False,
            message="Stored extracted text is not available for this record. Please re-upload the manuscript file to re-derive metadata.",
            meta=None,
        )

    import research_engine
    import summarizer

    fn = row["original_filename"] or row["filename"] or "document.pdf"
    cleaned_txt = summarizer.clean_extracted_text(extracted_txt)
    sections_map = summarizer.segment_paper_sections(cleaned_txt)
    auto_meta = research_engine.extract_paper_metadata(extracted_txt, filename=fn)
    profile = research_engine.extract_research_profile(cleaned_txt, sections_map)
    q_scores = research_engine.compute_researcher_quality_scores(cleaned_txt, sections_map, base_res=res_obj)
    counts = summarizer.compute_text_counts(cleaned_txt)
    findings = research_engine.generate_text_grounded_findings(
        cleaned_txt,
        sections_map,
        {"word_count": counts["word_count"], "sentence_count": counts["sentence_count"]},
        q_scores,
        profile=profile,
    )

    # Normalize stored summary limitation labels (Task 3)
    cur_summary = str(res_obj.get("summary") or "")
    if cur_summary:
        cur_summary = summarizer.normalize_summary_limitations_label(cur_summary)

    metrics_map = res_obj.get("metrics") if isinstance(res_obj.get("metrics"), dict) else {}
    metrics_map.update({
        "research_profile": profile,
        "keyword_details": auto_meta.get("keyword_details", []),
        "themes": auto_meta.get("themes", []),
        "grounded_findings": findings,
        "word_count": counts["word_count"],
        "sentence_count": counts["sentence_count"],
        "citation_count": q_scores["citation_count"],
        "in_text_citation_count": q_scores["in_text_citation_count"],
        "reference_list_count": q_scores["reference_list_count"],
        "unique_citation_markers": q_scores["unique_citation_markers"],
        "driven_by": q_scores["driven_by"],
    })

    res_obj.update({
        "title": auto_meta["title"],
        "paper_title": auto_meta["title"],
        "display_title": auto_meta["title"],
        "authors": auto_meta["authors"],
        "year": auto_meta["year"],
        "journal": auto_meta["journal"],
        "domain": auto_meta["domain"],
        "keywords": auto_meta["keywords"],
        "topics": auto_meta["topics"],
        "sections": sections_map,
        "metrics": metrics_map,
        "summary": cur_summary,
        "overall_score": q_scores["overall_score"],
        "structure_score": q_scores["structure_score"],
        "clarity_score": q_scores["clarity_score"],
        "coherence_score": q_scores["coherence_score"],
        "citation_score": q_scores["citation_score"],
        "readability_score": q_scores["readability_score"],
        "metadata_migration_v2": True,
    })

    c.execute(
        """
        UPDATE analysis_history
        SET display_title = ?, domain = ?, score = ?,
            coherence_score = ?, language_score = ?, argumentation_score = ?,
            academic_style_score = ?, readability_score = ?, results_json = ?
        WHERE id = ? AND username = ?
        """,
        (
            auto_meta["title"],
            auto_meta["domain"],
            float(q_scores["overall_score"]),
            float(q_scores["structure_score"]),
            float(q_scores["clarity_score"]),
            float(q_scores["coherence_score"]),
            float(q_scores["citation_score"]),
            float(q_scores["readability_score"]),
            json.dumps(res_obj),
            row["id"],
            clean_u,
        ),
    )
    conn.commit()
    conn.close()

    upsert_paper_metadata(
        analysis_id=canonical_aid,
        user_id=clean_u,
        title=auto_meta["title"],
        authors=auto_meta["authors"],
        year=auto_meta["year"],
        journal=auto_meta["journal"],
        keywords=auto_meta["keywords"],
        topics=auto_meta["topics"],
        domain=auto_meta["domain"],
        research_profile=profile,
    )

    return _RefreshResult(
        ok=True,
        message=f"Metadata refreshed: '{auto_meta['title']}'",
        title=auto_meta["title"],
        authors=auto_meta["authors"],
        year=auto_meta["year"],
        journal=auto_meta["journal"],
        domain=auto_meta["domain"],
        meta=auto_meta,
    )


def backfill_existing_researcher_records(force: bool = False) -> int:
    """
    TASK 2 & 3 — One-time idempotent migration (with non-destructive DB backup) that re-derives
    canonical title, authors, venue, sections, research profile, 5 distinct quality scores, and
    summary limitation labels for stored papers where the title looks like a byline (matches
    the author pattern or ends with a comma) or citation line.
    """
    global _BACKFILL_COMPLETED
    if _BACKFILL_COMPLETED and not force:
        return 0
    _BACKFILL_COMPLETED = True

    try:
        import shutil
        import research_engine
        if os.path.exists(DB_PATH):
            os.makedirs("backups", exist_ok=True)
            backup_path = os.path.join("backups", "users_pre_byline_migration.db")
            if not os.path.exists(backup_path):
                shutil.copy2(DB_PATH, backup_path)
        conn = get_db_connection()
        c = conn.cursor()
        c.execute("SELECT id, analysis_id, username, display_title, results_json FROM analysis_history")
        rows = c.fetchall()
        conn.close()
    except Exception:
        return 0

    updated_count = 0
    for r in rows:
        uid = r["username"]
        aid = r["analysis_id"] or r["id"]
        if not uid or not r["results_json"]:
            continue
        try:
            res_obj = json.loads(r["results_json"])
        except Exception:
            continue
        ext_txt = res_obj.get("extracted_text") or res_obj.get("full_text") or ""
        if not ext_txt or len(ext_txt.strip()) < 40:
            continue

        cur_title = str(r["display_title"] or res_obj.get("title") or "").strip()
        cur_authors = str(res_obj.get("authors") or "").strip()
        cur_summary = str(res_obj.get("summary") or "")
        secs = res_obj.get("sections") or {}
        metrics = res_obj.get("metrics") or {}
        s_vals = {
            round(float(res_obj.get("structure_score") or 0), 1),
            round(float(res_obj.get("clarity_score") or 0), 1),
            round(float(res_obj.get("coherence_score") or 0), 1),
            round(float(res_obj.get("citation_score") or 0), 1),
            round(float(res_obj.get("readability_score") or 0), 1),
        }
        needs_refresh = (
            force
            or cur_title.endswith(",")
            or research_engine.is_author_byline(cur_title)
            or research_engine.is_citation_or_header_line(cur_title)
            or (
                cur_title.lower() == "growth performance of nutri-cereals in india"
                and "gangadharan" in ext_txt.lower()
                and cur_authors != "Gangadharan S., Abhinav Pillai, S. Aravind"
            )
            or "Possible limitations mentioned" in cur_summary
            or "Preamble" in secs
            or any(k.lower().startswith("keyword") for k in secs.keys())
            or cur_authors in ("Unknown Authors", "S. Aravind")
            or (
                not res_obj.get("metadata_migration_v2")
                and (
                    len(s_vals) <= 1
                    or "driven_by" not in metrics
                    or not cur_authors
                    or res_obj.get("journal") in (None, "", "Manuscript / Preprint")
                )
            )
        )
        if needs_refresh:
            ok, _, _ = refresh_paper_metadata(aid, uid)
            if ok:
                updated_count += 1

    return updated_count


def get_researcher_library(user_id):
    """
    Return all analyzed papers owned by user_id, enriched with:
    - paper_metadata (title, authors, year, journal, keywords, topics, domain, research_profile)
    - projects (list of {id, name})
    - tags (list of tag strings)
    - notes (list of note dicts)
    - 5 distinct Researcher Manuscript Quality scores & driven_by telemetry
    Strictly filtered by user_id across all joined tables.
    """
    if not user_id:
        return []
    backfill_existing_researcher_records()
    clean_u = str(user_id).strip()
    base_history = get_user_history(clean_u)
    user_projects = {p["id"]: p["name"] for p in get_user_projects(clean_u)}

    conn = get_db_connection()
    c = conn.cursor()

    enriched = []
    for item in base_history:
        aid = item.get("analysis_id") or f"ANL-{item.get('id')}"
        res_obj = {}
        if item.get("results_json"):
            try:
                res_obj = json.loads(item["results_json"])
            except Exception:
                res_obj = {}

        meta = get_paper_metadata(aid, clean_u) or {}
        tags = get_paper_tags(aid, clean_u)
        notes = get_research_notes(clean_u, analysis_id=aid)

        c.execute(
            "SELECT project_id FROM project_papers WHERE analysis_id = ? AND user_id = ?",
            (aid, clean_u),
        )
        proj_ids = [r["project_id"] for r in c.fetchall() if r["project_id"] in user_projects]
        proj_list = [{"id": pid, "name": user_projects[pid]} for pid in proj_ids]

        title = (
            meta.get("title")
            or item.get("display_title")
            or res_obj.get("title")
            or res_obj.get("paper_title")
            or res_obj.get("display_title")
            or item.get("filename")
            or "Untitled Manuscript"
        )
        authors = meta.get("authors") or res_obj.get("authors") or "Not found"
        year = meta.get("year") or res_obj.get("year") or ""
        journal = meta.get("journal") or res_obj.get("journal") or res_obj.get("publisher") or "Manuscript / Preprint"
        domain = meta.get("domain") or item.get("domain") or res_obj.get("domain") or "Interdisciplinary"
        keywords = meta.get("keywords") or res_obj.get("keywords") or []
        topics = meta.get("topics") or res_obj.get("topics") or res_obj.get("domains") or ([domain] if domain else [])
        profile = meta.get("research_profile") or res_obj.get("research_profile") or (res_obj.get("metrics") or {}).get("research_profile") or {}

        overall_sc = float(res_obj.get("overall_score") or item.get("score") or 0.0)
        struct_sc = float(res_obj.get("structure_score") or item.get("coherence_score") or overall_sc)
        clar_sc = float(res_obj.get("clarity_score") or item.get("language_score") or overall_sc)
        coh_sc = float(res_obj.get("coherence_score") or item.get("argumentation_score") or overall_sc)
        cit_sc = float(res_obj.get("citation_score") or item.get("academic_style_score") or overall_sc)
        read_sc = float(res_obj.get("readability_score") or item.get("readability_score") or overall_sc)

        extracted_txt = res_obj.get("extracted_text") or res_obj.get("full_text") or ""
        summary_txt = res_obj.get("summary") or ""
        sections_map = res_obj.get("sections") if isinstance(res_obj.get("sections"), dict) else {}
        metrics_map = res_obj.get("metrics") if isinstance(res_obj.get("metrics"), dict) else {}
        if profile and "research_profile" not in metrics_map:
            metrics_map["research_profile"] = profile

        enriched_item = dict(item)
        enriched_item.update({
            "analysis_id": aid,
            "title": _unescape_val(title),
            "paper_title": _unescape_val(title),
            "display_title": _unescape_val(title),
            "authors": _unescape_val(authors),
            "year": _unescape_val(str(year)),
            "journal": _unescape_val(journal),
            "domain": _unescape_val(domain),
            "keywords": [_unescape_val(str(k)) for k in keywords],
            "topics": [_unescape_val(str(t)) for t in topics],
            "research_profile": profile,
            "extracted_text": _unescape_val(extracted_txt),
            "summary": _unescape_val(summary_txt),
            "sections": sections_map,
            "metrics": metrics_map,
            "overall_score": overall_sc,
            "structure_score": struct_sc,
            "clarity_score": clar_sc,
            "coherence_score": coh_sc,
            "citation_score": cit_sc,
            "readability_score": read_sc,
            "timestamp": item.get("created_at") or "",
            "projects": proj_list,
            "project_ids": proj_ids,
            "project_names": [p["name"] for p in proj_list],
            "tags": tags,
            "notes": notes,
            "results_dict": res_obj,
        })
        enriched.append(enriched_item)

    conn.close()
    return enriched


def export_researcher_data_json(user_id):
    """Export all researcher-owned data (profile, projects, papers metadata, notes, tags, comparisons) as dict."""
    if not user_id:
        return {}
    clean_u = str(user_id).strip()
    lib = get_researcher_library(clean_u)
    export_papers = []
    for p in lib:
        p_copy = {k: v for k, v in p.items() if k not in ("pdf", "results_json")}
        export_papers.append(p_copy)
    payload = {
        "user_id": clean_u,
        "exported_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "projects": get_user_projects(clean_u),
        "papers": export_papers,
        "tags": get_user_tags(clean_u),
        "notes": get_research_notes(clean_u),
        "comparisons": get_user_comparisons(clean_u),
        "activity_log": get_research_activity(clean_u, limit=100),
    }
    return payload


def delete_all_researcher_data(user_id):
    """Delete all papers, projects, metadata, tags, notes, comparisons, chats, and activity logs for user_id."""
    if not user_id:
        return False, "Authentication required."
    clean_u = str(user_id).strip()
    create_users_table()
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("DELETE FROM project_papers WHERE user_id = ?", (clean_u,))
    c.execute("DELETE FROM projects WHERE user_id = ?", (clean_u,))
    c.execute("DELETE FROM paper_metadata WHERE user_id = ?", (clean_u,))
    c.execute("DELETE FROM paper_tags WHERE user_id = ?", (clean_u,))
    c.execute("DELETE FROM tags WHERE user_id = ?", (clean_u,))
    c.execute("DELETE FROM research_notes WHERE user_id = ?", (clean_u,))
    c.execute("DELETE FROM saved_comparisons WHERE user_id = ?", (clean_u,))
    c.execute("DELETE FROM paper_chats WHERE user_id = ?", (clean_u,))
    c.execute("DELETE FROM activity_log WHERE user_id = ?", (clean_u,))
    c.execute("DELETE FROM analysis_history WHERE username = ?", (clean_u,))
    conn.commit()
    conn.close()
    return True, "All researcher library papers, projects, metadata, notes, comparisons, and chats have been permanently deleted."


if __name__ == "__main__":
    if len(sys.argv) >= 4 and sys.argv[1] == "provision-admin":
        success, msg = provision_admin(sys.argv[2], sys.argv[3])
        print(msg)
        sys.exit(0 if success else 1)
    else:
        create_users_table()
        backfill_existing_researcher_records(force=True)
        print("PaperIQ Database initialized with tables, schema migrations, and audit security.")


