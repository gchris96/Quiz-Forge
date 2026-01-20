# Environment loading tests.
import os
from pathlib import Path

from app.config import load_env_file

# Ensure missing env vars are populated from the .env file.
def test_load_env_file_sets_missing_values(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text('OPENAI_API_KEY="test_key"\n', encoding="utf-8")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    loaded = load_env_file(env_file)

    assert loaded["OPENAI_API_KEY"] == "test_key"
    assert os.environ["OPENAI_API_KEY"] == "test_key"

# Ensure existing env vars are not overridden by the .env file.
def test_load_env_file_does_not_override_existing(monkeypatch, tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text("OPENAI_API_KEY=ignored\n", encoding="utf-8")
    monkeypatch.setenv("OPENAI_API_KEY", "from_env")

    loaded = load_env_file(env_file)

    assert loaded == {}
    assert os.environ["OPENAI_API_KEY"] == "from_env"
