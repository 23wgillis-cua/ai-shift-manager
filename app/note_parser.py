import re
from datetime import datetime


def parse_note(body):
    """Parse a plain-English shift note into structured fields.

    Extracts:
    - who: the employee name mentioned (matched against employee list)
    - what: the reason (funeral, sick, vacation, etc.)
    - when: the day(s) mentioned
    - urgency: high if same-day or next-day, medium if within a week, low otherwise
    """
    body_lower = body.lower()

    # Detect days of week
    days = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
    found_days = [d for d in days if d in body_lower]

    # Detect date-like patterns
    date_patterns = [
        r"\b(\d{1,2}/\d{1,2}(?:/\d{2,4})?)\b",
        r"\b(january|february|march|april|may|june|july|august|september|october|november|december)\s+(\d{1,2})\b",
        r"\b(today|tomorrow|tonight|this (?:morning|afternoon|evening|week))\b",
    ]
    found_dates = []
    for pattern in date_patterns:
        matches = re.findall(pattern, body_lower)
        found_dates.extend([m if isinstance(m, str) else " ".join(m) for m in matches])

    when = ", ".join(found_days + found_dates) if found_days or found_dates else "unspecified"

    # Detect reason keywords
    reason_keywords = {
        "funeral": ["funeral", "memorial", "burial", "wake"],
        "sick": ["sick", "ill", "flu", "fever", "nausea", "throwing up", "vomiting"],
        "vacation": ["vacation", "pto", "time off", "holiday", "personal day"],
        "family": ["family", "childcare", "kid", "baby", "child", "dependent"],
        "appointment": ["appointment", "dentist", "doctor", "medical"],
        "emergency": ["emergency", "urgent", "hospital", "er"],
        "weather": ["snow", "storm", "weather", "ice", "blizzard"],
        "other": ["can't come", "cant come", "cant make", "can't make", "out", "cover", "miss"],
    }
    detected_reasons = []
    for reason, keywords in reason_keywords.items():
        if any(kw in body_lower for kw in keywords):
            detected_reasons.append(reason)

    what = detected_reasons[0] if detected_reasons else "other"

    # Urgency based on timing keywords
    urgency = "low"
    if any(kw in body_lower for kw in ["today", "tonight", "tomorrow", "this morning", "this afternoon", "this evening"]):
        urgency = "high"
    elif found_days:
        urgency = "medium"

    return {
        "who": None,  # filled in by caller with employee match
        "what": what,
        "when": when,
        "urgency": urgency,
        "raw": body,
    }
