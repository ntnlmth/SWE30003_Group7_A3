"""Register, sign in and sign out screens."""

from flask import (Blueprint, flash, redirect, render_template, request,
                   session, url_for)

from app.services.authenticator import get_authenticator

blueprint = Blueprint("auth", __name__, url_prefix="/auth")


def _safe_next(target):
    """Return ``target`` only if it is a path on this site."""
    if target and target.startswith("/") and not target.startswith("//"):
        return target
    return url_for("main.home")


@blueprint.route("/register", methods=["GET", "POST"])
def register():
    """Show the registration form and create an account."""
    form = {"name": "", "email": "", "role": "tourist"}
    errors = {}
    if request.method == "POST":
        form = {
            "name": request.form.get("name", ""),
            "email": request.form.get("email", ""),
            "role": request.form.get("role", ""),
        }
        password = request.form.get("password", "")
        authenticator = get_authenticator()
        errors = authenticator.validate_registration(
            form["name"], form["email"], password, form["role"])
        if not errors:
            user = authenticator.register(
                form["name"], form["email"], password, form["role"])
            session.clear()
            session["user_id"] = user.user_id
            flash(f"Welcome, {user.name}. Your account has been created.",
                  "success")
            return redirect(url_for("main.home"))
    return render_template("auth/register.html", form=form, errors=errors)


@blueprint.route("/sign-in", methods=["GET", "POST"])
def sign_in():
    """Show the sign-in form and start a session."""
    email = ""
    error = None
    if request.method == "POST":
        email = request.form.get("email", "")
        password = request.form.get("password", "")
        if not email.strip() or not password:
            error = "Enter both your email and password."
        else:
            user = get_authenticator().sign_in(email, password)
            if user is None:
                error = "Email or password is incorrect."
            else:
                session.clear()
                session["user_id"] = user.user_id
                flash(f"Signed in as {user.name}.", "success")
                return redirect(_safe_next(request.args.get("next")))
    return render_template("auth/sign_in.html", email=email, error=error)


@blueprint.route("/sign-out", methods=["POST"])
def sign_out():
    """End the session and return to the home screen."""
    session.clear()
    flash("You have signed out.", "success")
    return redirect(url_for("main.home"))
