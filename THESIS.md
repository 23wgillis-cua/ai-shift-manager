# AI Shift Manager - CUA AI Vibe Coding Competition Fall 2026

## Problem
Shift supervisors in 24/7 security operations spend hours manually managing schedule changes. When an employee calls out, the supervisor must find coverage, update the schedule, and notify multiple stakeholders by email or text. This is repetitive, error-prone work.

## AI Solution
A web app that takes plain-English notes from a supervisor ("Mike has a funeral Wednesday"), uses an LLM to parse them into structured scheduling constraints, suggests available employees based on their logged preferences and availability, and auto-sends notifications when a swap is approved.

## Target User
Shift supervisors and managers in security, healthcare, facilities, and other 24/7 operations. The supervisor types or speaks notes throughout the day as they come in.

## Success Criteria
- Supervisor types a natural language note and it is logged as a constraint
- System suggests who is available based on constraints and preferences
- Supervisor approves a swap and notifications go out automatically
- Deployed live on AWS behind a working login
