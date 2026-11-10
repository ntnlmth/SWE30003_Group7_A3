"""Authenticator: registers users, checks sign-in and permissions.

Implements CRC card 5.25. Passwords are stored only as salted hashes
(detailed-design change, report Section 2.3).
"""

from functools import wraps

from flask import current_app, flash, g, redirect, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from app.models.user import User
from app.services.form_validation import (check_email, check_length,
                                          first_error, require)

ROLES = ("tourist", "operator", "admin")
SELF_REGISTER_ROLES = ("tourist", "operator")


class Authenticator:
    """Check who a user is and what they may do."""

    def __init__(self, store):
        """Create an Authenticator that reads accounts from ``store``."""
        self._store = store

    def validate_registration(self, name, email, password, role):
        """Return a dict of field errors for a registration form."""
        errors = {}
        name_error = first_error(require(name, "Name"),
                                 check_length(name, "Name", maximum=80))
        if name_error:
            errors["name"] = name_error
        email_error = first_error(require(email, "Email"),
                                  check_email(email))
        if not email_error and self.find_by_email(email) is not None:
            email_error = "An account with this email already exists."
        if email_error:
            errors["email"] = email_error
        password_error = first_error(
            require(password, "Password"),
            check_length(password, "Password", minimum=8))
        if password_error:
            errors["password"] = password_error
        if role not in SELF_REGISTER_ROLES:
            errors["role"] = "Choose Tourist or Operator."
        return errors

    def register(self, name, email, password, role):
        """Create an account and return the new User."""
        user_id = self._store.execute(
            "INSERT INTO users (role, name, email, password_hash) "
            "VALUES (?, ?, ?, ?)",
            (role, name.strip(), email.strip().lower(),
             generate_password_hash(password)),
        )
        return self.find_by_id(user_id)

    def sign_in(self, email, password):
        """Return the User if the details match, otherwise None."""
        row = self._store.find_one(
            "SELECT * FROM users WHERE email = ?",
            ((email or "").strip().lower(),))
        if row is None or not check_password_hash(row["password_hash"],
                                                  password or ""):
            return None
        return User.from_row(row)

    def find_by_id(self, user_id):
        """Return the User with this id, or None."""
        row = self._store.find_one(
            "SELECT * FROM users WHERE id = ?", (user_id,))
        return User.from_row(row) if row else None

    def find_by_email(self, email):
        """Return the User with this email, or None."""
        row = self._store.find_one(
            "SELECT * FROM users WHERE email = ?",
            ((email or "").strip().lower(),))
        return User.from_row(row) if row else None

    @staticmethod
    def may_change_listing(user, listing_operator_id):
        """Say whether ``user`` may change a listing (Solution 1 rule).

        Admin staff may change any listing; an operator only its own.
        """
        if user is None:
            return False
        if user.role == "admin":
            return True
        return user.role == "operator" and user.user_id == listing_operator_id


def get_authenticator():
    """Return the application's Authenticator."""
    return current_app.extensions["authenticator"]


def load_current_user():
    """Put the signed-in user, if any, on ``g.user`` for this request."""
    user_id = session.get("user_id")
    g.user = get_authenticator().find_by_id(user_id) if user_id else None


def sign_in_required(*roles):
    """Decorate a route so only signed-in users with these roles reach it.

    With no roles given, any signed-in user may use the route.
    """
    def decorator(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            if g.get("user") is None:
                flash("Please sign in first.", "error")
                return redirect(url_for("auth.sign_in", next=request.path))
            if roles and g.user.role not in roles:
                flash("You do not have access to that page.", "error")
                return redirect(url_for("main.home"))
            return view(*args, **kwargs)
        return wrapped
    return decorator
