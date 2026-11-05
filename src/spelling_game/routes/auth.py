"""Login, logout, and access-control helpers.

Two user roles exist:
  - PLAYER: can play the game.
  - ADMIN:  can also manage the word list.
"""

from functools import wraps

from flask import (
    abort,
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
    if "user_id" not in session:
        return None
    return {
        "id": session["user_id"],
        "username": session["username"],
        "role": session["role"],
    }


@auth_bp.app_context_processor
def inject_current_user():
    """Make `current_user` available in every template."""
    return {"current_user": get_current_user(), "ADMIN": ADMIN, "PLAYER": PLAYER}


def _is_safe_next(target: str | None) -> bool:
    """Only allow redirects to paths on this site (prevents open redirects)."""
    return bool(
        target
        and target.startswith("/")
        and not target.startswith("//")
        and "\\" not in target
    )


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
# TODO: replace with real database lookups once the models exist
# --------------------------------------------------------------------------
def authenticate_user(username: str, password: str) -> dict | None:
    """Check credentials. Return {"id", "username", "role"} or None.

    TODO: look the user up in the database and verify the password against its
    stored hash (e.g. werkzeug.security.check_password_hash). Until then no one
    can log in.
    """
    return None


# --------------------------------------------------------------------------
# Routes
# --------------------------------------------------------------------------
@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if get_current_user() is not None:
        return redirect(url_for("core.game"))

    next_url = request.values.get("next")

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        if not username or not password:
            flash("Enter both a username and a password.", "danger")
            return render_template("login.html", next_url=next_url), 400

        user = authenticate_user(username, password)
        if user is None:
            flash("Invalid username or password.", "danger")
            return render_template("login.html", next_url=next_url), 401

        session.clear()  # drop any stale data from before login
        session["user_id"] = user["id"]
        session["username"] = user["username"]
        session["role"] = user["role"]

        if _is_safe_next(next_url):
            return redirect(next_url)
        return redirect(url_for("core.game"))

    return render_template("login.html", next_url=next_url)


@auth_bp.post("/logout")
def logout():
    """POST-only so a stray link or image can't log the user out."""
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for("auth.login"))
