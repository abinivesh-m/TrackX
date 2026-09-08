# Deploying TrackX (Render)

Chosen approach: **one single Render web service** runs the FastAPI backend,
which also serves the built React frontend as static files (see the
SPA-fallback route in `backend/app/main.py`). This avoids running two
deployed services and coordinating CORS between them under time pressure.
`render.yaml` in the repo root describes the build/start commands as a
Render "Blueprint" - it contains no secrets.

**No deployment has been performed by Claude.** Nothing here has been
deployed or connected to any Render/Railway account - this is preparation
only. Deploying requires an account and (if you want a persistent public
URL) a payment method on Render's side, which only you can provide.

## Steps

1. Push this repo to GitHub (Render deploys from a Git repo).
2. In the Render dashboard: **New > Blueprint**, point it at this repo.
   Render reads `render.yaml` automatically.
3. Before the first deploy, set these environment variables in Render's
   dashboard (Environment tab) - **do not** put real values in
   `render.yaml` or any committed file:
   - `SECRET_KEY` - a real random 64+ character string. The app runs with a
     well-known default otherwise (`backend/app/core/config.py`), which is
     fine for local development but not for anything public.
   - `FIRST_SUPERUSER` / `FIRST_SUPERUSER_PASSWORD` - real admin login
     credentials for the deployed instance, if you want an admin account
     bootstrapped automatically (see the ENVIRONMENT note below).
4. Deploy. First build installs both Python requirement files and builds
   the frontend (`render.yaml`'s `buildCommand`); the start command runs
   uvicorn against the built app.

## Two things you need to decide, not defaults Claude picked for you

**`ENVIRONMENT` and the bootstrap admin account.** `backend/app/main.py`'s
startup only creates the `FIRST_SUPERUSER` admin account when
`ENVIRONMENT != "production"` (a deliberate existing safeguard - a public
production deploy shouldn't auto-create an admin account from possibly
still-default credentials). `render.yaml` sets `ENVIRONMENT=production`,
which means **no admin account is auto-created** on deploy. For a judged
demo where you need to log in as an admin:
- Either set `ENVIRONMENT` to something other than `production` (e.g.
  `staging`) in Render's dashboard so the bootstrap admin account is
  created from your `FIRST_SUPERUSER`/`FIRST_SUPERUSER_PASSWORD` values, or
- Register a normal account through the app and use it as a non-admin
  operator account for the demo (public registration can no longer grant
  admin - see the Phase 14 fix in `backend/app/api/v1/auth.py` - so this
  path genuinely cannot self-escalate).

Neither option was chosen for you; pick whichever fits how you want the
demo to go.

**Ephemeral disk.** Render's free tier disk is wiped on every restart and
redeploy, including the SQLite database this app's demo data lives in.
`AUTO_SEED_DEMO_DATA=true` (already set in `render.yaml`) re-runs the same
seeding `python -m demo.seed_demo_data --reset` does, on every startup, so
a fresh deploy always comes up with the documented demo dataset (84
observations, 2 blacklist entries, 2 congested cameras - see
`DEMO_RUNBOOK.md`) instead of an empty database. If you later add a paid
persistent disk or a real Postgres database (`DATABASE_URL`), turn
`AUTO_SEED_DEMO_DATA` off so it stops overwriting real data on every
restart.

## Correction: other deployment files DO already exist in this repo

An earlier version of this document said no Render/Railway/Docker
configuration existed anywhere in the repo before `render.yaml` was added.
That was **wrong** - it was checked against a copy of the repo that had
diverged from your real checkout. Your actual folder also has:

- `railway.json` (repo root) - a minimal Railway builder config
  (`NIXPACKS`, healthcheck at `/api/v1/health/`).
- `docker-compose.yml` / `docker-compose.prod.yml` (repo root),
  `backend/Dockerfile`, `.dockerignore` - a Docker/Postgres-oriented setup.
- `backend/start.sh` - an entrypoint that branches between SQLite and
  PostgreSQL, runs Alembic migrations, then starts uvicorn on port 8000.
- `backend/render_main.py` - this one was actively dangerous: it was a
  **second, fake FastAPI app** ("No database - returns demo data for
  frontend") with hardcoded plates and randomly-generated timestamps, not
  wired into anything real. If it were ever deployed instead of
  `backend/app/main.py`, it would silently serve 100% fabricated data
  under a real-looking API. It has been overwritten with a stub that
  raises `RuntimeError` on import instead, so it can no longer run by
  accident - the old fake-data content is only recoverable from git
  history now. **Recommend deleting this file entirely** once you confirm
  nothing references it (`grep -r render_main` across the repo).
- Three more `requirements*.txt` variants beyond the root two already
  documented below: `backend/requirements-prod.txt` (a 3-package stub),
  `backend/requirements-render.txt` (2 packages), and a root
  `requirements-prod.txt` that pins **`easyocr`** - this codebase actually
  uses **PaddleOCR** (`recognition/ocr_reader.py`), not EasyOCR, so this
  file's dependency list does not match what the app imports. It also
  assumes PostgreSQL, while every real test this session ran used SQLite.

**Why these are not the recommended path for tomorrow:** they appear to
be from an earlier, different deployment attempt than the one this
session's actual fixes were built and tested against (PaddleOCR + SQLite +
`backend/app/main.py`). Using them as-is would very likely fail (wrong OCR
package, Postgres wiring the app doesn't require) or, worse, deploy the
fake-data `render_main.py` by mistake. They have been **left in place, not
deleted** (deleting them outright needs your confirmation), but the
`render.yaml` + single-Python-service path documented above is the one
that has actually been built, built-tested (`npm run build` succeeded),
and backend-tested (251/251 tests passing) this session. If you want the
Docker/Railway path instead, it needs its own verification pass before
tomorrow - there wasn't time to also test that path for real.

## Known limitations of this deployment, honestly

- The two `requirements.txt` files (repo root and `backend/`) have
  overlapping packages pinned to different versions (e.g. `ultralytics`,
  `paddleocr`, `opencv-python`, `numpy`). This already exists in the
  current working local setup and was **not** touched here - reconciling
  it is real, worthwhile cleanup but riskier to do blind right before a
  deadline than to leave alone. If Render's build fails on a dependency
  conflict, this is the first place to look.
- This has **not been tested on Render itself** (no deploy was performed -
  see above). It has been tested locally: the FastAPI app was started with
  a real production build of the frontend present, and `GET /`,
  `GET /dashboard` (a client-side route), `GET /assets/...`, and
  `GET /api/v1/...` were all confirmed to return the right thing from the
  same process. Render-specific issues (build timeouts on the free tier,
  cold starts, the ML dependencies' install size) are realistic risks that
  only an actual deploy will surface.
