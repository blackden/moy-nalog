from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Optional


def default_token_path() -> Path:
    xdg = os.getenv("XDG_CONFIG_HOME")
    base = Path(xdg) if xdg else Path.home() / ".config"
    return base / "moy-nalog" / "token.json"


class TokenStore:
    def __init__(self, path: Optional[Path] = None) -> None:
        self.path = Path(path) if path else default_token_path()

    def load(self) -> Optional[str]:
        try:
            data = self.path.read_text(encoding="utf-8")
            return data.strip() or None
        except FileNotFoundError:
            return None

    def save(self, token_json: str) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        # Best-effort restrict permissions on POSIX
        try:
            old_umask = os.umask(0o177)
        except Exception:
            old_umask = None
        try:
            self.path.write_text(token_json, encoding="utf-8")
        finally:
            if old_umask is not None:
                os.umask(old_umask)

