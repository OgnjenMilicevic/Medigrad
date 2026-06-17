"""
blueprints/_session.py — per-request AppState resolution and write-back.

resolve_state(store) returns the AppState for the current browser session.

With an in-memory SessionStore, the returned AppState is a live object and
mutations stick automatically — nothing more to do.

With a RedisSessionStore, the AppState is deserialised from Redis on each call,
so mutations must be written back. resolve_state records the (store, sid,
state) it handed out on Flask's `g`; persist_touched_state() — wired to
after_request in app.py — saves it back at the end of the request. Blueprints
are unaware of any of this: they call resolve_state and mutate as before.
"""

import uuid

from flask import session, g


SESSION_KEY = "sid"


def current_session_id() -> str:
    """Return the caller's session id, minting one on first request."""
    sid = session.get(SESSION_KEY)
    if sid is None:
        sid = uuid.uuid4().hex
        session[SESSION_KEY] = sid
        session.permanent = True
    return sid


def resolve_state(store):
    """
    Return the AppState for the current browser session.

    Records the resolved state on `g` so persist_touched_state() can write it
    back after the request (only matters for stores that need it, i.e. Redis).
    """
    sid = current_session_id()
    state = store.get_or_create(sid)
    g._touched_store = store
    g._touched_sid = sid
    g._touched_state = state
    return state


def persist_touched_state():
    """
    Save the request's AppState back to its store if the store requires it.

    In-memory SessionStore has no `save` method (mutations are already live),
    so this is a no-op for it. RedisSessionStore.save() serialises and writes.
    """
    store = g.pop("_touched_store", None)
    sid = g.pop("_touched_sid", None)
    state = g.pop("_touched_state", None)
    if store is None or sid is None or state is None:
        return
    save = getattr(store, "save", None)
    if callable(save):
        save(sid, state)
