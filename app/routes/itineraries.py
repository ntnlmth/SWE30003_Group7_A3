"""Area: Plan an itinerary (owner: Rukman).

Placeholder route so the app runs end to end. Replace the index view
with the real screens. Classes for this area: Itinerary, ItineraryItem,
Scheduler.
"""

from flask import Blueprint, render_template

from app.services.authenticator import sign_in_required

blueprint = Blueprint("itineraries", __name__, url_prefix="/itineraries")


@blueprint.route("/")
@sign_in_required("tourist")
def index():
    """Show the area's start screen (placeholder)."""
    return render_template(
        "placeholder.html",
        title="Plan an itinerary",
        owner="Rukman",
        classes="Itinerary, ItineraryItem, Scheduler",
    )
