# AI Shift Manager

![CI](https://github.com/23wgillis-cua/ai-shift-manager/actions/workflows/ci.yml/badge.svg)

**Live app:** https://aishiftmanager.duckdns.org

**Tech stack:** Python (Flask), SQLite, AWS SES, AWS Elastic Beanstalk, GitHub

An AI-powered shift scheduling application for shift supervisors and managers, built for the Catholic University of America AI Vibe Coding Competition (Fall 2026).

## The Problem

Shift supervisors, especially in security operations that need 24/7/365 coverage, spend hours every week managing schedule changes. When someone calls out, the supervisor has to figure out who can cover, manually update the schedule, and then email or text everyone who needs to know. It is a repetitive, tedious process that nobody wants to deal with.

## The Solution

A web app where a supervisor types a plain-English note ("Mike has a funeral Wednesday and can't come to work"), the AI parses it into a structured scheduling constraint, suggests available employees based on logged availability preferences, and sends notifications to everyone who needs to know once a swap is approved.

## Target User

Shift supervisors and managers in security, healthcare, facilities, and other 24/7 operations.

## Success Criteria

- Supervisor can type a natural language note and have it logged as a scheduling constraint
- System suggests available employees based on logged constraints and preferences
- Supervisor can approve a shift swap and trigger automatic notifications
- App is deployed live on AWS with a working login

## Tech Stack

- Backend: Python (Flask)
- Database: SQLite (prototype), PostgreSQL (production)
- Frontend: HTML/CSS/JavaScript
- AI: AWS Bedrock (Llama 3 8B) for note parsing and coverage recommendations, with regex fallback
- Email: AWS SES for swap approval notifications
- Hosting: AWS Elastic Beanstalk (t3.micro, Free Tier)
- Version Control: GitHub (this repo)
- CI: GitHub Actions (pytest on every push)

## Architecture

```
Browser (HTTPS)
  |
  v
nginx (port 443 SSL -> port 80 -> port 8000)
  |
  v
Flask App (gunicorn, port 8000)
  |
  +-- SQLite (shiftmanager.db)
  |     users, notes, employees, audit_log, shift_templates
  |
  +-- AWS Bedrock (Llama 3 8B)
  |     note parsing -> who/what/when/urgency
  |     coverage recommendation -> ranked candidates + reasoning
  |
  +-- AWS SES
  |     swap approval -> email to assigned employee
  |
  +-- AWS SNS
        swap approval -> SMS to assigned employee
```

## Rubric Alignment

| Category | Points | How This Repo Addresses It |
| --- | --- | --- |
| Problem Definition & Relevance | 10 | Real pain point for 24/7 security operations supervisors. Built from firsthand police and security experience managing shift coverage. |
| AI Feature Innovation & Integration | 20 | Two-stage AI pipeline: (1) AWS Bedrock LLM (Llama 3) parses plain-English notes into structured JSON (who, what, when, urgency) with regex fallback, (2) same LLM reasons through coverage recommendations by weighing availability, workload distribution, and role fit, returning ranked candidates with 1-10 scores and natural-language reasoning. |
| Technical Execution & Code Quality | 20 | Flask app with SQLite database, session-based auth, AWS SES email integration, AWS Bedrock LLM integration, pytest test suite (28 tests), GitHub Actions CI pipeline. Shared base template with Jinja inheritance. Separate modules for note parsing, LLM integration, and route handling. |
| User Experience & Design | 10 | Dark-themed responsive UI with shared sticky nav bar, smooth hover transitions, auto-dismissing notifications, mobile media queries. Pages: Notes (with AI recommendation cards), Calendar (month grid with color-coded notes), Team (add/remove employees, set availability), Dashboard (stat cards + bar charts), Audit Log. |
| Business Impact & Scalability | 10 | Replaces hours of manual schedule juggling per week. Availability-aware coverage filtering excludes unavailable employees automatically. CSV export for reporting up the chain. Audit log for compliance. SQLite prototype with PostgreSQL production path. AWS Free Tier deployment. |
| GitHub Transparency | 10 | 41+ commits showing iterative build from skeleton to full-featured app. CI badge in README. Clean commit messages documenting each feature addition. Conventional commit format. |
| Documentation & Communication | 10 | This README with problem statement, solution, tech stack, rubric alignment, and demo credentials. THESIS.md with project rationale. Live app link and tech stack at the top of the README. |
| Deployment & Live Demo | 10 | Live at https://aishiftmanager.duckdns.org on AWS Elastic Beanstalk (t3.micro, Free Tier). HTTPS enabled on port 443 with a trusted Let's Encrypt certificate (DuckDNS domain), no browser warnings. Working login (demo/demo). Full swap flow: note input, AI parsing, coverage recommendation, approval, email notification. Calendar, dashboard, audit log, and CSV export all functional. |

## Demo Credentials

| URL | Credentials |
| --- | --- |
| https://aishiftmanager.duckdns.org | Username: `demo` / Password: `demo` |

Log in with the demo account and try the full flow: type a shift note, see the AI parse it into who/what/when/urgency, get a coverage recommendation from the LLM, and approve a swap. The demo account logs email notifications instead of sending real email; the admin account (separate password, not in this repo) sends real SES emails.

## Demo Walkthrough (5 minutes)

1. **Log in** at https://aishiftmanager.duckdns.org with username `demo` and password `demo`.

2. **Notes page** - You will see 6 pre-loaded shift notes. Some are approved (green left border), some are open (blue left border). Each note shows the AI-parsed fields: who, reason, when, urgency.

3. **Type a new note** - In the "What happened?" box, type something like: `Sarah has a family emergency Friday and needs coverage`. Click Save Note. The AI will parse it into who/what/when/urgency automatically.

4. **AI Recommendation** - Scroll to the new open note. If the AI recommendation is available, you will see a blue "AI Recommendation" card with a suggested employee, reasoning, and ranked candidates with 1-10 scores.

5. **Approve a swap** - Click the dropdown next to an open note, select an employee, and click Approve Swap. The note turns green and shows "Assigned to."

6. **Calendar** - Click Calendar in the nav bar. See notes placed on the calendar grid by day of week, color-coded open (green) vs approved (blue).

7. **Dashboard** - Click Dashboard. See stat cards (total/open/approved/employees), a day-of-week heatmap, callout reason breakdown, and coverage assignment bar charts. Click "Export notes as CSV" to download all notes.

8. **Team** - Click Team to add or remove employees, set unavailable days, and assign roles.

9. **Audit Log** - Click Audit Log to see every action logged with timestamps.

## License

MIT License. See [LICENSE](LICENSE) for details.

## Status

Built as part of the CUA AI Vibe Coding Competition (Fall 2026). MVP complete: login, note input, swap approval, and email notifications all working live on AWS.
