"""Small input checks shared by every form.

Each function returns an error message, or None when the value is
valid, so a form can collect all its errors and show them together.
"""

import re

EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def require(value, label):
    """Return an error if ``value`` is blank."""
    if value is None or not str(value).strip():
        return f"{label} cannot be blank."
    return None


def check_length(value, label, minimum=0, maximum=None):
    """Return an error if ``value`` is outside the allowed length."""
    length = len(value or "")
    if length < minimum:
        return f"{label} must be at least {minimum} characters."
    if maximum is not None and length > maximum:
        return f"{label} must be at most {maximum} characters."
    return None


def check_email(value):
    """Return an error if ``value`` is not an email address."""
    if not EMAIL_PATTERN.match(value or ""):
        return "Enter a valid email address, such as name@example.com."
    return None


def check_number(value, label, minimum=None):
    """Return an error if ``value`` is not a number at or above minimum."""
    try:
        number = float(value)
    except (TypeError, ValueError):
        return f"{label} must be a number."
    if minimum is not None and number < minimum:
        return f"{label} must be {minimum} or more."
    return None


def first_error(*errors):
    """Return the first non-empty error from several checks."""
    for error in errors:
        if error:
            return error
    return None
