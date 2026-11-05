"""Spelling game Flask application package."""

from typing import Any

from flask_wtf.csrf import CSRFProtect

csrf = CSRFProtect()


def create_app(config: Any = None):
    """Application factory: build and configure the Flask app.

    `config` is a config object or class; if omitted, get_config() supplies it.
    """
    from flask import Flask

    flask_app = Flask(__name__)

    if config is None:
        from .config import get_config

        config = get_config()
    flask_app.config.from_object(config)

    # Rejects POST/PUT/PATCH/DELETE requests that lack a valid CSRF token.
    # Forms must include {{ csrf_token() }}; fetch() calls must send it in an
    # "X-CSRFToken" header.
    csrf.init_app(flask_app)

    from .routes import register_blueprints

    register_blueprints(flask_app)

    return flask_app
