"""Coverage cascade: ordered shift offers with accept/decline handling.

When a manager starts a coverage request, candidates are ranked by
best fit (AI recommendation when available, otherwise a deterministic
fairness rule), and each receives an email with Accept / Decline links.
A decline automatically advances to the next candidate.
"""
import os
import secrets
from datetime import datetime

from app.models import get_db
from app.notifications import send_coverage_offer
from app.llm_parser import recommend_coverage

APP_BASE_URL = os.environ.get("APP_BASE_URL", "https://aishiftmanager.duckdns.org")


def _now():
    return datetime.now().strftime("%Y-%m-%d %H:%M")


def build_candidate_order(note, db):
    """Return candidates for a note, ordered by best fit.

    Ordering: LLM recommendation rankings first, then remaining available
    employees sorted by fewest recent assignments (workload fairness).
    Excludes the person who is out and anyone unavailable on that day.
    """
    employees = db.execute("SELECT * FROM employees ORDER BY name").fetchall()

    all_notes = db.execute(
        "SELECT * FROM notes WHERE assigned_to IS NOT NULL"
    ).fetchall()
    assignment_counts = {}
    for n in all_notes:
        if n["assigned_to"]:
            assignment_counts[n["assigned_to"]] = (
                assignment_counts.get(n["assigned_to"], 0) + 1
            )

    out_who = note["parsed_who"]
    when = (note["parsed_when"] or "").lower()

    day_keywords = [
        "monday", "tuesday", "wednesday", "thursday",
        "friday", "saturday", "sunday",
    ]
    matched_days = [d for d in day_keywords if d in when]

    candidates = []
    for emp in employees:
        if out_who and emp["name"].lower() == out_who.lower():
            continue
        unavail = (emp["unavailable_days"] or "").lower()
        if matched_days and any(day in unavail for day in matched_days):
            continue
        candidates.append(emp)

    # Ask the LLM for a ranking (may be None in demo mode / no Bedrock).
    order = []
    try:
        rec = recommend_coverage(
            note["body"], note["parsed_who"], note["parsed_when"],
            [dict(e) for e in employees], assignment_counts,
        )
    except Exception:
        rec = None

    ranked_names = []
    if rec and rec.get("rankings"):
        for r in rec["rankings"]:
            name = (r.get("name") or "").strip()
            for emp in candidates:
                if emp["name"] == name and emp["name"] not in ranked_names:
                    ranked_names.append(emp["name"])
        if rec.get("recommended") and rec["recommended"] not in ranked_names:
            for emp in candidates:
                if emp["name"] == rec["recommended"]:
                    ranked_names.insert(0, emp["name"])
                    break

    ranked = [e for e in candidates if e["name"] in ranked_names]
    ranked.sort(key=lambda e: ranked_names.index(e["name"]))
    rest = [e for e in candidates if e["name"] not in ranked_names]
    # Fairness: fewest assignments first, then name for determinism.
    rest.sort(key=lambda e: (assignment_counts.get(e["name"], 0), e["name"]))
    return ranked + rest


def start_cascade(note_id, user_id, demo=False):
    """Begin (or resume) a coverage cascade for a note.

    Sends an offer to the best candidate. Returns a status dict.
    """
    db = get_db()
    note = db.execute(
        "SELECT * FROM notes WHERE id = ? AND user_id = ?", (note_id, user_id)
    ).fetchone()
    if not note or note["status"] != "open":
        db.close()
        return {"ok": False, "reason": "Note not found or already covered"}

    # Cancel any previous pending offers for this note.
    db.execute(
        "UPDATE coverage_offers SET status = 'cancelled' "
        "WHERE note_id = ? AND status = 'pending'",
        (note_id,),
    )

    candidates = build_candidate_order(note, db)
    if not candidates:
        db.close()
        return {"ok": False, "reason": "No available candidates for this shift"}

    _send_offer_to(db, note, candidates[0], user_id, demo)
    db.commit()
    db.close()
    return {"ok": True, "notified": candidates[0]["name"]}


def _send_offer_to(db, note, emp, user_id, demo=False):
    token = secrets.token_urlsafe(24)
    accept_url = f"{APP_BASE_URL}/offer/{token}/accept"
    decline_url = f"{APP_BASE_URL}/offer/{token}/decline"
    db.execute(
        "INSERT INTO coverage_offers "
        "(note_id, employee_name, employee_email, status, token, created_at) "
        "VALUES (?, ?, ?, 'pending', ?, ?)",
        (note["id"], emp["name"], emp["email"], token, _now()),
    )
    if demo:
        sent = True  # logged rather than sent for the demo account
        detail = (
            f"Coverage offer #{note['id']} sent to {emp['name']} "
            f"(demo account - logged, not sent)"
        )
    else:
        sent = send_coverage_offer(
            emp["name"], emp["email"], note["body"], accept_url, decline_url
        )
        detail = (
            f"Coverage offer #{note['id']} sent to {emp['name']}, email: {sent}"
        )
    db.execute(
        "INSERT INTO audit_log (user_id, action, detail, created_at) "
        "VALUES (?, 'offer_sent', ?, ?)",
        (user_id, detail, _now()),
    )
    return sent


def _advance(db, note, declined_name, user_id, demo=False):
    """Move to the next candidate after a decline. Returns next name or None."""
    declined = db.execute(
        "SELECT employee_name FROM coverage_offers WHERE note_id = ? AND status = 'declined'",
        (note["id"],),
    ).fetchall()
    declined_names = {r["employee_name"] for r in declined} | {declined_name}
    candidates = build_candidate_order(note, db)
    for emp in candidates:
        if emp["name"] not in declined_names:
            _send_offer_to(db, note, emp, user_id, demo)
            db.commit()
            return emp["name"]
    return None


def respond_to_offer(token, action):
    """Handle an employee clicking Accept or Decline in their email.

    Returns a status dict used by the public response page.
    """
    db = get_db()
    offer = db.execute(
        "SELECT * FROM coverage_offers WHERE token = ?", (token,)
    ).fetchone()
    if not offer:
        db.close()
        return {"ok": False, "reason": "not_found"}

    note = db.execute("SELECT * FROM notes WHERE id = ?", (offer["note_id"],)).fetchone()
    if not note:
        db.close()
        return {"ok": False, "reason": "not_found"}

    # Already handled (accepted, declined, or cancelled).
    if offer["status"] != "pending":
        db.close()
        return {
            "ok": True,
            "action": offer["status"],
            "employee": offer["employee_name"],
            "note_body": note["body"],
            "already": True,
        }

    if action == "accept":
        if note["status"] != "open":
            # Someone else accepted first.
            db.execute(
                "UPDATE coverage_offers SET status = 'cancelled', responded_at = ? "
                "WHERE id = ?",
                (_now(), offer["id"]),
            )
            db.commit()
            db.close()
            return {
                "ok": True, "action": "late", "employee": offer["employee_name"],
                "note_body": note["body"], "already": True,
            }
        db.execute(
            "UPDATE coverage_offers SET status = 'accepted', responded_at = ? "
            "WHERE id = ?",
            (_now(), offer["id"]),
        )
        db.execute(
            "UPDATE notes SET status = 'approved', assigned_to = ?, approved_at = ? "
            "WHERE id = ?",
            (offer["employee_name"], _now(), note["id"]),
        )
        # Cancel any other pending offers for this note.
        db.execute(
            "UPDATE coverage_offers SET status = 'cancelled' "
            "WHERE note_id = ? AND status = 'pending'",
            (note["id"],),
        )
        db.execute(
            "INSERT INTO audit_log (user_id, action, detail, created_at) "
            "VALUES (?, 'offer_accepted', ?, ?)",
            (note["user_id"],
             f"Note #{note['id']} accepted by {offer['employee_name']} via email link",
             _now()),
        )
        db.commit()
        db.close()
        return {
            "ok": True, "action": "accepted", "employee": offer["employee_name"],
            "note_body": note["body"], "manager": note["parsed_who"],
        }

    elif action == "decline":
        db.execute(
            "UPDATE coverage_offers SET status = 'declined', responded_at = ? "
            "WHERE id = ?",
            (_now(), offer["id"]),
        )
        db.execute(
            "INSERT INTO audit_log (user_id, action, detail, created_at) "
            "VALUES (?, 'offer_declined', ?, ?)",
            (note["user_id"],
             f"Note #{note['id']} declined by {offer['employee_name']}",
             _now()),
        )
        demo = _note_owner_is_demo(db, note["user_id"])
        next_name = _advance(db, note, offer["employee_name"], note["user_id"], demo)
        if next_name:
            detail = f"Offer advanced to {next_name} after decline"
        else:
            detail = "No more candidates available"
        db.execute(
            "INSERT INTO audit_log (user_id, action, detail, created_at) "
            "VALUES (?, 'offer_advanced', ?, ?)",
            (note["user_id"], detail, _now()),
        )
        db.commit()
        db.close()
        return {
            "ok": True, "action": "declined", "employee": offer["employee_name"],
            "note_body": note["body"], "next": next_name,
        }

    db.close()
    return {"ok": False, "reason": "bad_action"}


def _note_owner_is_demo(db, user_id):
    owner = db.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    return bool(owner and owner["role"] == "demo")


def get_note_offers(note_id):
    """Return the offer chain for a note, newest first."""
    db = get_db()
    offers = db.execute(
        "SELECT * FROM coverage_offers WHERE note_id = ? "
        "ORDER BY id DESC",
        (note_id,),
    ).fetchall()
    db.close()
    return offers
