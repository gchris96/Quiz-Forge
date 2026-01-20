# Environment file loading helpers.
import os
from pathlib import Path
from typing import Dict

# Load key/value pairs from a .env-style file into process environment.
def load_env_file(path: Path) -> Dict[str, str]:
    if not path.exists():
        return {}
    content = path.read_text(encoding="utf-8")
    loaded: Dict[str, str] = {}
    for line in content.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value
            loaded[key] = value
    return loaded

# Load the repo-root .env file and return any values that were set.
def load_env() -> Dict[str, str]:
    root = Path(__file__).resolve().parents[2]
    return load_env_file(root / ".env")
