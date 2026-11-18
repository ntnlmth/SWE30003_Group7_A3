"""Area: Manage listings (owner: Anisa).

Screens for operators and admin staff to add, change, deactivate and
delete listings. The route handlers only read the request, call
ListingManager and show the outcome; every rule lives in ListingManager,
DataValidator and the Listing classes.
"""

from flask import (Blueprint, abort, current_app, flash, g, redirect,
                   render_template, request, url_for)

from app.controllers.listing_manager import (InvalidListing, ListingManager,
                                             ListingNotFound, NotAllowed,
                                             PossibleDuplicate)
from app.data.data_store import DataStore
from app.models.listing import Listing
from app.services.authenticator import sign_in_required
from app.services.data_validator import MANAGEABLE_TYPES

blueprint = Blueprint("listings", __name__, url_prefix="/listings")


@blueprint.record_once
def create_listing_manager(state):
    """Bootstrap step: create the ListingManager with the application."""
    state.app.extensions["listing_manager"] = ListingManager(
        DataStore.get_instance())


def get_listing_manager():
    """Return the application's ListingManager."""
    return current_app.extensions["listing_manager"]


def _type_choices(types):
    """Return (type, label) pairs for a drop-down or a list of links."""
    return [(name, Listing.subtype_for(name).TYPE_LABEL) for name in types]


def _back_to_list(message):
    """Flash an error and go back to the listing table."""
    flash(message, "error")
    return redirect(url_for("listings.index"))


@blueprint.route("/")
@sign_in_required("operator", "admin")
def index():
    """Show the listings this user manages, with search and filters."""
    manager = get_listing_manager()
    filters = {
        "listing_type": request.args.get("type", ""),
        "status": request.args.get("status", ""),
        "search": request.args.get("q", ""),
    }
    return render_template(
        "listings/index.html",
        listings=manager.list_listings(g.user, **filters),
        filters=filters,
        filter_types=_type_choices(MANAGEABLE_TYPES),
        add_types=_type_choices(manager.creatable_types(g.user)),
    )


@blueprint.route("/new/<listing_type>", methods=["GET", "POST"])
@sign_in_required("operator", "admin")
def new(listing_type):
    """Show the add form for one type of listing and save it."""
    if listing_type not in MANAGEABLE_TYPES:
        abort(404)
    manager = get_listing_manager()
    form, errors, duplicate = {}, {}, None
    if request.method == "POST":
        form = request.form.to_dict()
        try:
            listing = manager.create_listing(
                g.user, listing_type, form,
                confirm_duplicate=request.form.get("confirm_duplicate") == "1")
        except NotAllowed as error:
            return _back_to_list(str(error))
        except InvalidListing as error:
            errors = error.errors
        except PossibleDuplicate as error:
            duplicate = error.existing
        else:
            flash(f"“{listing.name}” has been added.", "success")
            return redirect(url_for("listings.index"))
    return render_template(
        "listings/form.html", mode="new",
        kind=Listing.subtype_for(listing_type), form=form, errors=errors,
        duplicate=duplicate, heading="Add a listing")


@blueprint.route("/<int:listing_id>/edit", methods=["GET", "POST"])
@sign_in_required("operator", "admin")
def edit(listing_id):
    """Show the edit form for a listing and save the changes."""
    manager = get_listing_manager()
    try:
        listing = manager.get_listing_for_change(g.user, listing_id)
    except (NotAllowed, ListingNotFound) as error:
        return _back_to_list(str(error))
    form, errors, duplicate = listing.form_values(), {}, None
    if request.method == "POST":
        form = request.form.to_dict()
        try:
            saved = manager.update_listing(
                g.user, listing_id, form,
                confirm_duplicate=request.form.get("confirm_duplicate") == "1")
        except (NotAllowed, ListingNotFound) as error:
            return _back_to_list(str(error))
        except InvalidListing as error:
            errors = error.errors
        except PossibleDuplicate as error:
            duplicate = error.existing
        else:
            flash(f"“{saved.name}” has been updated.", "success")
            return redirect(url_for("listings.index"))
    return render_template(
        "listings/form.html", mode="edit", kind=type(listing), form=form,
        errors=errors, duplicate=duplicate, listing=listing,
        heading=f"Edit {listing.name}")


@blueprint.route("/<int:listing_id>/remove", methods=["GET", "POST"])
@sign_in_required("operator", "admin")
def remove(listing_id):
    """Ask for confirmation, then deactivate or delete a listing."""
    manager = get_listing_manager()
    try:
        listing = manager.get_listing_for_change(g.user, listing_id)
        if request.method == "POST":
            result = manager.remove_listing(g.user, listing_id)
            flash(_removal_message(result), "success")
            return redirect(url_for("listings.index"))
    except (NotAllowed, ListingNotFound) as error:
        return _back_to_list(str(error))
    return render_template(
        "listings/remove.html", listing=listing,
        references=manager.find_references(listing_id))


@blueprint.route("/<int:listing_id>/reactivate", methods=["POST"])
@sign_in_required("operator", "admin")
def reactivate(listing_id):
    """Make a deactivated listing visible to tourists again."""
    try:
        listing = get_listing_manager().reactivate_listing(
            g.user, listing_id)
    except (NotAllowed, ListingNotFound) as error:
        return _back_to_list(str(error))
    flash(f"“{listing.name}” is visible to tourists again.", "success")
    return redirect(url_for("listings.index"))


def _removal_message(result):
    """Return the success message for a removal result."""
    if result.outcome == "deleted":
        return f"“{result.listing_name}” has been deleted."
    bookings = len(result.references.upcoming_bookings)
    items = len(result.references.upcoming_items)
    return (f"“{result.listing_name}” is now hidden from tourists but "
            f"its record is kept. Affected: {bookings} upcoming "
            f"booking(s) and {items} itinerary item(s).")
