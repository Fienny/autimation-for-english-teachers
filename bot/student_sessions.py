from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import UTC, datetime, timedelta
from typing import Literal

StudentLanguage = Literal["ru", "uz"]
IeltsPart = Literal["1", "2", "3"]
StudentState = Literal[
    "choosing_language",
    "choosing_part",
    "generating_question",
    "awaiting_voice",
    "processing_answer",
    "completed",
]

SESSION_TTL = timedelta(minutes=60)


def _now() -> datetime:
    return datetime.now(UTC)


@dataclass(frozen=True)
class StudentSession:
    user_id: int
    state: StudentState
    language: StudentLanguage | None = None
    ielts_part: IeltsPart | None = None
    question: str | None = None
    transcript: str | None = None
    feedback: str | None = None
    created_at: datetime = field(default_factory=_now)
    updated_at: datetime = field(default_factory=_now)


_sessions: dict[int, StudentSession] = {}


def _is_expired(session: StudentSession) -> bool:
    return _now() - session.updated_at > SESSION_TTL


def create_session(user_id: int) -> StudentSession:
    session = StudentSession(user_id=user_id, state="choosing_language")
    _sessions[user_id] = session
    return session


def get_session(user_id: int) -> StudentSession | None:
    session = _sessions.get(user_id)
    if not session:
        return None
    if _is_expired(session):
        _sessions.pop(user_id, None)
        return None
    return session


def update_session(user_id: int, **changes: object) -> StudentSession:
    session = get_session(user_id) or create_session(user_id)
    updated = replace(session, updated_at=_now(), **changes)
    _sessions[user_id] = updated
    return updated


def clear_session(user_id: int) -> None:
    _sessions.pop(user_id, None)
