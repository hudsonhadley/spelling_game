"""Account validators that do not need additional third-party packages."""

import re

from wtforms.validators import ValidationError


def valid_email(form, field):
    """Check basic email syntax; this does not verify mailbox ownership."""
    if not re.fullmatch(r"[^\s@]+@[^\s@.]+(?:\.[^\s@.]+)+", field.data or ""):
        raise ValidationError("Enter a valid email address.")
