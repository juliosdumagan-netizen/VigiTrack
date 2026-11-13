"""
VigiTrack desktop app: runs the backend on this PC only and shows the hub in a native window.

Usage (from the backend folder):
    python desktop.py

Requires the hub to be built first:  cd ../frontend && npm run build
"""
import os
import socket
import sys
import threading
import time

os.environ.setdefault("VIGITRACK_DESKTOP", "1")

try:
    import webview  # type: ignore[import-not-found]
except ImportError:  # pragma: no cover - optional dependency for desktop mode
    webview = None

from flask import abort, send_from_directory  # type: ignore[import-not-found]
from waitress import serve

from app.database.retention import start_retention_worker
from run import create_app

FRONTEND_DIST = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "frontend", "dist"))
ICON_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "vigitrack.ico")
HOST = "127.0.0.1"


def use_taskbar_identity() -> None:
    """Makes Windows group the window under VigiTrack instead of python.exe."""
    if sys.platform != "win32":
        return
    try:
        import ctypes

        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("VigiTrack.Desktop.1")
    except Exception:
        pass


def add_frontend(app):
    """Serves the built React hub, with a fallback to index.html for in-app page addresses."""

    @app.route("/", defaults={"path": ""})
    @app.route("/<path:path>")
    def hub(path):
        if path == "api" or path.startswith("api/"):
            abort(404)
        if path and os.path.isfile(os.path.join(FRONTEND_DIST, path)):
            return send_from_directory(FRONTEND_DIST, path)
        return send_from_directory(FRONTEND_DIST, "index.html")


def free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind((HOST, 0))
        return s.getsockname()[1]


def wait_for_server(port: int, timeout: float = 15.0) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex((HOST, port)) == 0:
                return
        time.sleep(0.1)
    raise RuntimeError("The VigiTrack server did not start in time.")


def main() -> None:
    if not os.path.isfile(os.path.join(FRONTEND_DIST, "index.html")):
        print("The hub has not been built yet. Run 'npm run build' in the frontend folder, then try again.")
        sys.exit(1)

    if webview is None:
        print("Desktop mode requires the 'pywebview' package. Install it with 'pip install pywebview'.")
        sys.exit(1)

    app = create_app()
    add_frontend(app)
    start_retention_worker()

    port = free_port()
    server = threading.Thread(
        target=serve,
        kwargs={"app": app, "host": HOST, "port": port, "threads": 8, "_quiet": True},
        daemon=True,
    )
    server.start()
    wait_for_server(port)

    webview.create_window(
        "VigiTrack",
        f"http://{HOST}:{port}/",
        width=1400,
        height=900,
        min_size=(1100, 700),
    )
    use_taskbar_identity()
    webview.start(icon=ICON_PATH if os.path.isfile(ICON_PATH) else None)


if __name__ == "__main__":
    main()
