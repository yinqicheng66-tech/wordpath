# WordPath

A vocabulary-learning web app for Chinese speakers learning English, with spaced-repetition review (FSRS), meaning / spelling / listening quizzes, and learning statistics.

> Work in progress — MVP target: mid-November 2026.

## Tech stack

- **Frontend:** React, TypeScript, Vite, Tailwind CSS
- **Backend:** Python, FastAPI, SQLAlchemy, Alembic
- **Database:** PostgreSQL
- **Tooling:** Docker Compose, GitHub Actions, pytest, Vitest

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
