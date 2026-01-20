# Pydantic request/response schemas.
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

# Request payload for creating a user.
class UserCreate(BaseModel):
    username: str
    password: str

# Response model for a created user.
class UserOut(BaseModel):
    id: str
    username: str
    created_at: str
    message: str

# Request payload for creating a session.
class SessionCreate(BaseModel):
    username: str
    password: str

# Response model for a created session.
class SessionOut(BaseModel):
    user_id: str
    username: str

# Request payload for persisting a quiz with provided content.
class QuizCreate(BaseModel):
    user_id: str
    prompt: str
    quiz_content: Dict[str, Any]

# Request payload for creating a placeholder quiz.
class QuizPlaceholderCreate(BaseModel):
    user_id: str
    prompt: str

# Request payload for generating a quiz via AI.
class QuizGenerateCreate(BaseModel):
    user_id: str
    prompt: str

# Response model for quiz metadata.
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

# Response model for taking a quiz without answers.
class QuizTakeOut(BaseModel):
    id: str
    prompt: str
    status: str
    total_questions: int
    quiz_public: Dict[str, Any]
    message: Optional[str] = None

# Request payload for submitting an answer.
class AnswerCreate(BaseModel):
    question_index: int = Field(..., ge=1)
    selected_option_key: str

# Response model for answer feedback.
class AnswerOut(BaseModel):
    feedback: Dict[str, Any]
    status: str
    answered_count: int
    total_questions: int

# Response model for quiz results.
class ResultsOut(BaseModel):
    quiz_id: str
    completed_at: str
    score: Dict[str, Any]
    questions: List[Dict[str, Any]]
