"""Area: Manage listings (owner: Anisa).

Placeholder route so the app runs end to end. Replace the index view
with the real screens. Classes for this area: ListingManager,
DataValidator, Listing subtypes.
"""

from flask import Blueprint, render_template

from app.services.authenticator import sign_in_required

blueprint = Blueprint("listings", __name__, url_prefix="/listings")


@blueprint.route("/")
@sign_in_required("operator", "admin")
def index():
    """Show the area's start screen (placeholder)."""
    return render_template(
        "placeholder.html",
        title="Manage listings",
        owner="Anisa",
        classes="ListingManager, DataValidator, Listing subtypes",
    )
