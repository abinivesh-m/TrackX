# Running TrackX Locally

This is the simplest path that actually works out of the box - no `.env`
file, no PostgreSQL, no Redis required. The app defaults to SQLite and
sane development settings (see `backend/app/core/config.py`); everything
below is exactly how this session ran and tested the app all along.

## 1. Backend (FastAPI)

```bash
# from the repo root
pip install -r requirements.txt -r backend/requirements.txt

cd backend
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

- API docs: http://localhost:8000/docs
- Health check: http://localhost:8000/api/v1/health/
- The SQLite database lives at `outputs/results/observations.db` (created
  automatically on first write) plus `backend/trackx.db` for
  users/cameras/road-network (created automatically by `init_db()` on
  startup). Neither needs to be created manually.

**Seed demo data** (optional, but the frontend looks empty without it):

```bash
# from the repo root, with the backend's venv active
python -m demo.seed_demo_data --reset
```

This writes the same dataset `DEMO_RUNBOOK.md` describes (real seeded
observations, a couple of blacklist entries, a couple of congested
cameras) so every page has real data to show instead of empty states.

**Create a login**: register a normal account via `POST /api/v1/auth/register`
(e.g. through `/docs`), or, if `ENVIRONMENT` is not set to `production`,
the app auto-creates a bootstrap admin account from
`FIRST_SUPERUSER` / `FIRST_SUPERUSER_PASSWORD` (defaults exist in
`backend/app/core/config.py` if you don't set your own - check there
rather than assuming, since shipping default admin credentials is a real
risk if this ever runs publicly with `ENVIRONMENT` unset).

## 2. Frontend (React + Vite)

```bash
cd frontend
npm install
npm run dev
```

- Opens at http://localhost:5173 (Vite's default) and talks to the
  backend at `http://localhost:8000/api/v1` by default (see
  `frontend/src/services/api.ts` / `frontend/.env.example` - copy that to
  `frontend/.env` only if you need to point at a different backend URL or
  a different map tile provider).

Log in with whichever account you created against the backend above.

## 3. Running both together (what a judge will actually do)

Two terminals: one running the backend command from step 1, one running
the frontend command from step 2. Nothing else needs to be started -
no separate database server, no message queue, no Docker.

## 4. Camera-folder AI Processing feature

The **AI Processing** page (sidebar) has a "Camera Media" tab that runs
the real detection/OCR pipeline on whatever images or videos already sit
in a camera's local folder, instead of requiring an upload every time.
To use it, drop files here before starting the backend (or anytime -
it's read fresh on each request):

```
data/cameras/<CAMERA_ID>/images/*.jpg|.jpeg|.png
data/cameras/<CAMERA_ID>/videos/*.mp4|.avi|.mov
```

`<CAMERA_ID>` must be one of the seven cameras in `network/camera_network.py`
(`CAM_01`..`CAM_07`). If a camera has no folder yet, the page honestly
reports "0 image(s), 0 video(s) available" rather than pretending there's
something to process - this is not currently populated with any sample
media in this checkout, so add real files there first.

You can also run the same pipeline from the command line without the UI:

```bash
python -m demo.visual_pipeline --camera CAM_01
```

## 5. Running the test suite

```bash
# from the repo root
python -m pytest tests backend/tests integration_tests -q
```

251 tests pass as of this session's last run (a handful are skipped, not
failed - that's expected, see the skip reasons if curious).

```bash
cd frontend
npm run typecheck   # tsc --noEmit
npm run build        # production build - must succeed before shipping
```
