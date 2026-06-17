"""
desktop_main.py — Windows desktop entry point for the trimmed Datagrad app.

Starts the Flask app on a private localhost port using the waitress WSGI
server (in a background thread), waits until it answers, then opens a native
OS window pointed at it via pywebview. Closing the window shuts everything
down. No browser, no console, no network exposure beyond 127.0.0.1.

This module is what PyInstaller bundles into Datagrad.exe.
"""

import os
import socket
import sys
import threading
import time
from urllib.request import urlopen


def _resource_base():
    """
    Directory that holds index.html, style.css, js/, help_content/.

    When frozen by PyInstaller (one-file mode) the data files are unpacked to
    a temp dir exposed as sys._MEIPASS. In a normal checkout it's just the
    folder this file lives in.
    """
    if getattr(sys, "frozen", False):
        return sys._MEIPASS  # type: ignore[attr-defined]
    return os.path.dirname(os.path.abspath(__file__))


# app_state.BASE_DIR is computed at import time from __file__, which is wrong
# under PyInstaller. Pin it to the unpacked resource dir before importing app.
os.environ.setdefault("DATAGRAD_DISABLE_SWEEPER", "0")
_BASE = _resource_base()
os.environ["DATAGRAD_BASE_DIR"] = _BASE


def _find_free_port():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def _wait_until_up(url, timeout=30.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urlopen(url, timeout=1) as resp:
                if resp.status == 200:
                    return True
        except Exception:
            time.sleep(0.2)
    return False


def _serve(port):
    # Import here so any import cost happens on the server thread.
    from app import app
    from waitress import serve
    serve(app, host="127.0.0.1", port=port, threads=8)


def main():
    port = _find_free_port()
    base_url = f"http://127.0.0.1:{port}/"

    server_thread = threading.Thread(target=_serve, args=(port,), daemon=True)
    server_thread.start()

    if not _wait_until_up(base_url + "healthz", timeout=30.0):
        sys.stderr.write("Server did not start in time.\n")

    # Try a native OS window first. If no webview backend is available on this
    # machine, fall back to the default web browser so the app still works.
    used_browser_fallback = False
    try:
        import webview  # pywebview
        window = webview.create_window(
            "Datagrad MFUB Desktop",
            base_url,
            width=1280,
            height=860,
            min_size=(900, 600),
        )
        start_time = time.time()
        webview.start()
        # A near-instant return *with no windows registered* means no GUI
        # backend ever initialised (rather than the user closing the window).
        if (time.time() - start_time) < 1.0 and not getattr(webview, "windows", [window]):
            raise RuntimeError("no usable native-window backend")
    except Exception as e:
        used_browser_fallback = True
        sys.stderr.write(f"Native window unavailable ({e}); opening in browser.\n")

    if used_browser_fallback:
        import webbrowser
        webbrowser.open(base_url)
        # Keep the process (and the server thread) alive while the browser is open.
        try:
            while True:
                time.sleep(3600)
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    main()
