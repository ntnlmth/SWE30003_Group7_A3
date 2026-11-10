"""Area: Search and book accommodation (owner: Badrul).

Placeholder route so the app runs end to end. Replace the index view
with the real screens. Classes for this area: ListingCatalogue,
Accommodation, BookingManager, Booking.
"""

from flask import Blueprint, render_template

from app.services.authenticator import sign_in_required

blueprint = Blueprint("bookings", __name__, url_prefix="/bookings")


@blueprint.route("/")
@sign_in_required("tourist")
def index():
    """Show the area's start screen (placeholder)."""
    return render_template(
        "placeholder.html",
        title="Search and book accommodation",
        owner="Badrul",
        classes=(
            "ListingCatalogue, Accommodation, BookingManager, "
            "Booking"
        ),
    )
