from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class UserCreate(BaseModel):
    username: str
    password: str


class UserOut(BaseModel):
    id: str
    username: str
    created_at: str
    message: str


class SessionCreate(BaseModel):
    username: str
    password: str


class SessionOut(BaseModel):
    user_id: str
    username: str


class QuizCreate(BaseModel):
    user_id: str
    prompt: str
    quiz_content: Dict[str, Any]


class QuizPlaceholderCreate(BaseModel):
    user_id: str
    prompt: str


class QuizGenerateCreate(BaseModel):
    user_id: str
    prompt: str


class QuizOut(BaseModel):
    id: str
    user_id: str
    prompt: str
    status: str
    created_at: str
    completed_at: Optional[str]
    total_questions: int
    correct_count: Optional[int]
    score_percent: Optional[float]


class QuizTakeOut(BaseModel):
    id: str
    prompt: str
    status: str
    total_questions: int
    quiz_public: Dict[str, Any]


class AnswerCreate(BaseModel):
    question_index: int = Field(..., ge=1)
    selected_option_key: str


class AnswerOut(BaseModel):
    feedback: Dict[str, Any]
    status: str
    answered_count: int
    total_questions: int


class ResultsOut(BaseModel):
    quiz_id: str
    completed_at: str
    score: Dict[str, Any]
    questions: List[Dict[str, Any]]
