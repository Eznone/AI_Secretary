from dataclasses import dataclass
from datetime import datetime


@dataclass
class Session:
    id: int
    created_at: str
    summary: str | None


@dataclass
class Message:
    id: int
    session_id: int
    role: str          # "user" | "assistant" | "tool"
    content: str
    created_at: str


@dataclass
class UserContext:
    key: str           # e.g. "preferred_timezone", "name", "work_calendar_id"
    value: str
    updated_at: str
