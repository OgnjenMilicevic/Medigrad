"""
session_store.py — per-session AppState management.

Each browser session gets its own AppState, keyed by a session id carried
in a signed cookie. This is the change that makes concurrent users safe:
User A's dataframe lives in a different AppState than User B's.

Design notes:
  - In-memory dict, guarded by a lock. Correct for a single multi-threaded
    server process (3-5 users). When the app goes multi-process, this class
    is the single thing that swaps to Redis — the interface stays the same.
  - TTL eviction prevents abandoned sessions (each holds a full dataframe)
    from leaking memory.
  - Thread-safe: every access takes the lock. The critical sections are tiny
    (dict get/set), so contention is negligible at this scale.
"""

import threading
import time

from app_state import AppState


class SessionStore:
    def __init__(self, ttl_seconds: int = 3600):
        # session_id -> {"state": AppState, "last_access": float}
        self._sessions: dict[str, dict] = {}
        self._lock = threading.Lock()
        self._ttl = ttl_seconds

    def get_or_create(self, session_id: str) -> AppState:
        """Return the AppState for this session, creating one if needed."""
        now = time.time()
        with self._lock:
            entry = self._sessions.get(session_id)
            if entry is None:
                entry = {"state": AppState(), "last_access": now}
                self._sessions[session_id] = entry
            else:
                entry["last_access"] = now
            return entry["state"]

    def get(self, session_id: str) -> AppState | None:
        """Return the AppState for this session without creating one."""
        with self._lock:
            entry = self._sessions.get(session_id)
            if entry is None:
                return None
            entry["last_access"] = time.time()
            return entry["state"]

    def drop(self, session_id: str) -> None:
        """Explicitly remove a session (e.g. on logout / new dataset)."""
        with self._lock:
            self._sessions.pop(session_id, None)

    def evict_expired(self) -> int:
        """
        Remove sessions idle longer than the TTL. Returns the count evicted.
        Call periodically from a background sweep, or opportunistically.
        """
        cutoff = time.time() - self._ttl
        with self._lock:
            stale = [sid for sid, e in self._sessions.items() if e["last_access"] < cutoff]
            for sid in stale:
                del self._sessions[sid]
            return len(stale)

    def active_count(self) -> int:
        with self._lock:
            return len(self._sessions)
