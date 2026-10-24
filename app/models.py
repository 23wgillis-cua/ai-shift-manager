"""Database layer: schema, connection helper, initialization, and migration."""
import sqlite3
import os
from werkzeug.security import generate_password_hash
from datetime import datetime

DB_PATH = os.environ.get("DB_PATH", "shiftmanager.db")


def get_db():
    """Get a SQLite connection with Row factory and thread safety."""
    db = sqlite3.connect(DB_PATH, check_same_thread=False)
    db.row_factory = sqlite3.Row
    return db


def init_db():
    """Create tables if needed and seed initial data on a fresh database.

    On existing databases, runs lightweight migrations: ensures the demo
    account exists, rotates the admin password from the environment variable,
    and normalizes employee contact info to demo values.
    """
    db = get_db()

    # --- Schema ---
    db.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            display_name TEXT NOT NULL,
            role TEXT DEFAULT 'manager',
            email TEXT
        )
    """)
    db.execute("""
        CREATE TABLE IF NOT EXISTS notes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            body TEXT NOT NULL,
            status TEXT DEFAULT 'open',
            assigned_to TEXT,
            parsed_who TEXT,
            parsed_what TEXT,
            parsed_when TEXT,
            parsed_urgency TEXT DEFAULT 'low',
            created_at TEXT NOT NULL,
            approved_at TEXT,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    """)
    db.execute("""
        CREATE TABLE IF NOT EXISTS employees (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT,
            phone TEXT,
            role TEXT DEFAULT 'officer',
            unavailable_days TEXT DEFAULT ''
        )
    """)
    db.execute("""
        CREATE TABLE IF NOT EXISTS audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            action TEXT NOT NULL,
            detail TEXT,
            created_at TEXT NOT NULL
        )
    """)
    db.execute("""
        CREATE TABLE IF NOT EXISTS shift_templates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            day_pattern TEXT NOT NULL,
            start_time TEXT,
            end_time TEXT,
            required_officers INTEGER DEFAULT 2,
            created_at TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    """)

    # --- Seed or migrate ---
    user_count = db.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    if user_count == 0:
        db.execute(
            "INSERT INTO users (username, password_hash, display_name, role, email) VALUES (?, ?, ?, ?, ?)",
            ("demo", generate_password_hash("demo"), "Demo Manager", "demo", None),
        )
        admin_pass = os.environ.get("ADMIN_PASSWORD", "ChangeMeInProduction_2026!")
        db.execute(
            "INSERT INTO users (username, password_hash, display_name, role, email) VALUES (?, ?, ?, ?, ?)",
            ("admin", generate_password_hash(admin_pass), "Admin", "manager", "gillisw@cua.edu"),
        )
    else:
        admin_pass = os.environ.get("ADMIN_PASSWORD", "ChangeMeInProduction_2026!")
        demo_user = db.execute("SELECT * FROM users WHERE username = 'demo'").fetchone()
        if not demo_user:
            db.execute(
                "INSERT INTO users (username, password_hash, display_name, role, email) VALUES (?, ?, ?, ?, ?)",
                ("demo", generate_password_hash("demo"), "Demo Manager", "demo", None),
            )
        db.execute(
            "UPDATE users SET password_hash = ? WHERE username = 'admin'",
            (generate_password_hash(admin_pass),),
        )

    emp_count = db.execute("SELECT COUNT(*) FROM employees").fetchone()[0]
    if emp_count == 0:
        db.executemany(
            "INSERT INTO employees (name, email, phone, role, unavailable_days) VALUES (?, ?, ?, ?, ?)",
            [
                ("Mike Rodriguez", "demo@example.com", "555-0100", "officer", ""),
                ("Sarah Chen", "demo@example.com", "555-0101", "officer", "monday"),
                ("James O'Brien", "demo@example.com", "555-0102", "officer", ""),
                ("Maria Santos", "demo@example.com", "555-0103", "supervisor", ""),
                ("Tony Walker", "demo@example.com", "555-0104", "officer", "friday"),
                ("Priya Patel", "demo@example.com", "555-0105", "officer", ""),
            ],
        )
    else:
        db.execute(
            "UPDATE employees SET email = 'demo@example.com' "
            "WHERE email IS NOT NULL AND email != 'demo@example.com'"
        )
        db.execute(
            "UPDATE employees SET phone = '555-010' || CAST(id AS TEXT) "
            "WHERE phone IS NULL OR phone = ''"
        )

    # --- Seed demo notes for a fresh DB so judges see a populated app ---
    if user_count == 0:
        demo_user_id = db.execute(
            "SELECT id FROM users WHERE username = 'demo'"
        ).fetchone()[0]
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        demo_notes = [
            (demo_user_id, "Mike has a funeral Wednesday and can't come to work",
             "approved", "Mike Rodriguez", "Mike Rodriguez", "funeral", "wednesday", "medium", now, now),
            (demo_user_id, "Sarah called out sick with the flu today",
             "approved", "Sarah Chen", "Sarah Chen", "sick", "today", "high", now, now),
            (demo_user_id, "Tony has a dentist appointment Friday morning",
             "open", "Tony Walker", "Tony Walker", "appointment", "friday", "medium", now, None),
            (demo_user_id, "Priya needs to cover for a family emergency this evening",
             "open", "Priya Patel", "Priya Patel", "family", "today", "high", now, None),
            (demo_user_id, "James is on vacation next Tuesday",
             "open", "James O'Brien", "James O'Brien", "vacation", "tuesday", "low", now, None),
            (demo_user_id, "Maria has a medical appointment Wednesday afternoon",
             "approved", "Maria Santos", "Maria Santos", "appointment", "wednesday", "low", now, now),
        ]
        db.executemany(
            "INSERT INTO notes (user_id, body, status, assigned_to, parsed_who, "
            "parsed_what, parsed_when, parsed_urgency, created_at, approved_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            demo_notes,
        )
        # Seed audit log entries for the demo notes
        db.executemany(
            "INSERT INTO audit_log (user_id, action, detail, created_at) VALUES (?, ?, ?, ?)",
            [
                (demo_user_id, "note_created", "Mike has a funeral Wednesday...", now),
                (demo_user_id, "swap_approved", "Note #1 assigned to James O'Brien, email logged (demo account - not sent)", now),
                (demo_user_id, "note_created", "Sarah called out sick with the flu...", now),
                (demo_user_id, "swap_approved", "Note #2 assigned to Priya Patel, email logged (demo account - not sent)", now),
                (demo_user_id, "note_created", "Tony has a dentist appointment...", now),
                (demo_user_id, "note_created", "Priya needs to cover for a family emergency...", now),
                (demo_user_id, "note_created", "James is on vacation next Tuesday", now),
                (demo_user_id, "note_created", "Maria has a medical appointment...", now),
                (demo_user_id, "swap_approved", "Note #6 assigned to Mike Rodriguez, email logged (demo account - not sent)", now),
            ],
        )

    db.commit()
    db.close()
