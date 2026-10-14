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
