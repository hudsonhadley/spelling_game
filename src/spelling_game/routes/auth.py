"""Login, logout, and access-control helpers.

Two user roles exist:
  - PLAYER: can play the game.
  - ADMIN:  can also manage the word list.
"""

from functools import wraps
from contextlib import contextmanager
from pathlib import Path
import sqlite3
from urllib.parse import urlsplit

from werkzeug.security import check_password_hash, generate_password_hash
from spelling_game.forms import LoginForm, SignupForm

from flask import (
    abort,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    session,
    url_for,
)

from spelling_game.routes import auth_bp

PLAYER = "player"
ADMIN = "admin"


# --------------------------------------------------------------------------
# Session helpers
# --------------------------------------------------------------------------
def get_current_user() -> dict | None:
    """Return {"id", "username", "role"} for the logged-in user, else None."""
    user_id = session.get("user_id")
    if user_id is None:
        return None
    with _accounts() as db:
        row = db.execute("SELECT id, username, role FROM users WHERE id = ?", (user_id,)).fetchone()
    if row is None:
        session.clear()
        return None
    return dict(row)


@auth_bp.app_context_processor
def inject_current_user():
    """Make `current_user` available in every template."""
    return {"current_user": get_current_user(), "ADMIN": ADMIN, "PLAYER": PLAYER}


def _is_safe_next(target: str | None) -> bool:
    """Only allow redirects to paths on this site (prevents open redirects)."""
    if not target or not target.startswith("/"):
        return False
    if target.startswith("//") or "\\" in target or any(ord(char) < 32 or ord(char) == 127 for char in target):
        return False
    try:
        parsed = urlsplit(target)
    except ValueError:
        return False
    return not parsed.scheme and not parsed.netloc


# --------------------------------------------------------------------------
# Access-control decorators
# --------------------------------------------------------------------------
def login_required(view):
    """Redirect anonymous visitors to the login page."""

    @wraps(view)
    def wrapped(*args, **kwargs):
        if get_current_user() is None:
            flash("Please log in to continue.", "warning")
            return redirect(url_for("auth.login", next=request.path))
        return view(*args, **kwargs)

    return wrapped


def admin_required(view):
    """Like login_required, but also responds 403 to non-admin users."""

    @wraps(view)
    @login_required
    def wrapped(*args, **kwargs):
        if get_current_user()["role"] != ADMIN:
            abort(403)
        return view(*args, **kwargs)

    return wrapped


# --------------------------------------------------------------------------
# SQLite account storage (kept separate from future game data).
# --------------------------------------------------------------------------
@contextmanager
def _accounts():
    """Open the configured account database; create the table on first use."""
    database = Path(current_app.config.get("AUTH_DATABASE", Path(current_app.instance_path) / "accounts.sqlite3"))
    database.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(database)
    db.row_factory = sqlite3.Row
    try:
        db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY,
                username TEXT NOT NULL,
                email TEXT NOT NULL UNIQUE COLLATE NOCASE,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'player' CHECK (role IN ('player', 'admin'))
            )
        """)
        with db:
            yield db
    finally:
        db.close()


def authenticate_user(email: str, password: str) -> dict | None:
    """Return public account details when the password hash matches."""
    with _accounts() as db:
        user = db.execute("SELECT * FROM users WHERE email = ?", (email.strip().lower(),)).fetchone()
    if user is None or not check_password_hash(user["password_hash"], password):
        return None
    return {key: user[key] for key in ("id", "username", "role")}


def _start_session(user, remember=False):
    session.clear()
    session["user_id"] = user["id"]
    session["username"] = user["username"]
    session["role"] = user["role"]
    session.permanent = remember


def _destination(next_url):
    return next_url if _is_safe_next(next_url) else url_for("core.main")


def _render_account(login_form, signup_form, active_tab, next_url, status=200):
    return render_template("login.html", login_form=login_form, signup_form=signup_form,
                           active_tab=active_tab, next_url=next_url), status


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    next_url = request.values.get("next")
    if get_current_user() is not None:
        return redirect(_destination(next_url))
    form = LoginForm(prefix="login")
    if form.validate_on_submit():
        user = authenticate_user(form.email.data, form.password.data)
        if user is None:
            flash("Invalid email address or password.", "danger")
            return _render_account(form, SignupForm(prefix="signup", formdata=None), "login", next_url, 401)
        _start_session(user, form.remember.data)
        return redirect(_destination(next_url))
    return _render_account(form, SignupForm(prefix="signup", formdata=None), "login", next_url,
                           400 if request.method == "POST" else 200)


@auth_bp.route("/signup", methods=["GET", "POST"])
def signup():
    next_url = request.values.get("next")
    if get_current_user() is not None:
        return redirect(_destination(next_url))
    form = SignupForm(prefix="signup")
    if form.validate_on_submit():
        try:
            with _accounts() as db:
                cursor = db.execute(
                    "INSERT INTO users (username, email, password_hash, role) VALUES (?, ?, ?, ?)",
                    (form.name.data, form.email.data, generate_password_hash(form.password.data), PLAYER),
                )
                user = {"id": cursor.lastrowid, "username": form.name.data, "role": PLAYER}
        except sqlite3.IntegrityError:
            form.email.errors.append("An account with this email address already exists.")
            return _render_account(LoginForm(prefix="login", formdata=None), form, "signup", next_url, 409)
        _start_session(user)
        flash("Your account has been created. Welcome!", "success")
        return redirect(_destination(next_url))
    return _render_account(LoginForm(prefix="login", formdata=None), form, "signup", next_url,
                           400 if request.method == "POST" else 200)


@auth_bp.post("/logout")
def logout():
    """CSRF-protected POST clears the authenticated session."""
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for("auth.login"))
