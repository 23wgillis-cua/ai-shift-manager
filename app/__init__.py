"""AI Shift Manager - Flask application routes.

Routes are organized by feature area. Database layer lives in models.py,
notifications (SES/SNS) in notifications.py, AI parsing in note_parser.py
and llm_parser.py.
"""
from flask import (
    Flask, render_template, request, redirect, url_for, session, Response
)
from werkzeug.security import generate_password_hash, check_password_hash
import os
from datetime import datetime, date, timedelta
import io
import csv
import re

from app.models import get_db, init_db, DB_PATH
import app.models as models_module
from app.notifications import send_swap_notification, send_swap_sms
from app.note_parser import parse_note
from app.llm_parser import parse_note_with_llm, recommend_coverage

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "dev-secret-key-change-in-production")


@app.before_request
def redirect_to_https():
    """Redirect HTTP requests to HTTPS for security. Disabled in testing."""
    if app.config.get("TESTING"):
        return None
    if request.scheme == "http" and not request.headers.get("X-Forwarded-Proto", "") == "https":
        return redirect(request.url.replace("http://", "https://"), code=301)


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


def filter_available_employees(employees, parsed_when):
    """Filter out employees whose unavailable_days match the parsed day."""
    if not parsed_when or parsed_when == "unspecified":
        return employees
    day_keywords = [
        "monday", "tuesday", "wednesday", "thursday",
        "friday", "saturday", "sunday", "today", "tomorrow", "tonight",
    ]
    matched_days = [d for d in day_keywords if d in parsed_when.lower()]
    if not matched_days:
        return employees
    available = []
    for emp in employees:
        unavail = (emp["unavailable_days"] or "").lower()
        if not any(day in unavail for day in matched_days):
            available.append(emp)
    return available


# ---------------------------------------------------------------------------
# Core routes
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    if "user_id" not in session:
        return redirect(url_for("login"))
    db = get_db()
    user = db.execute("SELECT * FROM users WHERE id = ?", (session["user_id"],)).fetchone()
    notes = db.execute(
        "SELECT * FROM notes WHERE user_id = ? ORDER BY created_at DESC",
        (session["user_id"],),
    ).fetchall()
    all_employees = db.execute("SELECT * FROM employees ORDER BY name").fetchall()

    all_notes = db.execute(
        "SELECT * FROM notes WHERE user_id = ? AND assigned_to IS NOT NULL",
        (session["user_id"],),
    ).fetchall()
    assignment_counts = {}
    for n in all_notes:
        if n["assigned_to"]:
            assignment_counts[n["assigned_to"]] = assignment_counts.get(n["assigned_to"], 0) + 1

    available_employees = {}
    recommendations = {}
    for note in notes:
        if note["status"] == "open":
            avail = filter_available_employees(all_employees, note["parsed_when"])
            available_employees[note["id"]] = avail
            rec = recommend_coverage(
                note["body"], note["parsed_who"], note["parsed_when"],
                [dict(e) for e in all_employees], assignment_counts,
            )
            recommendations[note["id"]] = rec
        else:
            available_employees[note["id"]] = all_employees

    db.close()
    return render_template(
        "index.html", user=user, notes=notes, all_employees=all_employees,
        available_employees=available_employees, recommendations=recommendations,
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

        parsed = parse_note_with_llm(body, emp_names)
        if parsed is None:
            parsed = parse_note(body)

        if not parsed.get("who"):
            body_lower = body.lower()
            for emp in employees:
                first_name = emp["name"].split()[0].lower()
                if first_name in body_lower:
                    parsed["who"] = emp["name"]
                    break

        db.execute(
            "INSERT INTO notes (user_id, body, status, parsed_who, parsed_what, "
            "parsed_when, parsed_urgency, created_at) "
            "VALUES (?, ?, 'open', ?, ?, ?, ?, ?)",
            (session["user_id"], body, parsed["who"], parsed["what"],
             parsed["when"], parsed["urgency"], datetime.now().strftime("%Y-%m-%d %H:%M")),
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
            "SELECT * FROM notes WHERE id = ? AND user_id = ?",
            (note_id, session["user_id"]),
        ).fetchone()
        if note and note["status"] == "open":
            db.execute(
                "UPDATE notes SET status = 'approved', assigned_to = ?, approved_at = ? WHERE id = ?",
                (assigned_to, datetime.now().strftime("%Y-%m-%d %H:%M"), note_id),
            )
            db.commit()

            emp = db.execute(
                "SELECT * FROM employees WHERE name = ?", (assigned_to,)
            ).fetchone()
            user = db.execute(
                "SELECT * FROM users WHERE id = ?", (session["user_id"],)
            ).fetchone()
            db.close()

            user_role = user["role"] if user else "manager"
            if user_role == "demo":
                log_action(
                    "swap_approved",
                    f"Note #{note_id} assigned to {assigned_to}, "
                    "email logged (demo account - not sent)",
                )
            else:
                emp_email = emp["email"] if emp else None
                emp_phone = emp["phone"] if emp else None
                manager_name = user["display_name"] if user else "Manager"
                sent = send_swap_notification(assigned_to, emp_email, note["body"], manager_name)
                sms_sent = send_swap_sms(assigned_to, emp_phone, note["body"])
                log_action(
                    "swap_approved",
                    f"Note #{note_id} assigned to {assigned_to}, "
                    f"email sent: {sent}, sms sent: {sms_sent}",
                )
        else:
            db.close()
    return redirect(url_for("index"))


# ---------------------------------------------------------------------------
# Team / availability
# ---------------------------------------------------------------------------

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
                db.execute(
                    "UPDATE employees SET unavailable_days = ? WHERE id = ?",
                    (days, emp["id"]),
                )
            db.commit()
        elif action == "add_employee":
            name = request.form.get("emp_name", "").strip()
            email = request.form.get("emp_email", "").strip()
            phone = request.form.get("emp_phone", "").strip()
            role = request.form.get("emp_role", "officer").strip() or "officer"
            if name:
                db.execute(
                    "INSERT INTO employees (name, email, phone, role, unavailable_days) "
                    "VALUES (?, ?, ?, ?, '')",
                    (name, email, phone, role),
                )
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


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------

@app.route("/dashboard")
def dashboard():
    if "user_id" not in session:
        return redirect(url_for("login"))
    db = get_db()
    user = db.execute("SELECT * FROM users WHERE id = ?", (session["user_id"],)).fetchone()
    notes = db.execute(
        "SELECT * FROM notes WHERE user_id = ? ORDER BY created_at DESC",
        (session["user_id"],),
    ).fetchall()
    employees = db.execute("SELECT * FROM employees").fetchall()

    total_notes = len(notes)
    open_notes = sum(1 for n in notes if n["status"] == "open")
    approved_notes = sum(1 for n in notes if n["status"] == "approved")

    urgency_high = sum(1 for n in notes if n["parsed_urgency"] == "high")
    urgency_medium = sum(1 for n in notes if n["parsed_urgency"] == "medium")
    urgency_low = sum(1 for n in notes if n["parsed_urgency"] == "low")

    reasons = {}
    for n in notes:
        reason = n["parsed_what"] or "unspecified"
        reasons[reason] = reasons.get(reason, 0) + 1

    assignments = {}
    for n in notes:
        if n["assigned_to"]:
            assignments[n["assigned_to"]] = assignments.get(n["assigned_to"], 0) + 1

    day_names = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
    day_counts = {d: {"open": 0, "approved": 0, "total": 0} for d in day_names}
    for n in notes:
        when = (n["parsed_when"] or "").lower()
        for day in day_names:
            if day in when:
                day_counts[day]["total"] += 1
                if n["status"] == "open":
                    day_counts[day]["open"] += 1
                else:
                    day_counts[day]["approved"] += 1
                break

    db.close()
    return render_template(
        "dashboard.html", user=user, total_notes=total_notes, open_notes=open_notes,
        approved_notes=approved_notes, urgency_high=urgency_high,
        urgency_medium=urgency_medium, urgency_low=urgency_low,
        reasons=reasons, assignments=assignments,
        total_employees=len(employees), day_counts=day_counts,
        day_labels=["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
    )


# ---------------------------------------------------------------------------
# Audit log
# ---------------------------------------------------------------------------

@app.route("/audit")
def audit():
    if "user_id" not in session:
        return redirect(url_for("login"))
    db = get_db()
    user = db.execute("SELECT * FROM users WHERE id = ?", (session["user_id"],)).fetchone()
    logs = db.execute("SELECT * FROM audit_log ORDER BY created_at DESC LIMIT 50").fetchall()
    db.close()
    return render_template("audit.html", user=user, logs=logs)


# ---------------------------------------------------------------------------
# Calendar
# ---------------------------------------------------------------------------

@app.route("/calendar")
def calendar():
    if "user_id" not in session:
        return redirect(url_for("login"))
    import calendar as cal

    today = date.today()
    year = int(request.args.get("year", today.year))
    month = int(request.args.get("month", today.month))

    cal_data = cal.monthcalendar(year, month)
    month_name = cal.month_name[month]

    db = get_db()
    user = db.execute("SELECT * FROM users WHERE id = ?", (session["user_id"],)).fetchone()
    notes = db.execute(
        "SELECT * FROM notes WHERE user_id = ? ORDER BY created_at DESC",
        (session["user_id"],),
    ).fetchall()
    db.close()

    notes_by_day = {}
    day_keywords = {
        "monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3,
        "friday": 4, "saturday": 5, "sunday": 6,
    }
    for note in notes:
        when = (note["parsed_when"] or "").lower()
        placed = False

        for day_name, day_num in day_keywords.items():
            if day_name in when:
                for week in cal_data:
                    if week[day_num] != 0:
                        d = date(year, month, week[day_num])
                        notes_by_day.setdefault(d, []).append(note)
                        placed = True
                break

        if not placed:
            date_match = re.search(r"(\d{1,2})/(\d{1,2})", when)
            if date_match:
                m, d = int(date_match.group(1)), int(date_match.group(2))
                if m == month:
                    try:
                        target = date(year, month, d)
                        notes_by_day.setdefault(target, []).append(note)
                        placed = True
                    except ValueError:
                        pass

        if not placed and "today" in when:
            notes_by_day.setdefault(today, []).append(note)
        elif not placed and "tomorrow" in when:
            notes_by_day.setdefault(today + timedelta(days=1), []).append(note)

    weeks = []
    for week in cal_data:
        week_days = []
        for day_num in week:
            if day_num == 0:
                week_days.append(None)
            else:
                d = date(year, month, day_num)
                day_notes = notes_by_day.get(d, [])
                week_days.append({
                    "day": day_num,
                    "date": d,
                    "is_today": d == today,
                    "notes": day_notes,
                    "open_count": sum(1 for n in day_notes if n["status"] == "open"),
                    "approved_count": sum(1 for n in day_notes if n["status"] == "approved"),
                })
        weeks.append(week_days)

    prev_month = month - 1 if month > 1 else 12
    prev_year = year if month > 1 else year - 1
    next_month = month + 1 if month < 12 else 1
    next_year = year if month < 12 else year + 1

    return render_template(
        "calendar.html", user=user, weeks=weeks, month_name=month_name,
        year=year, month=month, prev_month=prev_month, prev_year=prev_year,
        next_month=next_month, next_year=next_year, today=today,
    )


# ---------------------------------------------------------------------------
# CSV export
# ---------------------------------------------------------------------------

@app.route("/export/csv")
def export_csv():
    if "user_id" not in session:
        return redirect(url_for("login"))
    db = get_db()
    notes = db.execute(
        "SELECT * FROM notes WHERE user_id = ? ORDER BY created_at DESC",
        (session["user_id"],),
    ).fetchall()
    db.close()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "ID", "Body", "Status", "Assigned To", "Who", "What", "When",
        "Urgency", "Created At", "Approved At",
    ])
    for n in notes:
        writer.writerow([
            n["id"], n["body"], n["status"], n["assigned_to"] or "",
            n["parsed_who"] or "", n["parsed_what"] or "", n["parsed_when"] or "",
            n["parsed_urgency"] or "", n["created_at"], n["approved_at"] or "",
        ])

    log_action("csv_exported", f"{len(notes)} notes")
    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=shift_notes_export.csv"},
    )


# ---------------------------------------------------------------------------
# Shift templates
# ---------------------------------------------------------------------------

@app.route("/templates", methods=["GET", "POST"])
def shift_templates():
    if "user_id" not in session:
        return redirect(url_for("login"))
    db = get_db()
    user = db.execute("SELECT * FROM users WHERE id = ?", (session["user_id"],)).fetchone()

    if request.method == "POST":
        action = request.form.get("action", "")
        if action == "create_template":
            name = request.form.get("name", "").strip()
            day_pattern = request.form.get("day_pattern", "").strip()
            start_time = request.form.get("start_time", "").strip()
            end_time = request.form.get("end_time", "").strip()
            required = request.form.get("required_officers", "2").strip()
            if name and day_pattern:
                db.execute(
                    "INSERT INTO shift_templates (user_id, name, day_pattern, start_time, "
                    "end_time, required_officers, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (session["user_id"], name, day_pattern, start_time, end_time,
                     int(required), datetime.now().strftime("%Y-%m-%d %H:%M")),
                )
                db.commit()
                log_action("template_created", name)
        elif action == "delete_template":
            tid = request.form.get("template_id", "")
            if tid:
                db.execute(
                    "DELETE FROM shift_templates WHERE id = ? AND user_id = ?",
                    (tid, session["user_id"]),
                )
                db.commit()
        elif action == "apply_template":
            tid = request.form.get("template_id", "")
            tmpl = db.execute(
                "SELECT * FROM shift_templates WHERE id = ? AND user_id = ?",
                (tid, session["user_id"]),
            ).fetchone()
            if tmpl:
                days = tmpl["day_pattern"].split(",")
                for day in days:
                    day = day.strip()
                    body = f"Shift coverage needed for {day} {tmpl['start_time']}-{tmpl['end_time']} ({tmpl['name']})"
                    db.execute(
                        "INSERT INTO notes (user_id, body, status, parsed_who, parsed_what, "
                        "parsed_when, parsed_urgency, created_at) "
                        "VALUES (?, ?, 'open', '', 'shift template', ?, 'medium', ?)",
                        (session["user_id"], body, day,
                         datetime.now().strftime("%Y-%m-%d %H:%M")),
                    )
                db.commit()
                log_action("template_applied", tmpl["name"])
        db.close()
        return redirect(url_for("shift_templates"))

    templates = db.execute(
        "SELECT * FROM shift_templates WHERE user_id = ? ORDER BY created_at DESC",
        (session["user_id"],),
    ).fetchall()
    db.close()
    return render_template("templates.html", user=user, templates=templates)


# ---------------------------------------------------------------------------
# API endpoints
# ---------------------------------------------------------------------------

@app.route("/api/conflict-check")
def conflict_check():
    """Check if an employee has conflicts for a given day."""
    if "user_id" not in session:
        return {"error": "not logged in"}, 401
    emp_name = request.args.get("name", "").strip()
    parsed_when = request.args.get("when", "").strip()
    if not emp_name:
        return {"conflicts": [], "unavailable": False}

    db = get_db()
    emp = db.execute("SELECT * FROM employees WHERE name = ?", (emp_name,)).fetchone()

    unavailable = False
    if emp and parsed_when:
        unavail = (emp["unavailable_days"] or "").lower()
        day_keywords = [
            "monday", "tuesday", "wednesday", "thursday",
            "friday", "saturday", "sunday",
        ]
        for day in day_keywords:
            if day in parsed_when.lower() and day in unavail:
                unavailable = True
                break

    existing = db.execute(
        "SELECT * FROM notes WHERE assigned_to = ? AND status = 'approved' AND parsed_when LIKE ?",
        (emp_name, f"%{parsed_when}%"),
    ).fetchall()
    db.close()
    return {
        "conflicts": [{"body": n["body"], "when": n["parsed_when"]} for n in existing],
        "unavailable": unavailable,
        "count": len(existing),
    }


@app.route("/api/llm-summary")
def llm_summary():
    """Generate a one-line summary of the current shift coverage situation."""
    if "user_id" not in session:
        return {"summary": ""}, 401
    db = get_db()
    notes = db.execute(
        "SELECT * FROM notes WHERE user_id = ? ORDER BY created_at DESC",
        (session["user_id"],),
    ).fetchall()
    db.close()

    open_count = sum(1 for n in notes if n["status"] == "open")
    approved_count = sum(1 for n in notes if n["status"] == "approved")
    high_count = sum(
        1 for n in notes if n["parsed_urgency"] == "high" and n["status"] == "open"
    )
    summary = f"{open_count} open notes, {approved_count} approved, {high_count} high-urgency uncovered."
    return {"summary": summary}


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

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


@app.route("/register", methods=["GET", "POST"])
def register():
    """User registration.

    NOTE: This is a prototype endpoint with no email verification or admin
    approval. Anyone can create a manager account. In production, this would
    require an invite code or admin approval flow.
    """
    error = None
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        display_name = request.form.get("display_name", "").strip()
        email = request.form.get("email", "").strip()
        if not username or not password or not display_name:
            error = "All fields are required."
        elif len(password) < 4:
            error = "Password must be at least 4 characters."
        else:
            db = get_db()
            existing = db.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
            if existing:
                error = "That username is taken."
            else:
                db.execute(
                    "INSERT INTO users (username, password_hash, display_name, role, email) "
                    "VALUES (?, ?, ?, 'manager', ?)",
                    (username, generate_password_hash(password), display_name, email or None),
                )
                db.commit()
                db.close()
                log_action("user_registered", username)
                return redirect(url_for("login"))
            db.close()
    return render_template("register.html", error=error)


@app.route("/reset-password", methods=["GET", "POST"])
def reset_password():
    """Simple password reset flow.

    NOTE: This is a prototype endpoint with no email verification. In
    production, this would send a reset link to the user's registered email
    rather than allowing an immediate password change.
    """
    error = None
    success = None
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        new_password = request.form.get("new_password", "")
        confirm = request.form.get("confirm_password", "")
        if not username or not new_password:
            error = "All fields are required."
        elif len(new_password) < 4:
            error = "Password must be at least 4 characters."
        elif new_password != confirm:
            error = "Passwords do not match."
        else:
            db = get_db()
            user = db.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
            if not user:
                error = "No account found with that username."
            else:
                db.execute(
                    "UPDATE users SET password_hash = ? WHERE username = ?",
                    (generate_password_hash(new_password), username),
                )
                db.commit()
                db.close()
                success = "Password updated. You can now log in with your new password."
                return render_template("reset_password.html", error=error, success=success)
            db.close()
    return render_template("reset_password.html", error=error, success=success)


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


if __name__ == "__main__":
    init_db()
    app.run(debug=True, port=5000)
