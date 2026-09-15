# AI Shift Manager

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

## MVP Scope (Minimum Viable Product)

The full platform includes note logging, AI suggestions, notifications, subscription billing, and security hardening. For the prototype, we are building only the core loop:

1. **Manager types a plain-English note** ("Mike has a funeral Wednesday and can't come to work")
2. **AI parses the note into a structured constraint** (employee, date, status, reason) and logs it
3. **System shows who is available** for the affected shift based on logged constraints and employee preferences
4. **Manager approves a swap** by selecting from the suggested available employees
5. **App fires off notifications** (email) to everyone who needs to know about the change

Everything else (subscription billing, multi-site support, SMS alerts, role-based access control, audit logs) is roadmap, not week-one build.

### MVP Data Model

- **Employees**: name, role, contact info, availability preferences (e.g., "takes kids to practice Wednesdays at 3")
- **Shifts**: date, start time, end time, assigned employee, role required
- **Constraints**: employee, date, type (unavailable, preference), reason, source note (raw text)
- **Notifications**: recipient, message, sent status, timestamp

### What Is Not in the MVP

- No subscription billing
- No multi-organization support
- No SMS notifications (email only for the prototype)
- No advanced reporting or analytics
- No mobile app (web only)
- No real authentication system beyond a working login

## Tech Stack

- Backend: Python (Flask)
- Database: SQLite (prototype), PostgreSQL (production)
- Frontend: HTML/CSS/JavaScript
- AI: LLM API for natural language to structured data parsing
- Hosting: AWS Free Tier
- Version Control: GitHub (this repo)

## Status

Built as part of the CUA AI Vibe Coding Competition. Work in progress.
