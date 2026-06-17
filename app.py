"""
app.py — Flask application entry point (trimmed desktop build).

Single-process, in-memory, single-user local app. Serves the UI and the
basic-statistics API (correlation + t-tests/nonparametric/ANOVA/Kruskal/
chi-square/Fisher). No Redis, no async job workers, no rate limiting —
none are needed for a local desktop deployment.
"""

import logging
import os
from datetime import timedelta

from flask import Flask, send_from_directory

from app_state import BASE_DIR

app = Flask(__name__)

app.config["SECRET_KEY"] = os.environ.get("DATAGRAD_SECRET_KEY", "local-desktop-key")
app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(hours=8)
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["SESSION_COOKIE_SECURE"] = False

# Reject oversized uploads before they balloon process memory. Default 100 MB.
app.config["MAX_CONTENT_LENGTH"] = int(
    os.environ.get("DATAGRAD_MAX_UPLOAD_BYTES", str(100 * 1024 * 1024))
)


def _is_debug():
    return bool(app.debug or app.config.get("DEBUG", False))


def _configure_logging():
    app.logger.setLevel(logging.DEBUG if _is_debug() else logging.INFO)


def get_logger():
    return app.logger


_configure_logging()

# ---------------------------------------------------------------------------
# In-memory session store (single process)
# ---------------------------------------------------------------------------

from session_store import SessionStore

store = SessionStore(ttl_seconds=int(os.environ.get("DATAGRAD_SESSION_TTL", str(8 * 3600))))

# ---------------------------------------------------------------------------
# Request-end write-back — no-op for the in-memory store, kept for parity.
# ---------------------------------------------------------------------------

from blueprints._session import persist_touched_state


@app.after_request
def _write_back_session(response):
    try:
        persist_touched_state()
    except Exception:
        app.logger.exception("Failed to persist session state")
    return response

# ---------------------------------------------------------------------------
# Background sweeper — evicts idle sessions (each holds a dataframe).
# ---------------------------------------------------------------------------

import threading


class _SessionSweeper:
    def __init__(self, store, interval_seconds=600, logger=None):
        self._store = store
        self._interval = interval_seconds
        self._logger = logger
        self._stop = threading.Event()
        self._thread = None

    def _run(self):
        while not self._stop.wait(self._interval):
            try:
                self._store.evict_expired()
            except Exception:
                if self._logger:
                    self._logger.exception("Session eviction failed")

    def start(self):
        if self._thread is None:
            self._thread = threading.Thread(target=self._run, name="datagrad-sweeper", daemon=True)
            self._thread.start()


if os.environ.get("DATAGRAD_DISABLE_SWEEPER") != "1":
    _SessionSweeper(store, logger=app.logger).start()

# ---------------------------------------------------------------------------
# Blueprint registration
# ---------------------------------------------------------------------------

from blueprints.data import create_blueprint as data_bp
from blueprints.analysis import create_blueprint as analysis_bp
from blueprints.help_bp import create_blueprint as help_bp
from blueprints.mfub_bp import create_blueprint as mfub_bp

app.register_blueprint(data_bp(store))
app.register_blueprint(analysis_bp(store))
app.register_blueprint(help_bp())
app.register_blueprint(mfub_bp())

# ---------------------------------------------------------------------------
# Static file serving
# ---------------------------------------------------------------------------

@app.errorhandler(413)
def _payload_too_large(_e):
    from flask import jsonify
    limit_mb = app.config["MAX_CONTENT_LENGTH"] / (1024 * 1024)
    return jsonify({
        "error": f"File too large. The maximum upload size is {limit_mb:.0f} MB."
    }), 413


@app.route('/healthz')
def healthz():
    from flask import jsonify
    return jsonify({"status": "ok", "backend": "memory"}), 200


@app.route('/log-location')
def log_location():
    from flask import jsonify
    import activity_log
    return jsonify({"folder": activity_log.log_location()}), 200


@app.route('/log-tail')
def log_tail():
    from flask import jsonify, request
    import os as _os
    import activity_log
    try:
        n = int(request.args.get('n', 200))
    except (TypeError, ValueError):
        n = 200
    n = max(1, min(n, 2000))
    path = _os.path.join(activity_log.log_location(), 'datagrad_activity.log')
    if not _os.path.exists(path):
        return jsonify({"lines": []}), 200
    try:
        with open(path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        return jsonify({"lines": [ln.rstrip('\n') for ln in lines[-n:]]}), 200
    except Exception:
        return jsonify({"lines": []}), 200


@app.route('/')
def index():
    return send_from_directory(BASE_DIR, 'index.html')


@app.route('/style.css')
def serve_css():
    return send_from_directory(BASE_DIR, 'style.css')


@app.route('/js/<path:filename>')
def serve_js(filename):
    return send_from_directory(os.path.join(BASE_DIR, 'js'), filename)


@app.route('/help_content/<path:filename>')
def serve_help_content(filename):
    return send_from_directory(os.path.join(BASE_DIR, 'help_content'), filename)


@app.route('/assets/<path:filename>')
def serve_assets(filename):
    return send_from_directory(os.path.join(BASE_DIR, 'assets'), filename)


@app.route('/vendor/<path:filename>')
def serve_vendor(filename):
    return send_from_directory(os.path.join(BASE_DIR, 'vendor'), filename)


# ---------------------------------------------------------------------------

if __name__ == '__main__':
    host = os.environ.get("DATAGRAD_HOST", "127.0.0.1")
    port = int(os.environ.get("DATAGRAD_PORT", "5000"))
    threads = int(os.environ.get("DATAGRAD_THREADS", "8"))
    try:
        from waitress import serve
        app.logger.info("Starting waitress on %s:%d", host, port)
        serve(app, host=host, port=port, threads=threads)
    except ImportError:
        app.logger.warning("waitress not installed — falling back to Flask dev server")
        app.run(debug=True, port=port, threaded=True)
