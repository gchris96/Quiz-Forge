# Environment loading tests.
import os

from app.env import load_environment


def test_load_environment_from_path(monkeypatch, tmp_path):
    dotenv_path = tmp_path / ".env"
    dotenv_path.write_text("AI_PROVIDER=claude\n")
    monkeypatch.delenv("AI_PROVIDER", raising=False)

    load_environment(dotenv_path=str(dotenv_path))

    assert os.getenv("AI_PROVIDER") == "claude"
