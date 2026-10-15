import pytest
import os
import tempfile
import app as app_module
import app.llm_parser as llm_module
from app import app, init_db, get_db


@pytest.fixture
def client():
    import importlib
    db_fd, db_path = tempfile.mkstemp(suffix=".db")
    app_module.DB_PATH = db_path
    app_module.ses_client = None
    app_module.BEDROCK_ENABLED = False
    llm_module.BEDROCK_ENABLED = False
    os.environ["SES_ENABLED"] = "0"
    os.environ["BEDROCK_ENABLED"] = "0"

    app.config["TESTING"] = True
    app.config["SECRET_KEY"] = "test-secret"
    init_db()

    with app.test_client() as client:
        yield client

    app_module.DB_PATH = "shiftmanager.db"
    os.close(db_fd)
    os.unlink(db_path)


def login(client, username="demo", password="demo"):
    return client.post("/login", data={"username": username, "password": password}, follow_redirects=True)


def test_login_page_loads(client):
    rv = client.get("/login")
    assert rv.status_code == 200
    assert b"AI Shift Manager" in rv.data
    assert b"Sign In" in rv.data


def test_root_redirects_to_login_when_not_logged_in(client):
    rv = client.get("/")
    assert rv.status_code == 302
    assert "/login" in rv.headers["Location"]


def test_login_with_correct_credentials(client):
    rv = login(client)
    assert rv.status_code == 200
    assert b"Shift Notes" in rv.data


def test_login_with_wrong_credentials(client):
    rv = client.post("/login", data={"username": "demo", "password": "wrong"}, follow_redirects=True)
    assert rv.status_code == 200
    assert b"Invalid username or password" in rv.data


def test_logout_clears_session(client):
    login(client)
    rv = client.get("/logout", follow_redirects=True)
    assert rv.status_code == 200
    assert b"Sign In" in rv.data


def test_add_note(client):
    login(client)
    rv = client.post("/add-note", data={"body": "Mike is out sick today"}, follow_redirects=True)
    assert rv.status_code == 200
    assert b"Mike is out sick today" in rv.data


def test_empty_note_not_saved(client):
    login(client)
    client.post("/add-note", data={"body": ""}, follow_redirects=True)
    rv = client.get("/")
    assert b"No notes yet" in rv.data or b"note-item" not in rv.data


def test_approve_swap(client):
    login(client)
    client.post("/add-note", data={"body": "Sarah has a dentist appointment Friday"}, follow_redirects=True)
    rv = client.get("/")
    assert b"approve-section" in rv.data or b"Approve" in rv.data
    assert b"Select an employee" in rv.data

    rv = client.post("/approve/1", data={"assigned_to": "Mike Rodriguez"}, follow_redirects=True)
    assert rv.status_code == 200
    assert b"approved" in rv.data
    assert b"Mike Rodriguez" in rv.data


def test_approved_note_shows_assigned_name(client):
    login(client)
    client.post("/add-note", data={"body": "Tony called out"}, follow_redirects=True)
    client.post("/approve/1", data={"assigned_to": "Priya Patel"}, follow_redirects=True)
    rv = client.get("/")
    assert b"Priya Patel" in rv.data
    assert b"Assigned to" in rv.data


def test_employees_are_seeded(client):
    login(client)
    client.post("/add-note", data={"body": "Test note for dropdown"}, follow_redirects=True)
    rv = client.get("/")
    assert b"Mike Rodriguez" in rv.data
    assert b"Sarah Chen" in rv.data


def test_cannot_approve_without_login(client):
    rv = client.post("/approve/1", data={"assigned_to": "Mike Rodriguez"}, follow_redirects=True)
    assert rv.status_code == 200
    assert b"Sign In" in rv.data


def test_cannot_add_note_without_login(client):
    rv = client.post("/add-note", data={"body": "test note"}, follow_redirects=True)
    assert rv.status_code == 200
    assert b"Sign In" in rv.data
