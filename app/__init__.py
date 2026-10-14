from flask import Flask, render_template, request, redirect, url_for, session
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3
import os
import boto3
from datetime import datetime
from botocore.exceptions import ClientError
from app.note_parser import parse_note
from app.llm_parser import parse_note_with_llm

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "dev-secret-key-change-in-production")

DB_PATH = os.environ.get("DB_PATH", "shiftmanager.db")
SES_REGION = os.environ.get("SES_REGION", "us-east-1")
SES_FROM = os.environ.get("SES_FROM", "gillisw@cua.edu")
SES_ENABLED = os.environ.get("SES_ENABLED", "1") != "0"

ses_client = boto3.client("ses", region_name=SES_REGION) if SES_ENABLED else None


def get_db():
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    return db


def log_action(action, detail=""):
    """Write an entry to the audit log."""
    uid = session.get("user_id")
    db = get_db()
    db.execute(
        "INSERT INTO audit_log (user_id, action, detail, created_at) VALUES (?, ?, ?, ?)",
        (uid, action, detail, datetime.now().strftime("%Y-%m-%d %H:%M")),
    )
    db.commit()
    db.close()


def init_db():
    db = get_db()
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            display_name TEXT NOT NULL,
            role TEXT DEFAULT 'manager',
            email TEXT
        )
        """
    )
    db.execute(
        """
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
        """
    )
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS employees (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT,
            role TEXT DEFAULT 'officer',
            unavailable_days TEXT DEFAULT ''
        )
        """
    )
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            action TEXT NOT NULL,
            detail TEXT,
            created_at TEXT NOT NULL
        )
        """
    )
    count = db.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    if count == 0:
        db.execute(
            "INSERT INTO users (username, password_hash, display_name, role, email) VALUES (?, ?, ?, ?, ?)",
            ("admin", generate_password_hash("admin"), "Admin", "manager", "gillisw@cua.edu"),
        )
    emp_count = db.execute("SELECT COUNT(*) FROM employees").fetchone()[0]
    if emp_count == 0:
        db.executemany(
            "INSERT INTO employees (name, email, role, unavailable_days) VALUES (?, ?, ?, ?)",
            [
                ("Mike Rodriguez", "23wgillis@gmail.com", "officer", ""),
                ("Sarah Chen", "23wgillis@gmail.com", "officer", "monday"),
                ("James O'Brien", "23wgillis@gmail.com", "officer", ""),
                ("Maria Santos", "23wgillis@gmail.com", "supervisor", ""),
                ("Tony Walker", "23wgillis@gmail.com", "officer", "friday"),
                ("Priya Patel", "23wgillis@gmail.com", "officer", ""),
            ],
        )
    db.commit()
    db.close()


def send_swap_notification(assigned_name, assigned_email, note_body, manager_name):
    if not ses_client or not assigned_email:
        return False
    subject = f"Shift Coverage Assignment - {assigned_name}"
    body = (
        f"Hi {assigned_name},\n\n"
        f"{manager_name} has assigned you to cover a shift.\n\n"
        f"Details:\n"
        f"  Note: {note_body}\n\n"
        f"Please confirm you can cover this shift.\n\n"
        f"- AI Shift Manager\n"
        f"CUA Busch School AI Vibe Coding Contest, Fall 2026"
    )
    try:
        ses_client.send_email(
            Source=SES_FROM,
            Destination={"ToAddresses": [assigned_email]},
            Message={
                "Subject": {"Data": subject},
                "Body": {"Text": {"Data": body}},
            },
        )
        return True
    except ClientError:
        return False


@app.route("/")
def index():
    if "user_id" not in session:
        return redirect(url_for("login"))
    db = get_db()
    user = db.execute("SELECT * FROM users WHERE id = ?", (session["user_id"],)).fetchone()
    notes = db.execute(
        "SELECT * FROM notes WHERE user_id = ? ORDER BY created_at DESC", (session["user_id"],)
    ).fetchall()
    all_employees = db.execute("SELECT * FROM employees ORDER BY name").fetchall()

    # Build a dict of available employees per open note
    available_employees = {}
    for note in notes:
        if note["status"] == "open":
            available_employees[note["id"]] = filter_available_employees(all_employees, note["parsed_when"])
        else:
            available_employees[note["id"]] = all_employees

    db.close()
    return render_template("index.html", user=user, notes=notes, all_employees=all_employees, available_employees=available_employees)


@app.route("/availability", methods=["GET", "POST"])
def availability():
    if "user_id" not in session:
        return redirect(url_for("login"))
    db = get_db()
    if request.method == "POST":
        action = request.form.get("action", "")
        if action == "save_availability":
            for emp in db.execute("SELECT * FROM employees").fetchall():
                days = request.form.get(f"days_{emp['id']}", "").strip().lower()
                db.execute("UPDATE employees SET unavailable_days = ? WHERE id = ?", (days, emp["id"]))
            db.commit()
        elif action == "add_employee":
            name = request.form.get("emp_name", "").strip()
            email = request.form.get("emp_email", "").strip()
            role = request.form.get("emp_role", "officer").strip() or "officer"
            if name:
                db.execute("INSERT INTO employees (name, email, role, unavailable_days) VALUES (?, ?, ?, '')", (name, email, role))
            db.commit()
        elif action == "delete_employee":
            emp_id = request.form.get("emp_id", "")
            if emp_id:
                db.execute("DELETE FROM employees WHERE id = ?", (emp_id,))
            db.commit()
        db.close()
        return redirect(url_for("availability"))
    employees = db.execute("SELECT * FROM employees ORDER BY name").fetchall()
    db.close()
    return render_template("availability.html", employees=employees)


def filter_available_employees(employees, parsed_when):
    """Filter out employees whose unavailable_days match the parsed day."""
    if not parsed_when or parsed_when == "unspecified":
        return employees
    day_keywords = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday",
                    "today", "tomorrow", "tonight"]
    matched_days = [d for d in day_keywords if d in parsed_when.lower()]
    if not matched_days:
        return employees
    available = []
    for emp in employees:
        unavail = (emp["unavailable_days"] or "").lower()
        if not any(day in unavail for day in matched_days):
            available.append(emp)
    return available


@app.route("/dashboard")
def dashboard():
    if "user_id" not in session:
        return redirect(url_for("login"))
    db = get_db()
    user = db.execute("SELECT * FROM users WHERE id = ?", (session["user_id"],)).fetchone()
    notes = db.execute("SELECT * FROM notes WHERE user_id = ? ORDER BY created_at DESC", (session["user_id"],)).fetchall()
    employees = db.execute("SELECT * FROM employees").fetchall()

    total_notes = len(notes)
    open_notes = sum(1 for n in notes if n["status"] == "open")
    approved_notes = sum(1 for n in notes if n["status"] == "approved")

    # Urgency breakdown
    urgency_high = sum(1 for n in notes if n["parsed_urgency"] == "high")
    urgency_medium = sum(1 for n in notes if n["parsed_urgency"] == "medium")
    urgency_low = sum(1 for n in notes if n["parsed_urgency"] == "low")

    # Reason breakdown
    reasons = {}
    for n in notes:
        reason = n["parsed_what"] or "unspecified"
        reasons[reason] = reasons.get(reason, 0) + 1

    # Most assigned employees
    assignments = {}
    for n in notes:
        if n["assigned_to"]:
            assignments[n["assigned_to"]] = assignments.get(n["assigned_to"], 0) + 1

    db.close()
    return render_template("dashboard.html", user=user, total_notes=total_notes, open_notes=open_notes,
                           approved_notes=approved_notes, urgency_high=urgency_high,
                           urgency_medium=urgency_medium, urgency_low=urgency_low,
                           reasons=reasons, assignments=assignments,
                           total_employees=len(employees))


@app.route("/audit")
def audit():
    if "user_id" not in session:
        return redirect(url_for("login"))
    db = get_db()
    user = db.execute("SELECT * FROM users WHERE id = ?", (session["user_id"],)).fetchone()
    logs = db.execute("SELECT * FROM audit_log ORDER BY created_at DESC LIMIT 50").fetchall()
    db.close()
    return render_template("audit.html", user=user, logs=logs)


@app.route("/export/csv")
def export_csv():
    if "user_id" not in session:
        return redirect(url_for("login"))
    db = get_db()
    notes = db.execute(
        "SELECT * FROM notes WHERE user_id = ? ORDER BY created_at DESC", (session["user_id"],)
    ).fetchall()
    db.close()

    import io
    import csv
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["ID", "Body", "Status", "Assigned To", "Who", "What", "When", "Urgency", "Created At", "Approved At"])
    for n in notes:
        writer.writerow([
            n["id"], n["body"], n["status"], n["assigned_to"] or "",
            n["parsed_who"] or "", n["parsed_what"] or "", n["parsed_when"] or "",
            n["parsed_urgency"] or "", n["created_at"], n["approved_at"] or ""
        ])

    from flask import Response
    log_action("csv_exported", f"{len(notes)} notes")
    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=shift_notes_export.csv"}
    )


@app.route("/add-note", methods=["POST"])
def add_note():
    if "user_id" not in session:
        return redirect(url_for("login"))
    body = request.form.get("body", "").strip()
    if body:
        db = get_db()
        employees = db.execute("SELECT * FROM employees").fetchall()
        emp_names = [e["name"] for e in employees]

        # Try LLM parser first, fall back to regex
        parsed = parse_note_with_llm(body, emp_names)
        if parsed is None:
            parsed = parse_note(body)

        # Match who against employee names if LLM didn't find a match
        if not parsed.get("who"):
            body_lower = body.lower()
            for emp in employees:
                first_name = emp["name"].split()[0].lower()
                if first_name in body_lower:
                    parsed["who"] = emp["name"]
                    break

        db.execute(
            "INSERT INTO notes (user_id, body, status, parsed_who, parsed_what, parsed_when, parsed_urgency, created_at) VALUES (?, ?, 'open', ?, ?, ?, ?, ?)",
            (session["user_id"], body, parsed["who"], parsed["what"], parsed["when"], parsed["urgency"], datetime.now().strftime("%Y-%m-%d %H:%M")),
        )
        db.commit()
        db.close()
        log_action("note_created", body[:100])
    return redirect(url_for("index"))


@app.route("/approve/<int:note_id>", methods=["POST"])
def approve_note(note_id):
    if "user_id" not in session:
        return redirect(url_for("login"))
    assigned_to = request.form.get("assigned_to", "").strip()
    if assigned_to:
        db = get_db()
        note = db.execute(
            "SELECT * FROM notes WHERE id = ? AND user_id = ?", (note_id, session["user_id"])
        ).fetchone()
        if note and note["status"] == "open":
            db.execute(
                "UPDATE notes SET status = 'approved', assigned_to = ?, approved_at = ? WHERE id = ?",
                (assigned_to, datetime.now().strftime("%Y-%m-%d %H:%M"), note_id),
            )
            db.commit()

            # Look up employee email
            emp = db.execute(
                "SELECT * FROM employees WHERE name = ?", (assigned_to,)
            ).fetchone()
            user = db.execute(
                "SELECT * FROM users WHERE id = ?", (session["user_id"],)
            ).fetchone()
            db.close()

            # Send email notification
            emp_email = emp["email"] if emp else None
            manager_name = user["display_name"] if user else "Manager"
            sent = send_swap_notification(assigned_to, emp_email, note["body"], manager_name)
            session["email_sent"] = sent
            log_action("swap_approved", f"Note #{note_id} assigned to {assigned_to}, email sent: {sent}")
        else:
            db.close()
    return redirect(url_for("index"))


@app.route("/login", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        db = get_db()
        user = db.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
        db.close()
        if user and check_password_hash(user["password_hash"], password):
            session["user_id"] = user["id"]
            return redirect(url_for("index"))
        error = "Invalid username or password."
    return render_template("login.html", error=error)


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


if __name__ == "__main__":
    init_db()
    app.run(debug=True, port=5000)
