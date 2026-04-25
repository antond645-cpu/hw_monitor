"""HW Monitor HTTP service.

The server avoids running slow I/O commands in request handlers.
All heavy lifting is done by the background `Collector`, while routes only
serve ready snapshots. This keeps request latency predictable under load.
"""
from __future__ import annotations

import functools
import logging

from flask import (
    Flask,
    jsonify,
    make_response,
    redirect,
    render_template,
    request,
    session,
)

import config
from collector import Collector

logging.basicConfig(
    level=getattr(logging, config.LOG_LEVEL, logging.INFO),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
log = logging.getLogger("server")

app = Flask(__name__, template_folder=".")
app.secret_key = config.SECRET_KEY
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    PERMANENT_SESSION_LIFETIME=config.SESSION_TTL_SEC,
)

collector = Collector()
collector.start()


# ---------- Authentication --------------------------------------------------

def _is_authed() -> bool:
    return bool(session.get("ok"))


def require_auth(view):
    @functools.wraps(view)
    def wrapper(*args, **kwargs):
        if _is_authed():
            return view(*args, **kwargs)
        # Backward compatibility: ?debug=<pass> still works,
        # but now it immediately sets a cookie so the password
        # does not remain in the URL.
        token = request.args.get("debug")
        if token and token == config.PASSWORD:
            session.permanent = True
            session["ok"] = True
            if request.path.startswith("/api/"):
                return view(*args, **kwargs)
            return redirect(request.path)
        if request.path.startswith("/api/"):
            return jsonify({"error": "Unauthorized"}), 401
        return redirect("/login")
    return wrapper


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        pw = request.form.get("password", "")
        if pw == config.PASSWORD:
            session.permanent = True
            session["ok"] = True
            return redirect("/")
        return render_template(
            "index.html",
            login_error="Invalid password",
            app_title=config.APP_TITLE,
        ), 401
    if _is_authed():
        return redirect("/")
    return render_template("index.html", login_error=None, app_title=config.APP_TITLE)


@app.route("/logout", methods=["POST"])
def logout():
    session.clear()
    return redirect("/login")


# ---------- System routes ---------------------------------------------------

@app.route("/healthz")
def healthz():
    return jsonify({"status": "ok"})


# ---------- Main routes -----------------------------------------------------

@app.route("/")
@require_auth
def index():
    return render_template("index.html", login_error=None, app_title=config.APP_TITLE)


@app.route("/api/data")
@require_auth
def api_data():
    """Live snapshot: latest N points from the in-memory buffer."""
    return jsonify(collector.snapshot_live())


@app.route("/api/history")
@require_auth
def api_history():
    period = request.args.get("period", "1h")
    if period not in {"10m", "1h", "24h", "1w"}:
        return jsonify({"error": "bad period"}), 400
    return jsonify(collector.snapshot_history(period))


# ---------- CLI ------------------------------------------------------------

if __name__ == "__main__":
    # For production use gunicorn/waitress; Flask dev server is debug-only.
    app.run(host=config.HOST, port=config.PORT, threaded=True)
