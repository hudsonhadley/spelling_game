"""Routes that render the site's main HTML pages."""

from flask import render_template

from spelling_game.routes import core_bp
from spelling_game.routes.auth import admin_required, login_required


@core_bp.get("/")
def main():
    """Public home page."""
    return render_template("main.html")


@core_bp.get("/game")
@login_required
def game():
    """The spelling game. Any logged-in user."""
    return render_template("game.html")


@core_bp.get("/words")
@admin_required
def words():
    """Word list management. Admins only."""
    return render_template("words.html")
