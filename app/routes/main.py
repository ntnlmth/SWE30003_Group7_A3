"""Home screen and per-request setup."""

from flask import Blueprint, render_template

from app.services.authenticator import load_current_user

blueprint = Blueprint("main", __name__)

AREAS = [
    ("bookings.index", "Search and book accommodation",
     "Find a place to stay and reserve it."),
    ("payments.index", "Pay for a booking",
     "Pay for a pending booking (simulated payment)."),
    ("itineraries.index", "Plan an itinerary",
     "Build a day-by-day trip plan with clash checks."),
    ("listings.index", "Manage listings",
     "Operators and admin staff add and update listings."),
]


@blueprint.before_app_request
def before_request():
    """Load the signed-in user before every request."""
    load_current_user()


@blueprint.route("/")
def home():
    """Show the home screen with the four areas."""
    return render_template("home.html", areas=AREAS)
