from __future__ import annotations

import hashlib


def stable_id(prefix: str, *parts: object, length: int = 32) -> str:
    """Build an idempotent, opaque identifier from adapter-local identity."""

    raw = "\x1f".join(str(part) for part in parts).encode("utf-8")
    return f"{prefix}_{hashlib.sha256(raw).hexdigest()[:length]}"


def repository_uri(filepath: str) -> str:
    """Represent a source path without leaking the absolute project directory."""

    clean = filepath.replace("\\", "/").lstrip("./")
    return f"repo:///{clean}"
