# WordPath

[![CI](https://github.com/yinqicheng66-tech/wordpath/actions/workflows/ci.yml/badge.svg)](https://github.com/yinqicheng66-tech/wordpath/actions/workflows/ci.yml)

A vocabulary-learning web app for Chinese speakers learning English, with spaced-repetition review (FSRS), meaning / spelling / listening quizzes, and learning statistics.

**Live demo: https://wordpath-bice.vercel.app** (the backend runs on a free plan and may take ~50 s to wake up on the first request)

### Highlights

- **FSRS-6 spaced repetition**, ported from the reference implementation (py-fsrs) to dependency-free pure functions that run on Python 3.9, and checked against it on 25,000+ reviews
- **Ratings inferred from response time**: fast correct answers stretch the next interval, slow ones shorten it, with no extra clicks
- **9 word books, 14,624 words** cleaned from the open ECDICT dictionary; advanced books put words the learner already knows from easier syllabuses last
- **103 backend tests** and a frontend build check on every push (GitHub Actions)

## Tech stack

- **Frontend:** React, TypeScript, Vite, plain CSS (light and dark themes)
- **Backend:** Python, FastAPI, SQLAlchemy, Alembic
- **Database:** PostgreSQL (Neon in production)
- **Hosting:** Vercel (frontend), Render (backend)
- **Tooling:** pytest, TypeScript strict mode, GitHub Actions

## Run the backend locally

1. Start PostgreSQL. On macOS the easiest way is [Postgres.app](https://postgresapp.com)
   (click **Initialize**), then create the database:

   ```bash
   psql -d postgres -c "CREATE USER wordpath WITH PASSWORD 'wordpath';" -c "CREATE DATABASE wordpath OWNER wordpath;"
   ```

   Alternatively, with Docker: `docker compose up -d db`.

2. Set up the backend, create the tables and load the word list:

   ```bash
   cp .env.example .env   # first time only, from the repo root
   cd backend
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   alembic upgrade head
   python -m app.importer
   uvicorn app.main:app --reload
   ```

Then open http://localhost:8000/docs.

3. In a second terminal, start the frontend:

   ```bash
   cd frontend
   npm install   # first time only
   npm run dev
   ```

   Open http://localhost:5173. Requests to `/api` are forwarded to the backend on port 8000.

## Deploy

| Part | Host | Settings |
| --- | --- | --- |
| Database | [Neon](https://neon.tech) (free Postgres) | copy the connection string |
| Backend | [Render](https://render.com) | New → Blueprint, pick this repo (`render.yaml`); set `DATABASE_URL` and `CORS_ORIGINS` |
| Frontend | [Vercel](https://vercel.com) | Root directory `frontend`; environment variable `VITE_API_URL` = the Render URL |

The backend runs migrations and imports the word books every time it starts.
Render's free plan sleeps after 15 minutes without traffic, so the first request
after a pause takes about a minute.

## Run tests

```bash
cd backend
pytest
```

## Data

The word list in `backend/data/core_1000.csv` is the 1000 most frequent CET-4 words
from [ECDICT](https://github.com/skywind3000/ECDICT) (MIT License, see
`backend/data/ECDICT_LICENSE`), with translations trimmed for flashcards by
`backend/app/wordbank.py`. To rebuild it: `python -m app.importer --from-ecdict path/to/ecdict.csv`.
