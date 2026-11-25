"""Area: Search and book accommodation (owner: Badrul).

Screens for a tourist to search accommodation, book it and cancel a
booking. As with Manage listings, the route handlers only read the
request, call BookingManager or ListingCatalogue, and show the outcome;
every rule lives in those two controllers.
"""

from flask import (Blueprint, current_app, flash, g, redirect,
                   render_template, request, url_for)

from app.controllers.booking_manager import (BookingManager, BookingNotFound,
                                             CannotCancel, InvalidBooking,
                                             ListingNotFound, NotAllowed,
                                             NotAvailable)
from app.controllers.listing_catalogue import ListingCatalogue
from app.data.data_store import DataStore
from app.services.activity_log import ActivityLog
from app.services.authenticator import sign_in_required

blueprint = Blueprint("bookings", __name__, url_prefix="/bookings")


@blueprint.record_once
def create_booking_services(state):
    """Bootstrap step: create this area's controllers with the app."""
    store = DataStore.get_instance()
    catalogue = ListingCatalogue(store)
    state.app.extensions["listing_catalogue"] = catalogue
    state.app.extensions["booking_manager"] = BookingManager(
        store, catalogue=catalogue, activity_log=ActivityLog(store))


def get_catalogue():
    """Return the application's ListingCatalogue."""
    return current_app.extensions["listing_catalogue"]


def get_booking_manager():
    """Return the application's BookingManager."""
    return current_app.extensions["booking_manager"]


def _back_to_search(message):
    """Flash an error and go back to the search screen."""
    flash(message, "error")
    return redirect(url_for("bookings.index"))


@blueprint.route("/")
@sign_in_required("tourist")
def index():
    """Show the search screen, with results once a search is run."""
    filters = {
        "location": request.args.get("location", ""),
        "check_in": request.args.get("check_in", ""),
        "check_out": request.args.get("check_out", ""),
    }
    searched = any(filters.values())
    results = []
    if searched:
        results = get_catalogue().search_accommodation(
            location=filters["location"],
            check_in=filters["check_in"] or None,
            check_out=filters["check_out"] or None)
    return render_template(
        "bookings/search.html", filters=filters, results=results,
        searched=searched)


@blueprint.route("/<int:listing_id>/book", methods=["GET", "POST"])
@sign_in_required("tourist")
def book(listing_id):
    """Show the booking form for one accommodation and save it."""
    accommodation = get_catalogue().find_bookable(listing_id)
    if accommodation is None:
        return _back_to_search("That accommodation is not available.")
    form = {
        "check_in": request.args.get("check_in", ""),
        "check_out": request.args.get("check_out", ""),
        "guests": "2",
    }
    errors, not_available = {}, None
    if request.method == "POST":
        form = request.form.to_dict()
        try:
            get_booking_manager().book(g.user, listing_id, form)
        except NotAllowed as error:
            return _back_to_search(str(error))
        except ListingNotFound as error:
            return _back_to_search(str(error))
        except InvalidBooking as error:
            errors = error.errors
        except NotAvailable as error:
            not_available = error.available_rooms
        else:
            flash(
                f"Booking for “{accommodation.name}” has been created "
                "and is pending payment.", "success")
            return redirect(url_for("bookings.mine"))
    return render_template(
        "bookings/book.html", accommodation=accommodation, form=form,
        errors=errors, not_available=not_available)


@blueprint.route("/mine")
@sign_in_required("tourist")
def mine():
    """Show this tourist's bookings, with a cancel option when allowed."""
    return render_template(
        "bookings/mine.html",
        views=get_booking_manager().list_bookings(g.user))


@blueprint.route("/<int:booking_id>/cancel", methods=["GET", "POST"])
@sign_in_required("tourist")
def cancel(booking_id):
    """Ask for confirmation, then cancel a booking."""
    manager = get_booking_manager()
    try:
        if request.method == "POST":
            manager.cancel_booking(g.user, booking_id)
            flash("Booking cancelled.", "success")
            return redirect(url_for("bookings.mine"))
        booking = manager.get_booking_for_cancel(g.user, booking_id)
    except (BookingNotFound, NotAllowed, CannotCancel) as error:
        flash(str(error), "error")
        return redirect(url_for("bookings.mine"))
    return render_template("bookings/cancel.html", booking=booking)
