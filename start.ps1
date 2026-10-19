$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
if (-not (Test-Path -LiteralPath '.venv\Scripts\python.exe')) {
    python -m venv .venv
    if ($LASTEXITCODE -ne 0) { throw 'Could not create the virtual environment.' }
}
if (-not (Test-Path -LiteralPath '.env')) {
    Copy-Item -LiteralPath '.env.example' -Destination '.env'
    & .\.venv\Scripts\python.exe -c "from pathlib import Path; import secrets; p=Path('.env'); p.write_text(p.read_text().replace('replace-with-a-random-secret',secrets.token_urlsafe(64)))"
}
& .\.venv\Scripts\python.exe -m pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) { throw 'Could not install Python dependencies.' }
if (-not (Test-Path -LiteralPath 'static\css\app.css')) {
    npm ci
    if ($LASTEXITCODE -ne 0) { throw 'Could not install CSS dependencies.' }
    npm run build:css
    if ($LASTEXITCODE -ne 0) { throw 'CSS build failed.' }
}
& .\.venv\Scripts\python.exe manage.py migrate
if ($LASTEXITCODE -ne 0) { throw 'Database setup failed.' }
& .\.venv\Scripts\python.exe manage.py runserver 127.0.0.1:8002
