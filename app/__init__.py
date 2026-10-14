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
            created_at TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
        """
    )
    count = db.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    if count == 0:
        db.execute(
            "INSERT INTO users (username, password_hash, display_name, role, email) VALUES (?, ?, ?, ?, ?)",
            ("admin", generate_password_hash("admin"), "Admin", "manager", "admin@example.com"),
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
    db.close()
    return render_template("index.html", user=user, notes=notes)


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
