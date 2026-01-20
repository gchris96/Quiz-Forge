# Environment loading helpers.
from typing import Optional

from dotenv import load_dotenv


def load_environment(dotenv_path: Optional[str] = None) -> None:
    load_dotenv(dotenv_path=dotenv_path)
