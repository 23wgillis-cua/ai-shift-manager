# AI Shift Manager - CUA AI Vibe Coding Competition Fall 2026

## Problem
Shift supervisors in 24/7 security operations spend hours manually managing schedule changes. When an employee calls out, the supervisor must find coverage, update the schedule, and notify multiple stakeholders by email or text. This is repetitive, error-prone work that takes time away from actually managing the operation.

## AI Solution
A web app that takes plain-English notes from a supervisor ("Mike has a funeral Wednesday"), uses an LLM to parse them into structured scheduling constraints, suggests available employees based on their logged preferences and availability, and then handles the outreach automatically: coverage offers go out by email and SMS with one-click Accept / Decline links, and each decline advances the offer to the next best-fit candidate until the shift is covered. The LLM's ranked recommendation is not a passive suggestion card; it directly determines the offer order of the cascade.

## Why AWS Bedrock Over OpenAI
I chose AWS Bedrock with Llama 3 8B for two reasons. First, the app is already deployed on AWS Elastic Beanstalk, so using Bedrock keeps everything in the same ecosystem. The IAM role on the EC2 instance already has Bedrock permissions, so there are no API keys to manage or rotate. Second, Bedrock is HIPAA-eligible and operates within AWS's compliance boundary, which matters for a tool designed for healthcare security teams. OpenAI would require an API key in the codebase or an environment variable, adding a secret management burden that a prototype should not have.

## Why SQLite Over PostgreSQL for the Prototype
SQLite is the right choice for a single-instance Elastic Beanstalk prototype. The app runs on a t3.micro with 1GB of RAM, and SQLite is file-based with zero configuration. The schema is designed with PostgreSQL compatibility in mind: all columns use standard SQL types (TEXT, INTEGER) that port directly. The migration path to PostgreSQL would involve changing the connection string and adding connection pooling, which is a configuration change, not a schema rewrite.

## Tradeoffs

~~The biggest tradeoff is the self-signed SSL certificate.~~ This was resolved: the app now serves a trusted Let's Encrypt certificate on a free DuckDNS domain (aishiftmanager.duckdns.org), so browsers show no warning. The remaining tradeoff is certificate lifecycle: Let's Encrypt certs expire every 90 days and must be renewed on the instance, unlike an ACM certificate which would renew automatically. For a production deployment, I would register a custom domain and use ACM with an Application Load Balancer to eliminate manual renewal entirely.

The LLM has a regex fallback for note parsing. If Bedrock is unavailable or returns invalid JSON, the regex parser extracts who/what/when/urgency using keyword matching. This is less accurate than the LLM but ensures the app never breaks on a bad API response. The tradeoff is accuracy vs reliability. The same philosophy applies to the coverage cascade: if the LLM ranking is unavailable, the cascade falls back to a deterministic order (availability filter, then fewest recent assignments), so coverage offers always go out even when the AI is down.

The coverage cascade uses token-based public links for Accept / Decline. This is a deliberate tradeoff: no login is required for employees to respond (a 2 AM offer gets answered in one tap), but it means anyone with the link can respond. Tokens are 32-byte cryptographic random values, offers are single-use, and a link that is already handled shows a neutral "already responded" page. For production I would add link expiry and bind offers to a per-employee secret.

Conflict detection on accept compares parsed day strings (e.g. "friday"). This is deliberately conservative: it only blocks accepts with an exact same-day match on already-approved coverage. A production system would compare actual dates and times from a real shift schedule rather than parsed note fields.

## What I Would Build Next
- Offer expiry: pending coverage offers never time out. A sweep that auto-declines offers after N hours and advances the cascade would close the gap between "emailed" and "answered."
- Multi-site support: the current schema is single-tenant. A site_id column on every table would enable multi-property security companies.
- Recurring shift generation: the shift_templates table exists but the template engine is basic. A proper cron-like syntax with conflict detection would let supervisors set up a week of shifts in one action.
- Mobile app: the app is now an installable PWA (web app manifest, home-screen icon, full-screen launch), which covers the phone-first workflow. A native app would add push notifications, which the web platform cannot do on iOS.
- RBAC: the current auth is login-or-not. Real role-based access control would let supervisors see only their team's notes while admins see everything.

## Target User
Shift supervisors and managers in security, healthcare, facilities, and other 24/7 operations. The supervisor types or speaks notes throughout the day as they come in.

## Success Criteria
- Supervisor types a natural language note and it is logged as a constraint
- System suggests who is available based on constraints and preferences
- Supervisor can let the system handle outreach: ranked offers go out by email and SMS, declines advance automatically, and conflicts are blocked
- Deployed live on AWS behind a working login with trusted HTTPS, installable as a PWA
