<!-- Project overview, architecture, and setup instructions. -->

# Quiz-Forge
AI-Powered Knowledge Quiz Builder

## MVP overview
- Web-based quiz generator that turns a short topic into 5 multiple-choice questions
- 4 options per question, 1 correct answer, with feedback and explanations
- Quiz results include score, correct answers, and a review list
- Past quizzes are stored and listed per user

## Architecture notes
See `docs/architecture.md` for system architecture, request/response flow, data model
notes, and manual Postgres queries.

## Technical decisions and tradeoffs
- FastAPI keeps the API surface small while supporting typed request/response models; a
  Flask app would be lighter but less structured, and Django would add more ORM and
  admin overhead than needed for this MVP.
- Postgres + SQLAlchemy provides durable quiz history and result snapshots; SQLite
  would simplify local setup but is less suitable for concurrent usage or production
  migrations.
- The selected provider API is used when available; OpenAI chat completions remains
  a fallback to keep compatibility with older SDKs. A self-hosted model would reduce
  vendor dependency but adds deployment and latency complexity.
- AI generation supports either OpenAI or Claude via `AI_PROVIDER` so teams can use
  existing accounts; this improves portability but adds configuration complexity.
- Quiz content is normalized server-side to guarantee 5 questions, 4 options, and a
  stable schema for the frontend; letting the frontend normalize would reduce backend
  logic but risks inconsistent validation and data integrity.
- Results are snapshotted at completion to avoid recomputation and simplify review;
  recomputing on demand would save storage but can drift if content changes later.

## Local setup
1. Create a virtual environment:
   - `python3 -m venv .venv`
   - `source .venv/bin/activate`
2. Install dependencies:
   - `pip install -r backend/requirements.txt -r backend/requirements-dev.txt`
3. Create a local env file:
   - `cp .env.example .env`
   - Set `AI_PROVIDER` to `openai` or `claude` (defaults to `openai`).
   - Update `OPENAI_API_KEY` or `CLAUDE_API_KEY` plus optional model vars.
   - Update database URLs as needed.
   - `.env` is auto-loaded when the API starts.
4. Start Postgres (Homebrew example):
   - `brew install postgresql@16`
   - `brew services start postgresql@16`
5. Create a test database:
   - `/opt/homebrew/opt/postgresql@16/bin/createdb quiz_forge_test`
6. Run tests:
   - `TEST_DATABASE_URL=postgresql+psycopg://localhost/quiz_forge_test pytest`
7. Run the API:
   - `DATABASE_URL=postgresql+psycopg://localhost/quiz_forge uvicorn app.main:app --reload --app-dir backend`
8. Troubleshoot issues:
   - Check API logs in the terminal running Uvicorn.
   - Verify the API responds: `curl -i http://127.0.0.1:8000/docs`
   - Confirm `.env` is loaded: `python -c "import os; print(os.getenv('AI_PROVIDER'), bool(os.getenv('OPENAI_API_KEY') or os.getenv('CLAUDE_API_KEY')))"`.
   - Confirm Postgres is running: `brew services list | rg postgresql` (or `psql -h localhost -d quiz_forge -c 'select 1'`).
   - See what is listening on port 8000: `lsof -nP -iTCP:8000 -sTCP:LISTEN`
   - Stop the process: `kill <PID>`
   - Run on a different port: `uvicorn app.main:app --reload --app-dir backend --port 8001`

## Frontend usage
1. Serve the frontend (from the repo root):
   - `python3 -m http.server --directory frontend 5173`
2. Open `http://localhost:5173/index.html` in a browser.

## API flow (high level)
1. Create account: `POST /users`
2. Log in: `POST /sessions`
3. Generate quiz: `POST /quizzes/generate`
4. Answer questions: `POST /quizzes/{quiz_id}/answers`
5. View results: `GET /quizzes/{quiz_id}/results`
6. Browse history: `GET /quizzes?user_id=...`
