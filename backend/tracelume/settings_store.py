"""Persistent workstation settings."""

from typing import Any
from urllib.parse import urlparse

from sqlmodel import Session

from tracelume.models import Setting

LOCAL_HOSTS = {"ollama", "localhost", "127.0.0.1", "::1", "host.docker.internal", "llm"}

DEFAULTS: dict[str, dict[str, Any]] = {
    "assistant": {
        "enabled": True,
        "base_url": "http://ollama:11434/v1",  # any OpenAI-compatible endpoint
        "model": "qwen2.5:7b-instruct",
        "api_key": "",
        "temperature": 0.1,
    },
    "examiner": {"name": ""},
}


def get(s: Session, key: str) -> dict[str, Any]:
    row = s.get(Setting, key)
    return {**DEFAULTS.get(key, {}), **(row.value if row else {})}


def put(s: Session, key: str, value: dict[str, Any]) -> dict[str, Any]:
    merged = {**get(s, key), **value}
    row = s.get(Setting, key) or Setting(key=key)
    row.value = merged
    s.add(row)
    s.commit()
    return merged


def is_local(base_url: str) -> bool:
    host = (urlparse(base_url).hostname or "").lower()
    return host in LOCAL_HOSTS or host.endswith(".local") or host.startswith(("10.", "192.168."))
