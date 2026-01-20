<!-- Project overview, architecture, and setup instructions. -->

# Quiz-Forge
AI-Powered Knowledge Quiz Builder

## MVP overview
- Web-based quiz generator that turns a short topic into 5 multiple-choice questions
- 4 options per question, 1 correct answer, with feedback and explanations
- Quiz results include score, correct answers, and a review list
- Past quizzes are stored and listed per user

## System architecture
- Frontend: static HTML/CSS/JS pages in `frontend/` with localStorage session state
- Backend: FastAPI app in `backend/` with SQLAlchemy models and a Postgres database
- AI layer: OpenAI API called from `backend/app/quiz_generation.py` to create quizzes
- Retrieval: the model can use built-in web search plus a scrape tool to ground answers

## Manual Postgres access
- Connect with psql: `psql postgresql://postgres:postgres@localhost:5432/quiz_forge`
- List quizzes: `SELECT id, user_id, prompt, status, created_at FROM quizzes ORDER BY created_at DESC;`
- Inspect quiz content: `SELECT quiz_content FROM quizzes WHERE id = '<quiz_id>';`
- Review answers: `SELECT quiz_id, question_index, selected_option_key, is_correct FROM quiz_answers WHERE quiz_id = '<quiz_id>';`
- Query a user's score for a quiz: `SELECT user_id, correct_count, total_questions, score_percent FROM quizzes WHERE id = '<quiz_id>' AND user_id = '<user_id>';`

## Technical decisions and tradeoffs
- FastAPI keeps the API surface small while supporting typed request/response models; a
  Flask app would be lighter but less structured, and Django would add more ORM and
  admin overhead than needed for this MVP.
- Postgres + SQLAlchemy provides durable quiz history and result snapshots; SQLite
  would simplify local setup but is less suitable for concurrent usage or production
  migrations.
- OpenAI responses API is used when available; chat completions is a fallback to keep
  compatibility with older SDKs. A self-hosted model would reduce vendor dependency
  but adds deployment and latency complexity.
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
   - Update `OPENAI_API_KEY` and database URLs as needed.
4. Start Postgres (Homebrew example):
   - `brew install postgresql@16`
   - `brew services start postgresql@16`
5. Create a test database:
   - `/opt/homebrew/opt/postgresql@16/bin/createdb quiz_forge_test`
6. Run tests:
   - `TEST_DATABASE_URL=postgresql+psycopg://localhost/quiz_forge_test pytest`
7. Run the API:
   - `DATABASE_URL=postgresql+psycopg://localhost/quiz_forge uvicorn app.main:app --reload --app-dir backend`

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
