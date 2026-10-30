# WordPath

A vocabulary-learning web app for Chinese speakers learning English, with spaced-repetition review (FSRS), meaning / spelling / listening quizzes, and learning statistics.

> Work in progress — MVP target: mid-November 2026.

## Tech stack

- **Frontend:** React, TypeScript, Vite, Tailwind CSS
- **Backend:** Python, FastAPI, SQLAlchemy, Alembic
- **Database:** PostgreSQL
- **Tooling:** Docker Compose, GitHub Actions, pytest, Vitest

## Run the backend locally

Start PostgreSQL (needs Docker Desktop):

```bash
cp .env.example .env   # first time only
docker compose up -d db
```

Then set up the backend and create the tables:

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload
```

Then open http://localhost:8000/docs.

## Run tests

```bash
cd backend
pytest
```
