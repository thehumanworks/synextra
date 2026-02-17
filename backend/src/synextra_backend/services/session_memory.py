from __future__ import annotations

import threading
from dataclasses import dataclass
from datetime import datetime, timezone

from synextra_backend.schemas.rag_chat import RagCitation, RetrievalMode


@dataclass(frozen=True)
class SessionTurn:
    role: str
    content: str
    mode: RetrievalMode | None
    citations: list[RagCitation]
    tools_used: list[str]
    created_at: datetime


class SessionMemory:
    """In-memory conversation store keyed by session id."""

    def __init__(self, *, max_turns: int = 20) -> None:
        self._lock = threading.RLock()
        self._max_turns = max(2, max_turns)
        self._sessions: dict[str, list[SessionTurn]] = {}

    def list_turns(self, session_id: str) -> list[SessionTurn]:
        with self._lock:
            return list(self._sessions.get(session_id, []))

    def append_turn(
        self,
        *,
        session_id: str,
        role: str,
        content: str,
        mode: RetrievalMode | None = None,
        citations: list[RagCitation] | None = None,
        tools_used: list[str] | None = None,
    ) -> None:
        with self._lock:
            turns = list(self._sessions.get(session_id, []))
            turns.append(
                SessionTurn(
                    role=role,
                    content=content,
                    mode=mode,
                    citations=list(citations or []),
                    tools_used=list(tools_used or []),
                    created_at=datetime.now(timezone.utc),
                )
            )
            if len(turns) > self._max_turns:
                turns = turns[-self._max_turns :]
            self._sessions[session_id] = turns
