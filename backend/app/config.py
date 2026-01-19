import os
from pathlib import Path
from typing import Dict


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


def load_env() -> Dict[str, str]:
    root = Path(__file__).resolve().parents[2]
    return load_env_file(root / ".env")
