# ProjectLedger Simple

A separate, simpler Django application. The original **Project Tracker** folder, database, accounts and code are unchanged. This app has its own database, environment, dependencies and cookie names.

## Open the local app

From this folder run:

```powershell
.\start.ps1
```

Open **http://127.0.0.1:8002/**. Sign in or create an account. Port 8002 keeps the original app on port 8000 independent.

For local development only, `python manage.py seed_demo` creates fictional sample records. Do not use the demo account on a public deployment. Existing accounts and project records are not included in this repository.

If scripts are restricted, use the existing installed environment directly:

```powershell
.\.venv\Scripts\python manage.py runserver 127.0.0.1:8002
```

## The simpler workflow

1. Create a project with a name, client name and optional location.
2. On its page, fill the five fields: **subproject name, type (Labour or Material), cost, amount paid so far, expected completion date**. Select Add.
3. The balance, project totals and latest completion date calculate immediately.
4. Choose Update paid beside a subproject to edit only the amount paid in a compact dialog. Name, type, cost and expected completion are locked after creation. Enter the cumulative amount paid so far; it replaces that figure rather than adding a second payment.
5. Create a client link and copy it. Clients see the project totals and subprojects without an account. They cannot edit. Disable sharing whenever needed.
6. Sign out from the top bar. Use Print summary for a readable paper copy.

There are no individual cost items, categories, receipt uploads, separate payment forms, progress questionnaires or long project forms. Changes to saved financial figures are retained in the owner-scoped database audit history without adding extra screens to the everyday workflow. No permanent deletion is exposed.

## Calculations

- Subproject balance = cost minus total paid, clamped at zero. Excess is displayed as credit/overpayment.
- Project cost and paid are sums of subproject figures. Project balance sums remaining subproject balances; overpaid credit is displayed separately instead of silently paying another subproject.
- Project completion is the latest expected subproject completion date. An empty project shows Not set yet.
- Past dates are labelled “Expected date has passed”; this version does not infer whether work is completed from payment amounts.
- All stored amounts use DecimalField and server validation. The live input preview is for convenience; server calculations are authoritative.

## Setup on another machine

Requires Python 3.12+; Node is needed only to rebuild CSS. Django 5.2, Django templates, locally compiled Tailwind CSS and small vanilla JavaScript helpers are used.

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.txt
Copy-Item .env.example .env
# Replace SECRET_KEY in .env with a long random value.
npm ci
npm run build:css
.\.venv\Scripts\python manage.py migrate
.\.venv\Scripts\python manage.py runserver 127.0.0.1:8002
```

Optional fictional sample projects: `python manage.py seed_demo`. It only runs in DEBUG mode and never changes an existing demo account. The included compiled CSS allows normal local startup without Node.

## Verification

```powershell
.\.venv\Scripts\python manage.py test
.\.venv\Scripts\python manage.py check
.\.venv\Scripts\python manage.py makemigrations --check --dry-run
npm run build:css
npm audit
```

The 40 tests cover account registration/sign-out, compact project/subproject creation, Decimal totals, updates without double counting, validation, overpaid credit, ownership, forged parent IDs, read-only clients, secure link revocation/regeneration, and local preview CSRF restrictions.

## Security and deployment notes

SQLite and Africa/Lagos are the local defaults. Production can use PostgreSQL via DATABASE_URL. Set DEBUG=False, a private random SECRET_KEY, ALLOWED_HOSTS and HTTPS CSRF_TRUSTED_ORIGINS. Use `python manage.py collectstatic --noinput` and `python manage.py migrate` before starting a WSGI server. Waitress is included; terminate TLS at a trusted reverse proxy. TRUST_PROXY=True is supported only when the proxy sanitises and writes X-Forwarded-Proto. Private responses are not cached. Configure production ingress rate limits; the built-in login limiter uses Django's process-local cache.

LOCAL_EMBEDDED_PREVIEW=True is set in the current ignored .env so the Codex in-app browser works. It only accepts an opaque/null origin in DEBUG mode over HTTP with loopback host and peer; correct CSRF cookie/token pairs remain mandatory. The distributed default is False and production always rejects the exception.

Client links are random access credentials. Django logs redact them; configure reverse-proxy logs to omit or redact them too. Client pages display only project/client names, optional location and subproject financial/date summaries.

This app is local and has not been deployed. Production PostgreSQL concurrency and hosting configuration need deployment verification.

Subproject type is required for new records. Existing unclassified records retain Not set. Saved name, type, cost and expected completion date are locked; only the amount paid can be updated. The type is also displayed in the read-only client table.

## Email notifications and project deletion

Gmail notifications can be configured privately in `.env`. See GMAIL_SETUP.md for setup and queued-email retries. Email failures do not undo saved changes. Hosting providers may restrict SMTP; verify email delivery on your chosen host.

Delete project is available on the project list, with confirmation and immediate Undo. It hides the project and revokes the client link while retaining financial records. Subprojects have no delete button.
