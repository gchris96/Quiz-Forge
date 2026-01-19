import uuid

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.types import JSON

from app.database import Base


def _uuid_str():
    return str(uuid.uuid4())


class User(Base):
    __tablename__ = "users"

    id = Column(String(36), primary_key=True, default=_uuid_str)
    username = Column(String(255), nullable=False, unique=True, index=True)
    password_hash = Column(String(255), nullable=False)
    password_salt = Column(String(255), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class Quiz(Base):
    __tablename__ = "quizzes"

    id = Column(String(36), primary_key=True, default=_uuid_str)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    prompt = Column(Text, nullable=False)
    status = Column(String(20), nullable=False, default="in_progress")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    completed_at = Column(DateTime(timezone=True))
    total_questions = Column(Integer, nullable=False)
    correct_count = Column(Integer)
    score_percent = Column(Numeric(5, 2))
    quiz_content = Column(JSON().with_variant(JSONB, "postgresql"), nullable=False)
    quiz_public = Column(JSON().with_variant(JSONB, "postgresql"), nullable=False)
    results_snapshot = Column(JSON().with_variant(JSONB, "postgresql"))

    __table_args__ = (
        CheckConstraint(
            "status IN ('in_progress', 'completed')", name="quizzes_status_check"
        ),
        Index("quizzes_user_created_idx", "user_id", "created_at"),
        Index("quizzes_user_status_idx", "user_id", "status"),
    )


class QuizAnswer(Base):
    __tablename__ = "quiz_answers"

    id = Column(String(36), primary_key=True, default=_uuid_str)
    quiz_id = Column(String(36), ForeignKey("quizzes.id"), nullable=False)
    question_index = Column(Integer, nullable=False)
    selected_option_key = Column(String(50), nullable=False)
    is_correct = Column(Boolean, nullable=False)
    answered_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    feedback = Column(JSON().with_variant(JSONB, "postgresql"), nullable=False)

    __table_args__ = (
        Index("quiz_answers_quiz_idx", "quiz_id"),
        Index("quiz_answers_quiz_question_idx", "quiz_id", "question_index", unique=True),
    )
