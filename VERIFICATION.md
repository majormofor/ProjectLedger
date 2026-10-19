# Verification — 19 October 2026

Created as a new sibling folder. The original Project Tracker app was not modified or migrated.

- Created an independent virtual environment and installed Python dependencies.
- Created and ran the initial database migration successfully.
- All 23 Django tests passed, including costs/balances, the four-field workflow, ownership, validation, sign-in/sign-out, client read-only access, revoked links and CSRF rules.
- Django system check passed. Production-mode `check --deploy` passed with no issues. No pending model changes were detected.
- Tailwind production CSS built successfully. Static collection succeeded. npm audit reported zero vulnerabilities.
- Browser verification succeeded against the actual running app: demo sign-in, add a subproject with cost/paid/date, correct live balance preview, saved project totals, prefilled four-field editing, updated cumulative payment without double counting, client link creation and read-only client display.
- Narrow-screen table layout was reviewed and changed to cards at 800px and below. Summary cards were compacted so the entry form is easier to reach.

The simplified app is served locally at http://127.0.0.1:8002/. It has a separate SQLite database and new demo credentials. No production deployment or original-account import was performed. Production hosting/PostgreSQL concurrency remain unverified.

## Notifications and project deletion follow-up

All 40 tests passed. Added tests for mail recipient/content, after-commit sending, rollback suppression, failed-send retry, missing Gmail credentials, project-only deletion, owner/CSRF restrictions, hidden totals, client-link revocation, retained financial records and Undo. Tests used an in-memory mail backend; no real email was sent. Gmail sender settings and recipient are configured locally, but EMAIL_HOST_PASSWORD is still missing.

## Live Gmail connection

On 19 October 2026, configured the supplied app password locally without printing it. Port 587 timed out; port 465 SSL worked. Gmail accepted one test email to the configured recipient. Restarted the application to load the sender credentials. Older queued notifications were not flushed. SMTP acceptance does not confirm inbox placement.
