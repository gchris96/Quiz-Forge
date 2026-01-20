# FastAPI app, routes, and quiz flow handlers.
from copy import deepcopy
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Dict, List

import logging
import re

from fastapi import Depends, FastAPI, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import Base, engine, get_db
from app.models import Quiz, QuizAnswer, User
from app.quiz_generation import (
    ensure_prompt_coverage,
    generate_quiz_content,
    get_ai_api_key,
    get_ai_api_key_env_var,
    get_ai_provider,
)
from app.schemas import (
    AnswerCreate,
    AnswerOut,
    QuizCreate,
    QuizOut,
    QuizGenerateCreate,
    QuizPlaceholderCreate,
    QuizTakeOut,
    ResultsOut,
    SessionCreate,
    SessionOut,
    UserCreate,
    UserOut,
)
from app.security import generate_salt, hash_password


# Create database tables on app startup.
@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(title="Quiz Forge API", lifespan=lifespan)
logger = logging.getLogger("quiz_forge")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Format datetimes as ISO-8601 strings with UTC fallback.
def to_iso(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat()

# Validate and normalize quiz content to the expected schema.
def normalize_quiz_content(quiz_content: Dict) -> Dict:
    questions = quiz_content.get("questions")
    if not isinstance(questions, list) or not questions:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="quiz_content must include a non-empty questions array",
        )
    if len(questions) != 5:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="quiz_content must include exactly 5 questions",
        )
    normalized = deepcopy(quiz_content)
    normalized_questions: List[Dict] = []
    for idx, question in enumerate(questions, start=1):
        if not isinstance(question, dict):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="each question must be an object",
            )
        item = dict(question)
        options = item.get("options")
        if not isinstance(options, list) or len(options) != 4:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="each question must include 4 options",
            )
        option_keys = []
        for option in options:
            if not isinstance(option, dict):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="each option must include a key and text",
                )
            key = option.get("key")
            text = option.get("text")
            if not key or not text:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="each option must include a key and text",
                )
            option_keys.append(str(key))
        if len(set(option_keys)) != 4 or set(option_keys) != {"A", "B", "C", "D"}:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="options must use unique keys A-D",
            )
        correct_key = item.get("correct_option_key")
        if correct_key not in option_keys:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="correct_option_key must match one of the option keys",
            )
        item.setdefault("index", idx)
        normalized_questions.append(item)
    normalized["questions"] = normalized_questions
    return normalized

# Strip answer keys/explanations for the public quiz payload.
def build_quiz_public(quiz_content: Dict) -> Dict:
    public_content = deepcopy(quiz_content)
    for question in public_content.get("questions", []):
        question.pop("correct_option_key", None)
        question.pop("explanation", None)
    return public_content

# Fetch a question by its index or raise a validation error.
def question_by_index(quiz_content: Dict, question_index: int) -> Dict:
    for question in quiz_content.get("questions", []):
        if question.get("index") == question_index:
            return question
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="question_index not found",
    )

# Build an immutable results snapshot for completed quizzes.
def build_results_snapshot(
    quiz: Quiz, answers: List[QuizAnswer], completed_at: datetime
) -> Dict:
    answers_by_index = {answer.question_index: answer for answer in answers}
    questions = []
    for question in quiz.quiz_content.get("questions", []):
        index = question.get("index")
        answer = answers_by_index.get(index)
        questions.append(
            {
                "index": index,
                "prompt": question.get("prompt"),
                "options": question.get("options"),
                "selected_option_key": answer.selected_option_key if answer else None,
                "correct_option_key": question.get("correct_option_key"),
                "is_correct": answer.is_correct if answer else False,
                "explanation": question.get("explanation"),
            }
        )
    correct_count = sum(1 for answer in answers if answer.is_correct)
    score_percent = round((correct_count / quiz.total_questions) * 100, 2)
    return {
        "quiz_id": quiz.id,
        "completed_at": to_iso(completed_at),
        "score": {
            "correct_count": correct_count,
            "total_questions": quiz.total_questions,
            "score_percent": score_percent,
        },
        "questions": questions,
    }

# Create placeholder quiz content when AI generation is unavailable.
def build_placeholder_quiz_content(prompt: str) -> Dict:
    topic = prompt.strip() or "General Knowledge"
    return {
        "title": f"{topic} Placeholder Quiz",
        "questions": [
            {
                "prompt": f"Which statement best summarizes {topic}?",
                "options": [
                    {"key": "A", "text": f"{topic} is the main focus."},
                    {"key": "B", "text": "It is unrelated to the topic."},
                    {"key": "C", "text": "It only applies in rare cases."},
                    {"key": "D", "text": "It is a historical footnote."},
                ],
                "correct_option_key": "A",
                "explanation": "Placeholder explanation: the topic should be central.",
            },
            {
                "prompt": f"Which term is most associated with {topic}?",
                "options": [
                    {"key": "A", "text": "Distant echoes"},
                    {"key": "B", "text": f"Core {topic} concept"},
                    {"key": "C", "text": "Random noise"},
                    {"key": "D", "text": "Unrelated field"},
                ],
                "correct_option_key": "B",
                "explanation": "Placeholder explanation: this is a common association.",
            },
            {
                "prompt": f"Which activity is an example of {topic}?",
                "options": [
                    {"key": "A", "text": "Unrelated observation"},
                    {"key": "B", "text": "Contradictory practice"},
                    {"key": "C", "text": f"Applying {topic} principles"},
                    {"key": "D", "text": "Ignoring the topic entirely"},
                ],
                "correct_option_key": "C",
                "explanation": "Placeholder explanation: examples apply the topic.",
            },
            {
                "prompt": f"Which question would you ask to learn about {topic}?",
                "options": [
                    {"key": "A", "text": "What is the weather tomorrow?"},
                    {"key": "B", "text": "How tall is the nearest mountain?"},
                    {"key": "C", "text": "Who won last night's game?"},
                    {"key": "D", "text": f"What are the basics of {topic}?"},
                ],
                "correct_option_key": "D",
                "explanation": "Placeholder explanation: questions should be on-topic.",
            },
            {
                "prompt": f"Which choice is least related to {topic}?",
                "options": [
                    {"key": "A", "text": f"An overview of {topic}"},
                    {"key": "B", "text": "An unrelated distraction"},
                    {"key": "C", "text": f"{topic} fundamentals"},
                    {"key": "D", "text": f"Common {topic} vocabulary"},
                ],
                "correct_option_key": "B",
                "explanation": "Placeholder explanation: the unrelated option stands out.",
            },
        ],
    }

# Enforce quiz prompt length and allowed characters.
def validate_quiz_prompt(prompt: str) -> str:
    cleaned = prompt.strip()
    if not cleaned:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="prompt must be 1-3 words",
        )
    words = cleaned.split()
    if len(words) < 1 or len(words) > 3:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="prompt must be 1-3 words",
        )
    for word in words:
        if not re.fullmatch(r"[A-Za-z0-9-]+", word):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="prompt must be 1-3 words",
            )
    return " ".join(words)

# Create a new user and persist hashed credentials.
@app.post("/users", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def create_user(payload: UserCreate, db: Session = Depends(get_db)):
    salt = generate_salt()
    user = User(
        username=payload.username,
        password_hash=hash_password(payload.password, salt),
        password_salt=salt,
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="username already exists",
        )
    db.refresh(user)
    return UserOut(
        id=user.id,
        username=user.username,
        created_at=to_iso(user.created_at),
        message="account created",
    )

# Verify credentials and return a session payload.
@app.post("/sessions", response_model=SessionOut)
def create_session(payload: SessionCreate, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == payload.username).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="account not found. create an account.",
        )
    expected = hash_password(payload.password, user.password_salt)
    if expected != user.password_hash:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid")
    return SessionOut(user_id=user.id, username=user.username)

# Store a quiz with client-provided content.
@app.post("/quizzes", response_model=QuizOut, status_code=status.HTTP_201_CREATED)
def create_quiz(payload: QuizCreate, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == payload.user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="user not found")

    quiz_content = normalize_quiz_content(payload.quiz_content)
    quiz_public = build_quiz_public(quiz_content)
    total_questions = len(quiz_content["questions"])

    quiz = Quiz(
        user_id=payload.user_id,
        prompt=payload.prompt,
        status="in_progress",
        total_questions=total_questions,
        quiz_content=quiz_content,
        quiz_public=quiz_public,
    )
    db.add(quiz)
    db.commit()
    db.refresh(quiz)
    return QuizOut(
        id=quiz.id,
        user_id=quiz.user_id,
        prompt=quiz.prompt,
        status=quiz.status,
        created_at=to_iso(quiz.created_at),
        completed_at=None,
        total_questions=quiz.total_questions,
        correct_count=quiz.correct_count,
        score_percent=float(quiz.score_percent) if quiz.score_percent else None,
    )

# Persist a placeholder quiz for a user.
@app.post(
    "/quizzes/placeholder",
    response_model=QuizTakeOut,
    status_code=status.HTTP_201_CREATED,
)
def create_placeholder_quiz(
    payload: QuizPlaceholderCreate, db: Session = Depends(get_db)
):
    user = db.query(User).filter(User.id == payload.user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="user not found")

    quiz_content = normalize_quiz_content(build_placeholder_quiz_content(payload.prompt))
    quiz_public = build_quiz_public(quiz_content)
    total_questions = len(quiz_content["questions"])

    quiz = Quiz(
        user_id=payload.user_id,
        prompt=payload.prompt,
        status="in_progress",
        total_questions=total_questions,
        quiz_content=quiz_content,
        quiz_public=quiz_public,
    )
    db.add(quiz)
    db.commit()
    db.refresh(quiz)
    return QuizTakeOut(
        id=quiz.id,
        prompt=quiz.prompt,
        status=quiz.status,
        total_questions=quiz.total_questions,
        quiz_public=quiz.quiz_public,
    )

# Generate quiz content with AI and persist the quiz.
@app.post("/quizzes/generate", response_model=QuizTakeOut, status_code=status.HTTP_201_CREATED)
def create_generated_quiz(payload: QuizGenerateCreate, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == payload.user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="user not found")

    prompt = validate_quiz_prompt(payload.prompt)

    provider = get_ai_provider()
    api_key = get_ai_api_key(provider)
    if not api_key:
        key_env_var = get_ai_api_key_env_var(provider)
        quiz_content = normalize_quiz_content(build_placeholder_quiz_content(prompt))
        quiz_public = build_quiz_public(quiz_content)
        total_questions = len(quiz_content["questions"])

        quiz = Quiz(
            user_id=payload.user_id,
            prompt=prompt,
            status="in_progress",
            total_questions=total_questions,
            quiz_content=quiz_content,
            quiz_public=quiz_public,
        )
        db.add(quiz)
        db.commit()
        db.refresh(quiz)
        return QuizTakeOut(
            id=quiz.id,
            prompt=quiz.prompt,
            status=quiz.status,
            total_questions=quiz.total_questions,
            quiz_public=quiz.quiz_public,
            message=(
                f"Unable to create quiz: {key_env_var} is not configured. "
                "Defaulting to placeholder quiz."
            ),
        )

    try:
        quiz_content = generate_quiz_content(prompt)
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        )
    except Exception as exc:
        logger.exception("Quiz generation failed")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"quiz generation failed: {exc}",
        )

    quiz_content = ensure_prompt_coverage(prompt, quiz_content)
    quiz_content = normalize_quiz_content(quiz_content)
    quiz_public = build_quiz_public(quiz_content)
    total_questions = len(quiz_content["questions"])

    quiz = Quiz(
        user_id=payload.user_id,
        prompt=prompt,
        status="in_progress",
        total_questions=total_questions,
        quiz_content=quiz_content,
        quiz_public=quiz_public,
    )
    db.add(quiz)
    db.commit()
    db.refresh(quiz)
    return QuizTakeOut(
        id=quiz.id,
        prompt=quiz.prompt,
        status=quiz.status,
        total_questions=quiz.total_questions,
        quiz_public=quiz.quiz_public,
    )

# Return quiz metadata for a user.
@app.get("/quizzes", response_model=List[QuizOut])
def list_quizzes(user_id: str = Query(...), db: Session = Depends(get_db)):
    quizzes = (
        db.query(Quiz)
        .filter(Quiz.user_id == user_id)
        .order_by(Quiz.created_at.desc())
        .all()
    )
    results: List[QuizOut] = []
    for quiz in quizzes:
        results.append(
            QuizOut(
                id=quiz.id,
                user_id=quiz.user_id,
                prompt=quiz.prompt,
                status=quiz.status,
                created_at=to_iso(quiz.created_at),
                completed_at=to_iso(quiz.completed_at) if quiz.completed_at else None,
                total_questions=quiz.total_questions,
                correct_count=quiz.correct_count,
                score_percent=float(quiz.score_percent) if quiz.score_percent else None,
            )
        )
    return results

# Return the public quiz payload for taking the quiz.
@app.get("/quizzes/{quiz_id}", response_model=QuizTakeOut)
def get_quiz(quiz_id: str, db: Session = Depends(get_db)):
    quiz = db.query(Quiz).filter(Quiz.id == quiz_id).first()
    if not quiz:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="quiz not found")
    return QuizTakeOut(
        id=quiz.id,
        prompt=quiz.prompt,
        status=quiz.status,
        total_questions=quiz.total_questions,
        quiz_public=quiz.quiz_public,
    )

# Record an answer and finalize results when complete.
@app.post("/quizzes/{quiz_id}/answers", response_model=AnswerOut)
def submit_answer(quiz_id: str, payload: AnswerCreate, db: Session = Depends(get_db)):
    quiz = db.query(Quiz).filter(Quiz.id == quiz_id).first()
    if not quiz:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="quiz not found")
    if quiz.status == "completed":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="quiz completed")

    question = question_by_index(quiz.quiz_content, payload.question_index)
    selected_key = payload.selected_option_key
    correct_key = question.get("correct_option_key")
    is_correct = selected_key == correct_key

    feedback = {
        "question_index": payload.question_index,
        "selected_option_key": selected_key,
        "is_correct": is_correct,
        "correct_option_key": correct_key,
        "explanation": question.get("explanation"),
    }

    answer = QuizAnswer(
        quiz_id=quiz.id,
        question_index=payload.question_index,
        selected_option_key=selected_key,
        is_correct=is_correct,
        feedback=feedback,
    )
    db.add(answer)

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="answer already submitted",
        )

    answered_count = db.query(QuizAnswer).filter(QuizAnswer.quiz_id == quiz.id).count()
    if answered_count == quiz.total_questions:
        answers = db.query(QuizAnswer).filter(QuizAnswer.quiz_id == quiz.id).all()
        completed_at = datetime.now(tz=timezone.utc)
        results_snapshot = build_results_snapshot(quiz, answers, completed_at)
        quiz.correct_count = results_snapshot["score"]["correct_count"]
        quiz.score_percent = results_snapshot["score"]["score_percent"]
        quiz.status = "completed"
        quiz.completed_at = completed_at
        quiz.results_snapshot = results_snapshot
        db.add(quiz)
        db.commit()

    status_value = "completed" if quiz.status == "completed" else "in_progress"
    return AnswerOut(
        feedback=feedback,
        status=status_value,
        answered_count=answered_count,
        total_questions=quiz.total_questions,
    )

# Return results for a completed quiz.
@app.get("/quizzes/{quiz_id}/results", response_model=ResultsOut)
def get_results(quiz_id: str, db: Session = Depends(get_db)):
    quiz = db.query(Quiz).filter(Quiz.id == quiz_id).first()
    if not quiz:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="quiz not found")
    if quiz.status != "completed" or not quiz.results_snapshot:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="quiz not completed"
        )
    results = quiz.results_snapshot
    return ResultsOut(
        quiz_id=results["quiz_id"],
        completed_at=results["completed_at"],
        score=results["score"],
        questions=results["questions"],
    )
