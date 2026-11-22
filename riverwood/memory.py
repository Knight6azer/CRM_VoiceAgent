"""Thread-safe conversation memory store with strict session isolation and bounded capacity."""

import threading
from collections import OrderedDict, deque
from typing import Deque, Dict, List, Optional


class ConversationStore:
    """Thread-safe conversation memory store with LRU session eviction and max turns per session."""

    def __init__(self, max_turns: int = 12, max_sessions: int = 1000) -> None:
        self.max_turns = max_turns
        self.max_sessions = max_sessions
        self._lock = threading.Lock()
        self._sessions: OrderedDict[str, Deque[Dict[str, str]]] = OrderedDict()

    def append(self, session_id: str, user_text: str, agent_text: str) -> None:
        """Append a dialogue turn for a specific session with strict session isolation."""
        with self._lock:
            if session_id in self._sessions:
                # Move to end for LRU tracking
                self._sessions.move_to_end(session_id)
            else:
                if len(self._sessions) >= self.max_sessions:
                    # Evict oldest session
                    self._sessions.popitem(last=False)
                self._sessions[session_id] = deque(maxlen=self.max_turns)

            self._sessions[session_id].append({"user": user_text, "assistant": agent_text})

    def as_messages(self, session_id: str) -> List[Dict[str, str]]:
        """Return session history formatted as OpenAI chat completion messages."""
        with self._lock:
            if session_id not in self._sessions:
                return []
            self._sessions.move_to_end(session_id)
            messages: List[Dict[str, str]] = []
            for turn in self._sessions[session_id]:
                messages.append({"role": "user", "content": turn["user"]})
                messages.append({"role": "assistant", "content": turn["assistant"]})
            return messages

    def clear(self, session_id: Optional[str] = None) -> None:
        """Clear memory for a single session or all sessions."""
        with self._lock:
            if session_id is None:
                self._sessions.clear()
            elif session_id in self._sessions:
                del self._sessions[session_id]

    def session_count(self) -> int:
        """Return count of currently active sessions in memory."""
        with self._lock:
            return len(self._sessions)
