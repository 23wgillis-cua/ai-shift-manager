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
| AI Feature Innovation & Integration | 20 | Plain-English note input parsed into structured scheduling constraints. Manager types natural language ("Mike has a funeral Wednesday"), app logs it as a constraint and surfaces available employees for swap approval. |
| Technical Execution & Code Quality | 20 | Flask app with SQLite database, session-based auth, AWS SES email integration, pytest test suite (12 tests), GitHub Actions CI pipeline. Clean separation of routes, templates, and database layer. |
| User Experience & Design | 10 | Dark-themed responsive UI. Login flow, note input form, employee dropdown for swap approval, status badges (open/approved), email confirmation banners. Designed for the supervisor who needs to act fast. |
| Business Impact & Scalability | 10 | Replaces hours of manual schedule juggling per week. Scales from a single hospital security team to multi-site operations. SQLite prototype with PostgreSQL production path. AWS Free Tier deployment. |
| GitHub Transparency | 10 | Full commit history showing iterative build from skeleton to MVP. CI badge in README. Public repo with clean commit messages documenting each feature addition. |
| Documentation & Communication | 10 | This README with problem statement, solution, tech stack, and rubric alignment. THESIS.md with project rationale. Live app link at the top of the README. |
| Deployment & Live Demo | 10 | Live at http://ai-shift-manager.us-east-1.elasticbeanstalk.com on AWS Elastic Beanstalk (t3.micro, Free Tier). Working login (admin/admin). Full swap flow functional end to end. |

## Demo Credentials

| URL | Credentials |
| --- | --- |
| http://ai-shift-manager.us-east-1.elasticbeanstalk.com | Username: `admin` / Password: `admin` |

Log in with the demo account and try the full flow: type a shift note, see the AI parse it into who/what/when/urgency, get a coverage recommendation from the LLM, approve a swap, and an email notification goes out via AWS SES.

## Status

Built as part of the CUA AI Vibe Coding Competition (Fall 2026). MVP complete: login, note input, swap approval, and email notifications all working live on AWS.
