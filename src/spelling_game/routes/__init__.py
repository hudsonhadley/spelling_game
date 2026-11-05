"""Route blueprints.

Blueprints are defined here and imported by the modules that attach routes to
them (api.py, auth.py, core.py).
"""

from flask import Blueprint, Flask

core_bp = Blueprint("core", __name__)
auth_bp = Blueprint("auth", __name__)
api_bp = Blueprint("api", __name__, url_prefix="/api")

# Imported last, after the blueprints exist: importing these modules runs their
# @<blueprint>.route decorators, which attach the views. They must be imported
# before the blueprints are registered on the app.
from . import api, auth, core  # noqa: E402,F401

def register_blueprints(app: Flask) -> None:
    app.register_blueprint(core_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(api_bp)
