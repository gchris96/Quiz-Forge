<!-- System architecture, request/response flow, and data model notes. -->
# Architecture Notes

## Overview
- Frontend: static HTML/CSS/JS pages in `frontend/` with localStorage session state
- Backend: FastAPI app in `backend/` with SQLAlchemy models and a Postgres database
- AI layer: OpenAI API called from `backend/app/quiz_generation.py` to create quizzes
- Retrieval: the model can use built-in web search plus a scrape tool to ground answers

## Request/response flow
1. Signup: `POST /users` creates a user record and returns the user id.
2. Login: `POST /sessions` validates credentials and returns session data.
3. Generate quiz: `POST /quizzes/generate` validates prompt and stores quiz content.
4. Take quiz: `GET /quizzes/{quiz_id}` returns the public quiz payload without answers.
5. Submit answers: `POST /quizzes/{quiz_id}/answers` stores answers and computes results
   after the final question.
6. Results: `GET /quizzes/{quiz_id}/results` returns the immutable results snapshot.
7. History: `GET /quizzes?user_id=...` lists a user's past quizzes.

## Data model notes
- `users`: stores usernames and salted password hashes for authentication.
- `quizzes`: stores prompt, status, totals, full quiz content, public quiz view, and
  final results snapshot after completion.
- `quiz_answers`: stores per-question selections and correctness for a quiz.

## Manual Postgres access
- Connect with psql: `psql postgresql://postgres:postgres@localhost:5432/quiz_forge`
- List quizzes: `SELECT id, user_id, prompt, status, created_at FROM quizzes ORDER BY created_at DESC;`
- Inspect quiz content: `SELECT quiz_content FROM quizzes WHERE id = '<quiz_id>';`
- Review answers: `SELECT quiz_id, question_index, selected_option_key, is_correct FROM quiz_answers WHERE quiz_id = '<quiz_id>';`
- Query a user's score for a quiz: `SELECT user_id, correct_count, total_questions, score_percent FROM quizzes WHERE id = '<quiz_id>' AND user_id = '<user_id>';`


## Sequence Diagram

```
Browser        API             AI/Tools          Postgres
  |            |                  |                 |
  | POST /users|                  |                 |
  |----------->|                  |                 |
  |            |  INSERT users    |                 |
  |            |------------------------------->    |
  |            |<------------------------------|    |
  |<-----------|                  |                 |
  | POST /quizzes/generate         |                 |
  |----------->|                  |                 |
  |            |   call OpenAI + tools            |
  |            |----------------->|                 |
  |            |<-----------------|                 |
  |            | INSERT quizzes + content          |
  |            |------------------------------->    |
  |            |<------------------------------|    |
  |<-----------|                  |                 |
  | POST /quizzes/{id}/answers                     |
  |----------->|                  |                 |
  |            | INSERT quiz_answers               |
  |            |------------------------------->    |
  |            |<------------------------------|    |
  |            | (if last answer) UPDATE quizzes  |
  |            |------------------------------->    |
  |            |<------------------------------|    |
  |<-----------|                  |                 |
  | GET /quizzes/{id}/results                      |
  |----------->|                  |                 |
  |            | SELECT results_snapshot           |
  |            |------------------------------->    |
  |            |<------------------------------|    |
  |<-----------|                  |                 |
```

## Data model notes
