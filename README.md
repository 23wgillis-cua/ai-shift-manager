# AI Shift Manager

![CI](https://github.com/23wgillis-cua/ai-shift-manager/actions/workflows/ci.yml/badge.svg)

**Live app:** http://ai-shift-manager.us-east-1.elasticbeanstalk.com

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
- AI: LLM API for natural language to structured data parsing
- Hosting: AWS Free Tier
- Version Control: GitHub (this repo)

## Rubric Alignment

| Category | Points | How This Repo Addresses It |
| --- | --- | --- |
| Problem Definition & Relevance | 10 | Real pain point for 24/7 security operations supervisors. Built from firsthand experience as a DC MPD Special Police Officer managing shift coverage at MedStar Washington Hospital Center. |
| AI Feature Innovation & Integration | 20 | Two-stage AI pipeline: (1) AWS Bedrock LLM (Llama 3) parses plain-English notes into structured JSON (who, what, when, urgency) with regex fallback, (2) same LLM reasons through coverage recommendations by weighing availability, workload distribution, and role fit, returning ranked candidates with 1-10 scores and natural-language reasoning. |
| Technical Execution & Code Quality | 20 | Flask app with SQLite database, session-based auth, AWS SES email integration, AWS Bedrock LLM integration, pytest test suite (12 tests), GitHub Actions CI pipeline. Shared base template with Jinja inheritance. Separate modules for note parsing, LLM integration, and route handling. |
| User Experience & Design | 10 | Dark-themed responsive UI with shared sticky nav bar, smooth hover transitions, auto-dismissing notifications, mobile media queries. Pages: Notes (with AI recommendation cards), Calendar (month grid with color-coded notes), Team (add/remove employees, set availability), Dashboard (stat cards + bar charts), Audit Log. |
| Business Impact & Scalability | 10 | Replaces hours of manual schedule juggling per week. Availability-aware coverage filtering excludes unavailable employees automatically. CSV export for reporting up the chain. Audit log for compliance. SQLite prototype with PostgreSQL production path. AWS Free Tier deployment. |
| GitHub Transparency | 10 | 31+ commits showing iterative build from skeleton to full-featured app. CI badge in README. Clean commit messages documenting each feature addition. Conventional commit format. |
| Documentation & Communication | 10 | This README with problem statement, solution, tech stack, rubric alignment, and demo credentials. THESIS.md with project rationale. Live app link and tech stack at the top of the README. |
| Deployment & Live Demo | 10 | Live at http://ai-shift-manager.us-east-1.elasticbeanstalk.com on AWS Elastic Beanstalk (t3.micro, Free Tier). Working login (admin/admin). Full swap flow: note input, AI parsing, coverage recommendation, approval, email notification. Calendar, dashboard, audit log, and CSV export all functional. |

## Demo Credentials

| URL | Credentials |
| --- | --- |
| http://ai-shift-manager.us-east-1.elasticbeanstalk.com | Username: `admin` / Password: `admin` |

Log in with the demo account and try the full flow: type a shift note, see the AI parse it into who/what/when/urgency, get a coverage recommendation from the LLM, approve a swap, and an email notification goes out via AWS SES.

## Status

Built as part of the CUA AI Vibe Coding Competition (Fall 2026). MVP complete: login, note input, swap approval, and email notifications all working live on AWS.
