# Pytest fixtures and test database setup.
import importlib
import os
import sys

import pytest
from fastapi.testclient import TestClient

# Build a normalized quiz payload for reuse in tests.
@pytest.fixture()
def build_quiz_content():
    # Construct quiz content with a configurable number of questions.
    def _build(prompt: str, question_count: int = 5):
        questions = []
        for idx in range(1, question_count + 1):
            questions.append(
                {
                    "index": idx,
                    "prompt": f"{prompt} question {idx}?",
                    "options": [
                        {"key": "A", "text": "Option A"},
                        {"key": "B", "text": "Option B"},
                        {"key": "C", "text": "Option C"},
                        {"key": "D", "text": "Option D"},
                    ],
                    "correct_option_key": "A",
                    "explanation": "Example explanation.",
                }
            )
        return {"title": f"{prompt} Quiz", "questions": questions}

    return _build


# Provide a stable sample quiz payload with known correct answers.
@pytest.fixture()
def sample_quiz_content():
    return {
        "title": "Sample Quiz",
        "questions": [
            {
                "index": 1,
                "prompt": "What is 2 + 2?",
                "options": [
                    {"key": "A", "text": "3"},
                    {"key": "B", "text": "4"},
                    {"key": "C", "text": "5"},
                    {"key": "D", "text": "6"},
                ],
                "correct_option_key": "B",
                "explanation": "2 + 2 equals 4.",
            },
            {
                "index": 2,
                "prompt": "Which planet is known as the Red Planet?",
                "options": [
                    {"key": "A", "text": "Mars"},
                    {"key": "B", "text": "Venus"},
                    {"key": "C", "text": "Jupiter"},
                    {"key": "D", "text": "Mercury"},
                ],
                "correct_option_key": "A",
                "explanation": "Mars is called the Red Planet.",
            },
            {
                "index": 3,
                "prompt": "Which gas do plants absorb from the atmosphere?",
                "options": [
                    {"key": "A", "text": "Oxygen"},
                    {"key": "B", "text": "Carbon dioxide"},
                    {"key": "C", "text": "Nitrogen"},
                    {"key": "D", "text": "Helium"},
                ],
                "correct_option_key": "B",
                "explanation": "Plants absorb carbon dioxide for photosynthesis.",
            },
            {
                "index": 4,
                "prompt": "What is the capital of France?",
                "options": [
                    {"key": "A", "text": "Paris"},
                    {"key": "B", "text": "Lyon"},
                    {"key": "C", "text": "Marseille"},
                    {"key": "D", "text": "Bordeaux"},
                ],
                "correct_option_key": "A",
                "explanation": "Paris is the capital of France.",
            },
            {
                "index": 5,
                "prompt": "What is the boiling point of water at sea level?",
                "options": [
                    {"key": "A", "text": "100 C"},
                    {"key": "B", "text": "0 C"},
                    {"key": "C", "text": "50 C"},
                    {"key": "D", "text": "150 C"},
                ],
                "correct_option_key": "A",
                "explanation": "Water boils at 100 C at sea level.",
            },
        ],
    }

# Provide a FastAPI test client backed by a temporary test database.
@pytest.fixture()
def client():
    test_database_url = os.getenv(
        "TEST_DATABASE_URL",
        "postgresql+psycopg://postgres:postgres@localhost:5432/quiz_forge_test",
    )
    os.environ["DATABASE_URL"] = test_database_url

    if "app.database" in sys.modules:
        importlib.reload(sys.modules["app.database"])
    if "app.models" in sys.modules:
        importlib.reload(sys.modules["app.models"])
    if "app.main" in sys.modules:
        importlib.reload(sys.modules["app.main"])

    from app.database import Base, engine  # noqa: E402
    from app.main import app  # noqa: E402

    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)

    with TestClient(app) as test_client:
        yield test_client

    Base.metadata.drop_all(bind=engine)
