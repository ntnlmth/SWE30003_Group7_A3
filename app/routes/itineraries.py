"""Area: Plan an itinerary (owner: Rukman)."""

from flask import (Blueprint, current_app, flash, g, redirect,
                   render_template, request, url_for)

from app.controllers.itinerary_manager import (InvalidItinerary,
                                               ItineraryManager,
                                               ItineraryNotFound,
                                               ListingNotFound,
                                               NotAllowed,
                                               ScheduleConflict)
from app.data.data_store import DataStore
from app.services.authenticator import sign_in_required

blueprint = Blueprint("itineraries", __name__, url_prefix="/itineraries")


@blueprint.record_once
def create_itinerary_manager(state):
    """Bootstrap step: create the itinerary manager with the app."""
    state.app.extensions["itinerary_manager"] = ItineraryManager(
        DataStore.get_instance())


def get_itinerary_manager():
    """Return the application's ItineraryManager."""
    return current_app.extensions["itinerary_manager"]


@blueprint.route("/")
@sign_in_required("tourist")
def index():
    """Show this tourist's itineraries."""
    return render_template("itineraries/index.html",
                           itineraries=get_itinerary_manager()
                           .list_itineraries(g.user))


@blueprint.route("/new", methods=["GET", "POST"])
@sign_in_required("tourist")
def new():
    """Create a new itinerary."""
    form = {"title": "", "start_date": "", "end_date": ""}
    errors = {}
    if request.method == "POST":
        form = request.form.to_dict()
        try:
            itinerary = get_itinerary_manager().create_itinerary(
                g.user, form)
        except InvalidItinerary as error:
            errors = error.errors
        else:
            flash(f"“{itinerary.title}” has been created.", "success")
            return redirect(url_for(
                "itineraries.detail",
                itinerary_id=itinerary.itinerary_id))
    return render_template(
        "itineraries/form.html", mode="new", form=form, errors=errors)


@blueprint.route("/<int:itinerary_id>")
@sign_in_required("tourist")
def detail(itinerary_id):
    """Show one itinerary and its day/time items."""
    try:
        itinerary = get_itinerary_manager().get_itinerary(
            g.user, itinerary_id)
    except (ItineraryNotFound, NotAllowed) as error:
        flash(str(error), "error")
        return redirect(url_for("itineraries.index"))
    return render_template("itineraries/detail.html", itinerary=itinerary)


@blueprint.route("/<int:itinerary_id>/edit", methods=["GET", "POST"])
@sign_in_required("tourist")
def edit(itinerary_id):
    """Edit an itinerary's title or date range."""
    manager = get_itinerary_manager()
    try:
        itinerary = manager.get_itinerary(g.user, itinerary_id)
    except (ItineraryNotFound, NotAllowed) as error:
        flash(str(error), "error")
        return redirect(url_for("itineraries.index"))
    form = {"title": itinerary.title,
            "start_date": itinerary.start_date,
            "end_date": itinerary.end_date}
    errors = {}
    if request.method == "POST":
        form = request.form.to_dict()
        try:
            saved = manager.update_itinerary(g.user, itinerary_id, form)
        except InvalidItinerary as error:
            errors = error.errors
        except (ItineraryNotFound, NotAllowed) as error:
            flash(str(error), "error")
            return redirect(url_for("itineraries.index"))
        else:
            flash(f"“{saved.title}” has been updated.", "success")
            return redirect(url_for(
                "itineraries.detail", itinerary_id=itinerary_id))
    return render_template(
        "itineraries/form.html", mode="edit", form=form,
        errors=errors, itinerary=itinerary)


@blueprint.route("/<int:itinerary_id>/delete", methods=["POST"])
@sign_in_required("tourist")
def delete(itinerary_id):
    """Delete an owned itinerary."""
    try:
        get_itinerary_manager().delete_itinerary(g.user, itinerary_id)
    except (ItineraryNotFound, NotAllowed) as error:
        flash(str(error), "error")
    else:
        flash("Itinerary deleted.", "success")
    return redirect(url_for("itineraries.index"))


@blueprint.route("/<int:itinerary_id>/items/new",
                 methods=["GET", "POST"])
@sign_in_required("tourist")
def add_item(itinerary_id):
    """Add a listing to a time slot."""
    manager = get_itinerary_manager()
    try:
        itinerary = manager.get_itinerary(g.user, itinerary_id)
    except (ItineraryNotFound, NotAllowed) as error:
        flash(str(error), "error")
        return redirect(url_for("itineraries.index"))
    form = {
        "listing_id": request.args.get("listing_id", ""),
        "day": itinerary.start_date,
        "start_time": "09:00",
        "end_time": "10:00",
    }
    errors, clashes = {}, []
    if request.method == "POST":
        form = request.form.to_dict()
        try:
            manager.add_item(g.user, itinerary_id, form)
        except InvalidItinerary as error:
            errors = error.errors
        except ListingNotFound as error:
            flash(str(error), "error")
        except ScheduleConflict as error:
            clashes = error.clashes
        except (ItineraryNotFound, NotAllowed) as error:
            flash(str(error), "error")
            return redirect(url_for("itineraries.index"))
        else:
            flash("Activity added to the itinerary.", "success")
            return redirect(url_for(
                "itineraries.detail", itinerary_id=itinerary_id))
    return render_template(
        "itineraries/item_form.html", mode="new", itinerary=itinerary,
        listings=manager.list_listings(), form=form, errors=errors,
        clashes=clashes)


@blueprint.route("/<int:itinerary_id>/items/<int:item_id>/edit",
                 methods=["GET", "POST"])
@sign_in_required("tourist")
def edit_item(itinerary_id, item_id):
    """Move or change an itinerary item."""
    manager = get_itinerary_manager()
    try:
        itinerary = manager.get_itinerary(g.user, itinerary_id)
        row = manager.get_item(g.user, itinerary_id, item_id)
    except (ItineraryNotFound, NotAllowed) as error:
        flash(str(error), "error")
        return redirect(url_for("itineraries.index"))
    form = {
        "listing_id": str(row["listing_id"]),
        "day": row["day"],
        "start_time": row["start_time"],
        "end_time": row["end_time"],
    }
    errors, clashes = {}, []
    if request.method == "POST":
        form = request.form.to_dict()
        try:
            manager.move_item(g.user, itinerary_id, item_id, form)
        except InvalidItinerary as error:
            errors = error.errors
        except ListingNotFound as error:
            flash(str(error), "error")
        except ScheduleConflict as error:
            clashes = error.clashes
        except (ItineraryNotFound, NotAllowed) as error:
            flash(str(error), "error")
            return redirect(url_for("itineraries.index"))
        else:
            flash("Activity updated.", "success")
            return redirect(url_for(
                "itineraries.detail", itinerary_id=itinerary_id))
    return render_template(
        "itineraries/item_form.html", mode="edit", itinerary=itinerary,
        listings=manager.list_listings(), form=form, errors=errors,
        clashes=clashes)


@blueprint.route("/<int:itinerary_id>/items/<int:item_id>/delete",
                 methods=["POST"])
@sign_in_required("tourist")
def delete_item(itinerary_id, item_id):
    """Remove an item from an owned itinerary."""
    try:
        get_itinerary_manager().remove_item(g.user, itinerary_id, item_id)
    except (ItineraryNotFound, NotAllowed) as error:
        flash(str(error), "error")
    else:
        flash("Activity removed.", "success")
    return redirect(url_for(
        "itineraries.detail", itinerary_id=itinerary_id))
