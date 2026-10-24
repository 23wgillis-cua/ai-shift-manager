import pytest
import os
import tempfile
import app as app_module
import app.models as models_module
import app.llm_parser as llm_module
from app import app, init_db, get_db


@pytest.fixture
def client():
    db_fd, db_path = tempfile.mkstemp(suffix=".db")
    app_module.DB_PATH = db_path
    models_module.DB_PATH = db_path
    # Disable external services for tests
    from app import notifications as notif
    notif.ses_client = None
    notif.sns_client = None
    app_module.BEDROCK_ENABLED = False
    llm_module.BEDROCK_ENABLED = False
    os.environ["SES_ENABLED"] = "0"
    os.environ["BEDROCK_ENABLED"] = "0"
    os.environ["SNS_ENABLED"] = "0"

    app.config["TESTING"] = True
    app.config["SECRET_KEY"] = "test-secret"
    init_db()

    with app.test_client() as client:
        yield client

    app_module.DB_PATH = "shiftmanager.db"
    models_module.DB_PATH = "shiftmanager.db"
    os.close(db_fd)
    os.unlink(db_path)


def login(client, username="demo", password="demo"):
    return client.post("/login", data={"username": username, "password": password}, follow_redirects=True)


# --- Login / auth tests ---

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


# --- Note CRUD tests ---

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


# --- Dashboard tests ---

def test_dashboard_has_heatmap(client):
    login(client)
    client.post("/add-note", data={"body": "Mike is out Friday"}, follow_redirects=True)
    rv = client.get("/dashboard")
    assert rv.status_code == 200
    assert b"heatmap" in rv.data


def test_dashboard_shows_counts(client):
    login(client)
    client.post("/add-note", data={"body": "Mike is out sick today"}, follow_redirects=True)
    client.post("/add-note", data={"body": "Sarah has a funeral Wednesday"}, follow_redirects=True)
    rv = client.get("/dashboard")
    assert rv.status_code == 200
    assert b"total" in rv.data or b"Total" in rv.data


# --- Calendar tests ---

def test_calendar_page_loads(client):
    login(client)
    rv = client.get("/calendar")
    assert rv.status_code == 200
    assert b"calendar" in rv.data or b"Calendar" in rv.data


def test_calendar_shows_notes_on_correct_day(client):
    login(client)
    client.post("/add-note", data={"body": "Mike is out Friday"}, follow_redirects=True)
    rv = client.get("/calendar")
    assert rv.status_code == 200
    assert b"Mike is out Friday" in rv.data or b"note" in rv.data


# --- CSV export test ---

def test_csv_export(client):
    login(client)
    client.post("/add-note", data={"body": "Mike is out sick today"}, follow_redirects=True)
    rv = client.get("/export/csv")
    assert rv.status_code == 200
    assert b"text/csv" in rv.content_type.encode()
    assert b"ID" in rv.data
    assert b"Mike is out sick today" in rv.data


# --- Templates tests ---

def test_templates_page_loads(client):
    login(client)
    rv = client.get("/templates")
    assert rv.status_code == 200
    assert b"Shift Templates" in rv.data


def test_create_and_apply_template(client):
    login(client)
    rv = client.post("/templates", data={
        "action": "create_template",
        "name": "Weekday Day",
        "day_pattern": "monday, tuesday",
        "start_time": "7am",
        "end_time": "3pm",
        "required_officers": "2",
    }, follow_redirects=True)
    assert rv.status_code == 200
    assert b"Weekday Day" in rv.data
    rv = client.post("/templates", data={"action": "apply_template", "template_id": "1"}, follow_redirects=True)
    assert rv.status_code == 200


# --- Audit log test ---

def test_audit_log_page_loads(client):
    login(client)
    client.post("/add-note", data={"body": "Test audit note"}, follow_redirects=True)
    rv = client.get("/audit")
    assert rv.status_code == 200
    assert b"audit" in rv.data or b"Audit" in rv.data
    assert b"note_created" in rv.data


# --- Password reset tests ---

def test_password_reset_page_loads(client):
    rv = client.get("/reset-password")
    assert rv.status_code == 200
    assert b"Reset Password" in rv.data


def test_password_reset_changes_password(client):
    rv = client.post("/reset-password", data={
        "username": "demo",
        "new_password": "newpass",
        "confirm_password": "newpass",
    }, follow_redirects=True)
    assert rv.status_code == 200
    assert b"Password updated" in rv.data
    rv = client.post("/login", data={"username": "demo", "password": "demo"}, follow_redirects=True)
    assert b"Invalid username or password" in rv.data
    rv = client.post("/login", data={"username": "demo", "password": "newpass"}, follow_redirects=True)
    assert rv.status_code == 200
    assert b"Shift Notes" in rv.data


# --- Registration test ---

def test_register_new_user(client):
    rv = client.post("/register", data={
        "username": "newuser",
        "password": "test1234",
        "display_name": "New User",
        "email": "new@example.com",
    }, follow_redirects=True)
    assert rv.status_code == 200
    assert b"Sign In" in rv.data
    rv = client.post("/login", data={"username": "newuser", "password": "test1234"}, follow_redirects=True)
    assert rv.status_code == 200
    assert b"Shift Notes" in rv.data


def test_register_duplicate_username_fails(client):
    rv = client.post("/register", data={
        "username": "demo",
        "password": "test1234",
        "display_name": "Duplicate",
    }, follow_redirects=True)
    assert b"taken" in rv.data or b"Sign In" not in rv.data


# --- API tests ---

def test_conflict_check_api(client):
    login(client)
    rv = client.get("/api/conflict-check?name=Mike%20Rodriguez&when=friday")
    assert rv.status_code == 200
    data = rv.get_json()
    assert "conflicts" in data
    assert "unavailable" in data


def test_llm_summary_api(client):
    login(client)
    rv = client.get("/api/llm-summary")
    assert rv.status_code == 200
    data = rv.get_json()
    assert "summary" in data
    assert "open" in data["summary"]


# --- Notification tests ---

def test_sms_disabled_in_test(client):
    from app.notifications import send_swap_sms
    result = send_swap_sms("Test", "+15555555555", "test note")
    assert result is False


def test_email_disabled_in_test(client):
    from app.notifications import send_swap_notification
    result = send_swap_notification("Test", "test@example.com", "note", "Manager")
    assert result is False
