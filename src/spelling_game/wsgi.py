"""WSGI entry point.

Run locally with:  flask --app spelling_game.wsgi run --debug
"""

from . import create_app

app = create_app()
