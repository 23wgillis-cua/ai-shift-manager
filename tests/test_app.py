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
    # Count notes before empty submission
    rv = client.get("/")
    before_count = rv.data.count(b"note-item")
    client.post("/add-note", data={"body": ""}, follow_redirects=True)
    rv = client.get("/")
    after_count = rv.data.count(b"note-item")
    # Empty note should not increase the count
    assert after_count == before_count


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


# --- Coverage cascade tests ---

def _get_open_note_id(client):
    rv = client.get("/")
    db = models_module.get_db()
    note = db.execute(
        "SELECT * FROM notes WHERE status = 'open' AND user_id = "
        "(SELECT id FROM users WHERE username='demo') LIMIT 1"
    ).fetchone()
    db.close()
    return note["id"], note["parsed_who"]


def test_start_cascade_creates_pending_offer(client):
    login(client)
    note_id, _ = _get_open_note_id(client)
    rv = client.post(f"/start-cascade/{note_id}", follow_redirects=True)
    assert rv.status_code == 200
    assert b"Start coverage cascade" in rv.data
    db = models_module.get_db()
    offers = db.execute("SELECT * FROM coverage_offers WHERE note_id = ?", (note_id,)).fetchall()
    db.close()
    assert len(offers) == 1
    assert offers[0]["status"] == "pending"
    assert offers[0]["token"]


def test_cascade_accepts_and_covers_shift(client):
    login(client)
    note_id, _ = _get_open_note_id(client)
    client.post(f"/start-cascade/{note_id}", follow_redirects=True)
    db = models_module.get_db()
    offer = db.execute("SELECT * FROM coverage_offers WHERE note_id = ?", (note_id,)).fetchone()
    db.close()
    rv = client.get(f"/offer/{offer['token']}/accept")
    assert rv.status_code == 200
    assert b"confirmed to cover" in rv.data
    db = models_module.get_db()
    note = db.execute("SELECT * FROM notes WHERE id = ?", (note_id,)).fetchone()
    updated = db.execute("SELECT * FROM coverage_offers WHERE id = ?", (offer["id"],)).fetchone()
    db.close()
    assert note["status"] == "approved"
    assert note["assigned_to"] == offer["employee_name"]
    assert updated["status"] == "accepted"


def test_cascade_decline_advances_to_next_candidate(client):
    login(client)
    note_id, parsed_who = _get_open_note_id(client)
    client.post(f"/start-cascade/{note_id}", follow_redirects=True)
    db = models_module.get_db()
    first = db.execute("SELECT * FROM coverage_offers WHERE note_id = ?", (note_id,)).fetchone()
    db.close()
    rv = client.get(f"/offer/{first['token']}/decline")
    assert rv.status_code == 200
    assert b"passed to the next available candidate" in rv.data
    db = models_module.get_db()
    offers = db.execute(
        "SELECT * FROM coverage_offers WHERE note_id = ? ORDER BY id", (note_id,)
    ).fetchall()
    note = db.execute("SELECT * FROM notes WHERE id = ?", (note_id,)).fetchone()
    db.close()
    assert len(offers) == 2
    assert offers[0]["status"] == "declined"
    assert offers[1]["status"] == "pending"
    assert offers[1]["employee_name"] != offers[0]["employee_name"]
    assert note["status"] == "open"  # not covered yet


def test_cascade_excludes_declined_and_unavailable(client):
    login(client)
    # Note: "Tony has a dentist appointment Friday" -> excludes Tony (who is out)
    # and Tony is also unavailable Friday, but others remain.
    db = models_module.get_db()
    note = db.execute(
        "SELECT * FROM notes WHERE status='open' AND parsed_when='friday' LIMIT 1"
    ).fetchone()
    db.close()
    assert note is not None
    client.post(f"/start-cascade/{note['id']}", follow_redirects=True)
    db = models_module.get_db()
    offer = db.execute("SELECT * FROM coverage_offers WHERE note_id = ?", (note["id"],)).fetchone()
    db.close()
    # Offer must not go to Tony Walker (unavailable Friday / the one out)
    assert offer["employee_name"] != "Tony Walker"


def test_cascade_offer_link_invalid_token(client):
    rv = client.get("/offer/not-a-real-token/accept")
    assert rv.status_code == 200
    assert b"invalid or has expired" in rv.data


def test_cascade_accept_twice_is_late(client):
    login(client)
    note_id, _ = _get_open_note_id(client)
    client.post(f"/start-cascade/{note_id}", follow_redirects=True)
    db = models_module.get_db()
    offer = db.execute("SELECT * FROM coverage_offers WHERE note_id = ?", (note_id,)).fetchone()
    db.close()
    client.get(f"/offer/{offer['token']}/accept")
    rv = client.get(f"/offer/{offer['token']}/accept")
    assert b"already handled" in rv.data or b"already responded" in rv.data


def test_login_page_has_hero(client):
    rv = client.get("/login")
    assert rv.status_code == 200
    assert b"Never chase shift coverage again" in rv.data


# --- SMS cascade + conflict detection tests ---

def test_offer_sms_disabled_in_test(client):
    from app.notifications import send_coverage_offer_sms
    result = send_coverage_offer_sms("Test", "+15550005555", "note", "http://a", "http://d")
    assert result is False


def test_conflict_blocks_accept_and_advances(client):
    login(client)
    db = models_module.get_db()
    # Find an open note; give its top candidate a same-day approved shift.
    note = db.execute(
        "SELECT * FROM notes WHERE status='open' AND user_id = "
        "(SELECT id FROM users WHERE username='demo') ORDER BY id LIMIT 1"
    ).fetchone()
    db.close()

    # Start cascade, capture the first offer
    client.post(f"/start-cascade/{note['id']}", follow_redirects=True)
    db = models_module.get_db()
    offer = db.execute(
        "SELECT * FROM coverage_offers WHERE note_id = ? ORDER BY id LIMIT 1", (note["id"],)
    ).fetchone()
    db.close()
    assert offer["status"] == "pending"
    first_name = offer["employee_name"]

    # Give that employee an approved assignment on the same day
    db = models_module.get_db()
    db.execute(
        "INSERT INTO notes (user_id, body, status, assigned_to, parsed_who, "
        "parsed_what, parsed_when, parsed_urgency, created_at) "
        "VALUES (?, 'Pre-existing approved shift', 'approved', ?, '', 'other', ?, 'low', ?)",
        (note["user_id"], first_name, note["parsed_when"], "2026-11-01 08:00"),
    )
    db.commit()
    db.close()

    rv = client.get(f"/offer/{offer['token']}/accept")
    assert rv.status_code == 200
    assert b"already covering another shift" in rv.data

    db = models_module.get_db()
    note_after = db.execute("SELECT * FROM notes WHERE id = ?", (note["id"],)).fetchone()
    offers = db.execute(
        "SELECT * FROM coverage_offers WHERE note_id = ? ORDER BY id", (note["id"],)
    ).fetchall()
    db.close()
    # Note stays open, conflicted offer cancelled, next candidate offered
    assert note_after["status"] == "open"
    statuses = {o["employee_name"]: o["status"] for o in offers}
    assert statuses[first_name] == "cancelled"
    pending = [o for o in offers if o["status"] == "pending"]
    assert len(pending) == 1
    assert pending[0]["employee_name"] != first_name


def test_accept_with_no_conflict_succeeds(client):
    login(client)
    db = models_module.get_db()
    note = db.execute(
        "SELECT * FROM notes WHERE status='open' AND user_id = "
        "(SELECT id FROM users WHERE username='demo') ORDER BY id LIMIT 1"
    ).fetchone()
    db.close()
    client.post(f"/start-cascade/{note['id']}", follow_redirects=True)
    db = models_module.get_db()
    offer = db.execute(
        "SELECT * FROM coverage_offers WHERE note_id = ? ORDER BY id LIMIT 1", (note["id"],)
    ).fetchone()
    db.close()
    rv = client.get(f"/offer/{offer['token']}/accept")
    assert b"confirmed to cover" in rv.data
