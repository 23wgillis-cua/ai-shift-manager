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

One core loop, nothing else:

1. **Manager types a plain-English note** ("Mike has a funeral Wednesday and can't come to work")
2. **Manager approves the swap** (picks who covers)
3. **App emails the people who need to know**

Everything else is roadmap.

## Tech Stack

- Backend: Python (Flask)
- Database: SQLite (prototype), PostgreSQL (production)
- Frontend: HTML/CSS/JavaScript
- AI: LLM API for natural language to structured data parsing
- Hosting: AWS Free Tier
- Version Control: GitHub (this repo)

## Status

Built as part of the CUA AI Vibe Coding Competition. Work in progress.
