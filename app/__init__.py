from flask import Flask, render_template, request, redirect, url_for, session
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3
import os
from datetime import datetime

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "dev-secret-key-change-in-production")

DB_PATH = os.environ.get("DB_PATH", "shiftmanager.db")


def get_db():
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    return db


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
            role TEXT DEFAULT 'officer'
        )
        """
    )
    count = db.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    if count == 0:
        db.execute(
            "INSERT INTO users (username, password_hash, display_name, role, email) VALUES (?, ?, ?, ?, ?)",
            ("admin", generate_password_hash("admin"), "Admin", "manager", "admin@example.com"),
        )
    emp_count = db.execute("SELECT COUNT(*) FROM employees").fetchone()[0]
    if emp_count == 0:
        db.executemany(
            "INSERT INTO employees (name, email, role) VALUES (?, ?, ?)",
            [
                ("Mike Rodriguez", "mike@example.com", "officer"),
                ("Sarah Chen", "sarah@example.com", "officer"),
                ("James O'Brien", "james@example.com", "officer"),
                ("Maria Santos", "maria@example.com", "supervisor"),
                ("Tony Walker", "tony@example.com", "officer"),
                ("Priya Patel", "priya@example.com", "officer"),
            ],
        )
    db.commit()
    db.close()


@app.route("/")
def index():
    if "user_id" not in session:
        return redirect(url_for("login"))
    db = get_db()
    user = db.execute("SELECT * FROM users WHERE id = ?", (session["user_id"],)).fetchone()
    notes = db.execute(
        "SELECT * FROM notes WHERE user_id = ? ORDER BY created_at DESC", (session["user_id"],)
    ).fetchall()
    employees = db.execute("SELECT * FROM employees ORDER BY name").fetchall()
    db.close()
    return render_template("index.html", user=user, notes=notes, employees=employees)


@app.route("/add-note", methods=["POST"])
def add_note():
    if "user_id" not in session:
        return redirect(url_for("login"))
    body = request.form.get("body", "").strip()
    if body:
        db = get_db()
        db.execute(
            "INSERT INTO notes (user_id, body, status, created_at) VALUES (?, ?, 'open', ?)",
            (session["user_id"], body, datetime.now().strftime("%Y-%m-%d %H:%M")),
        )
        db.commit()
        db.close()
    return redirect(url_for("index"))


@app.route("/approve/<int:note_id>", methods=["POST"])
def approve_note(note_id):
    if "user_id" not in session:
        return redirect(url_for("login"))
    assigned_to = request.form.get("assigned_to", "").strip()
    if assigned_to:
        db = get_db()
        db.execute(
            "UPDATE notes SET status = 'approved', assigned_to = ?, approved_at = ? WHERE id = ? AND user_id = ?",
            (assigned_to, datetime.now().strftime("%Y-%m-%d %H:%M"), note_id, session["user_id"]),
        )
        db.commit()
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
