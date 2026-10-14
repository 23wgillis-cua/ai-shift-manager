import json
import os
import boto3
from botocore.exceptions import ClientError


BEDROCK_MODEL_ID = os.environ.get("BEDROCK_MODEL_ID", "meta.llama3-8b-instruct-v1:0")
BEDROCK_ENABLED = os.environ.get("BEDROCK_ENABLED", "1") != "0"

_bedrock_client = None


def get_bedrock_client():
    global _bedrock_client
    if _bedrock_client is None and BEDROCK_ENABLED:
        _bedrock_client = boto3.client("bedrock-runtime", region_name="us-east-1")
    return _bedrock_client


def parse_note_with_llm(body, employee_names=None):
    """Use LLM via AWS Bedrock to parse a plain-English shift note into structured data.

    Falls back to None if LLM is unavailable (caller uses regex parser).
    """
    if not BEDROCK_ENABLED:
        return None

    emp_list = ", ".join(employee_names) if employee_names else "not provided"
    prompt = f"""You are a shift scheduling assistant. Parse this note into structured data.

Note: "{body}"

Known employees: {emp_list}

Extract:
- who: the employee name (match to closest known employee, or extract the name in the note)
- what: reason for absence (one word: funeral, sick, vacation, family, appointment, emergency, weather, other)
- when: day or date (e.g. "Wednesday", "today", "tomorrow", or "unspecified")
- urgency: "high" if same-day/next-day, "medium" if within a week, "low" otherwise

Respond with ONLY a JSON object on one line:
{{"who": "", "what": "", "when": "", "urgency": ""}}

Do not include any other text."""

    try:
        client = get_bedrock_client()
        if not client:
            return None

        resp = client.invoke_model(
            modelId=BEDROCK_MODEL_ID,
            body=json.dumps({
                "prompt": prompt,
                "max_gen_len": 200,
            })
        )
        result = json.loads(resp["body"].read())
        text = result.get("generation", "").strip()

        # Extract the first complete JSON object from the response
        start = text.find("{")
        if start == -1:
            return None
        # Find the matching closing brace
        depth = 0
        end = -1
        in_string = False
        escape = False
        for i in range(start, len(text)):
            ch = text[i]
            if escape:
                escape = False
                continue
            if ch == "\\":
                escape = True
                continue
            if ch == '"' and not escape:
                in_string = not in_string
            if not in_string:
                if ch == "{":
                    depth += 1
                elif ch == "}":
                    depth -= 1
                    if depth == 0:
                        end = i + 1
                        break
        if end == -1:
            return None

        json_str = text[start:end]
        parsed = json.loads(json_str)
        return {
            "who": parsed.get("who") or None,
            "what": parsed.get("what", "other"),
            "when": parsed.get("when", "unspecified"),
            "urgency": parsed.get("urgency", "low"),
        }
    except (ClientError, Exception):
        return None


def recommend_coverage(note_body, parsed_who, parsed_when, employees, recent_assignments):
    """Use LLM to recommend the best employee to cover a shift.

    Args:
        note_body: the raw note text
        parsed_who: who is out
        parsed_when: when the shift is
        employees: list of dicts with name, role, unavailable_days
        recent_assignments: dict mapping employee name -> count of recent assignments

    Returns:
        dict with 'recommended' (name), 'reasoning' (string), and 'rankings' (list)
        or None if LLM fails.
    """
    if not BEDROCK_ENABLED:
        return None

    # Build employee summary for the prompt
    emp_lines = []
    for emp in employees:
        if parsed_who and emp["name"] == parsed_who:
            continue  # skip the person who is out
        unavail = emp.get("unavailable_days", "") or ""
        load = recent_assignments.get(emp["name"], 0)
        emp_lines.append(f"- {emp['name']} (role: {emp['role']}, unavailable: {unavail or 'none'}, recent assignments: {load})")

    emp_summary = "\n".join(emp_lines) if emp_lines else "No available employees"

    prompt = f"""You are a shift scheduling assistant. A supervisor needs someone to cover a shift.

Situation:
- Note: "{note_body}"
- Who is out: {parsed_who or 'unknown'}
- When: {parsed_when or 'unspecified'}

Available employees:
{emp_summary}

Recommend the best person to cover this shift. Consider:
1. Is the person available on that day? (check their unavailable days)
2. Who has the fewest recent assignments? (distribute workload fairly)
3. Is the role appropriate? (supervisors covering officers is fine but not ideal)

Respond with ONLY a JSON object:
{{"recommended": "employee name", "reasoning": "one sentence explanation", "rankings": [{{"name": "", "score": 0}}]}}

Scores should be 1-10 based on suitability. Do not include any other text."""

    try:
        client = get_bedrock_client()
        if not client:
            return None

        resp = client.invoke_model(
            modelId=BEDROCK_MODEL_ID,
            body=json.dumps({
                "prompt": prompt,
                "max_gen_len": 400,
            })
        )
        result = json.loads(resp["body"].read())
        text = result.get("generation", "").strip()

        # Extract the first complete JSON object
        start = text.find("{")
        if start == -1:
            return None
        depth = 0
        end = -1
        in_string = False
        escape = False
        for i in range(start, len(text)):
            ch = text[i]
            if escape:
                escape = False
                continue
            if ch == "\\":
                escape = True
                continue
            if ch == '"':
                in_string = not in_string
            if not in_string:
                if ch == "{":
                    depth += 1
                elif ch == "}":
                    depth -= 1
                    if depth == 0:
                        end = i + 1
                        break
        if end == -1:
            return None

        json_str = text[start:end]
        parsed = json.loads(json_str)
        return {
            "recommended": parsed.get("recommended"),
            "reasoning": parsed.get("reasoning", ""),
            "rankings": parsed.get("rankings", []),
        }
    except (ClientError, Exception):
        return None
