"""Account validators that do not need additional third-party packages."""

import re

from wtforms.validators import ValidationError


def valid_email(form, field):
    """Check basic email syntax; this does not verify mailbox ownership."""
    if not re.fullmatch(r"[^\s@]+@[^\s@.]+(?:\.[^\s@.]+)+", field.data or ""):
        raise ValidationError("Enter a valid email address.")


def strong_password(form, field):
    """Require at least one letter and one digit for new passwords."""
    password = field.data or ""
    if not any(char.isalpha() for char in password) or not any(char.isdecimal() for char in password):
        raise ValidationError("Include at least one letter and one number in your password.")
