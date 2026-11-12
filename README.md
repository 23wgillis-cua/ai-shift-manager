# AI Shift Manager

![CI](https://github.com/23wgillis-cua/ai-shift-manager/actions/workflows/ci.yml/badge.svg)

**Live app:** https://aishiftmanager.duckdns.org

**Tech stack:** Python (Flask), SQLite, AWS SES, AWS Elastic Beanstalk, GitHub

An AI-powered shift scheduling application for shift supervisors and managers, built for the Catholic University of America AI Vibe Coding Competition (Fall 2026).

## The Problem

Shift supervisors, especially in security operations that need 24/7/365 coverage, spend hours every week managing schedule changes. When someone calls out, the supervisor has to figure out who can cover, manually update the schedule, and then email or text everyone who needs to know. It is a repetitive, tedious process that nobody wants to deal with.

## The Solution

A web app where a supervisor types a plain-English note ("Mike has a funeral Wednesday and can't come to work"), the AI parses it into a structured scheduling constraint, suggests available employees based on logged availability preferences, and handles the outreach: each coverage offer goes out by email and SMS with one-click Accept / Decline links, and a decline automatically advances the offer to the next best-fit candidate until someone accepts. The supervisor can also assign coverage manually, in which case notifications go out on approval.

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
- Email: AWS SES for swap approval notifications and coverage offers
- SMS: AWS SNS for coverage offers (Accept / Decline links)
- Hosting: AWS Elastic Beanstalk (t3.micro, Free Tier)
- Mobile: PWA (web app manifest, installable on iOS/Android home screens)
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
  |     users, notes, employees, audit_log, shift_templates, coverage_offers
  |
  +-- AWS Bedrock (Llama 3 8B)
  |     note parsing -> who/what/when/urgency
  |     coverage recommendation -> ranked candidates + reasoning
  |
  +-- AWS SES
  |     swap approval -> email to assigned employee
  |     coverage offers -> email with Accept / Decline links
  |
  +-- AWS SNS
        swap approval -> SMS to assigned employee
        coverage offers -> SMS with Accept / Decline links
```

## Coverage Cascade

The signature feature. For any open note, the supervisor clicks **Start coverage cascade** and the system:

1. Ranks candidates by best fit, using the LLM's ranked recommendations when available, with a deterministic fallback (availability filter + fewest recent assignments).
2. Emails and texts the top candidate an offer with unique one-click Accept and Decline links (no login required, token-based).
3. On **Accept**: the note is approved and assigned, all other pending offers are cancelled, and the audit log records it.
4. On **Decline**: the offer automatically advances to the next ranked candidate, and so on down the list.
5. Conflict detection: if the accepting employee is already approved for another shift on the same day, the accept is blocked with a clear explanation and the cascade advances instead of double-booking.
6. Every state transition (sent, accepted, declined, cancelled, conflict) is visible on the notes page and in the audit log.

## Rubric Alignment

| Category | Points | How This Repo Addresses It |
| --- | --- | --- |
| Problem Definition & Relevance | 10 | Real pain point for 24/7 security operations supervisors. Built from firsthand police and security experience managing shift coverage. |
| AI Feature Innovation & Integration | 20 | Two-stage AI pipeline: (1) AWS Bedrock LLM (Llama 3) parses plain-English notes into structured JSON (who, what, when, urgency) with regex fallback, (2) same LLM reasons through coverage recommendations by weighing availability, workload distribution, and role fit, returning ranked candidates with 1-10 scores and natural-language reasoning. The AI's ranking directly drives the coverage cascade, so the model's output has operational consequences, not just a suggestion card. |
| Technical Execution & Code Quality | 20 | Flask app with SQLite database, session-based auth, AWS SES/SNS integration, AWS Bedrock LLM integration, token-based public offer endpoints, same-day conflict detection, pytest test suite (42 tests), GitHub Actions CI pipeline. Shared base template with Jinja inheritance. Separate modules for note parsing, LLM integration, coverage cascade, notifications, and route handling. |
| User Experience & Design | 10 | Dark-themed responsive UI with landing-page hero, first-run onboarding tour, PWA manifest (installable on iOS/Android), sticky nav bar, smooth hover transitions, auto-dismissing notifications, mobile media queries. Pages: Notes (AI recommendation cards + cascade offer chain), Calendar (month grid with color-coded notes), Team (add/remove employees, set availability), Dashboard (stat cards + bar charts), Audit Log. Employees get a clean, branded response page for Accept/Decline with no login required. |
| Business Impact & Scalability | 10 | Replaces hours of manual schedule juggling per week. Availability-aware coverage filtering excludes unavailable employees automatically. CSV export for reporting up the chain. Audit log for compliance. SQLite prototype with PostgreSQL production path. AWS Free Tier deployment. |
| GitHub Transparency | 10 | 50+ commits showing iterative build from skeleton to full-featured app. CI badge in README. Clean commit messages documenting each feature addition. Conventional commit format. |
| Documentation & Communication | 10 | This README with problem statement, solution, tech stack, rubric alignment, and demo credentials. THESIS.md with project rationale. Live app link and tech stack at the top of the README. |
| Deployment & Live Demo | 10 | Live at https://aishiftmanager.duckdns.org on AWS Elastic Beanstalk (t3.micro, Free Tier). HTTPS enabled on port 443 with a trusted Let's Encrypt certificate (DuckDNS domain), no browser warnings. Working login (demo/demo). Full swap flow: note input, AI parsing, coverage recommendation, approval, email notification. Calendar, dashboard, audit log, and CSV export all functional. |

## Demo Credentials

| URL | Credentials |
| --- | --- |
| https://aishiftmanager.duckdns.org | Username: `demo` / Password: `demo` |

Log in with the demo account and try the full flow: type a shift note, see the AI parse it into who/what/when/urgency, get a coverage recommendation from the LLM, and approve a swap. The demo account logs email notifications instead of sending real email; the admin account (separate password, not in this repo) sends real SES emails.

## Demo Walkthrough (5 minutes)

1. **Log in** at https://aishiftmanager.duckdns.org with username `demo` and password `demo`. The login page's landing hero explains the product in one screen, and a first-run tour walks through the core loop.

2. **Notes page** - You will see 6 pre-loaded shift notes. Some are approved (green left border), some are open (blue left border). Each note shows the AI-parsed fields: who, reason, when, urgency.

3. **Type a new note** - In the "What happened?" box, type something like: `Sarah has a family emergency Friday and needs coverage`. Click Save Note. The AI will parse it into who/what/when/urgency automatically.

4. **AI Recommendation** - Scroll to the new open note. If the AI recommendation is available, you will see a blue "AI Recommendation" card with a suggested employee, reasoning, and ranked candidates with 1-10 scores.

5. **Start a coverage cascade** - Instead of assigning manually, click "Start coverage cascade" under the note. The system ranks candidates (AI ranking with a fairness fallback), and sends the top person an offer by email and SMS with Accept / Decline links. The notes page shows the live offer chain (sent / awaiting response). Because this is the demo account, offers are logged rather than actually sent, and the audit log records them.

6. **Decline advances automatically** - Declining an offer (the link an employee would click in their email or text) automatically sends the offer to the next ranked candidate. If the accepting employee already has a shift that day, the accept is blocked as a conflict and the cascade advances instead.

7. **Approve a swap manually** - Alternatively, use the dropdown next to an open note, select an employee, and click Approve Swap. The note turns green and shows "Assigned to."

8. **Calendar** - Click Calendar in the nav bar. See notes placed on the calendar grid by day of week, color-coded open (green) vs approved (blue).

9. **Dashboard** - Click Dashboard. See stat cards (total/open/approved/employees), a day-of-week heatmap, callout reason breakdown, and coverage assignment bar charts. Click "Export notes as CSV" to download all notes.

10. **Team** - Click Team to add or remove employees, set unavailable days, and assign roles.

11. **Audit Log** - Click Audit Log to see every action logged with timestamps: notes created, swaps approved, offers sent, accepted, declined, and conflict-blocked.

12. **Install it** - On a phone, open the site in Safari (iOS) or Chrome (Android) and use Add to Home Screen. The app installs as a PWA with its own icon and launches full-screen.

## License

MIT License. See [LICENSE](LICENSE) for details.

## Status

Built as part of the CUA AI Vibe Coding Competition (Fall 2026). Feature-complete for judging: login with landing hero, note input with AI parsing, AI-ranked coverage recommendations, coverage cascade with email/SMS accept-decline and automatic advance, same-day conflict detection, first-run onboarding tour, installable PWA, calendar, dashboard, audit log, and CSV export, all working live on AWS. 42 tests, CI on every push.
