"""Business workflows for creating and changing itineraries.

Every change a tourist makes (creating, changing or deleting an
itinerary, and adding, moving or removing an item) is recorded through
ActivityLog (Area 2), the same audit trail the other areas use.
"""

from datetime import date, datetime

from app.data.itinerary_repository import ItineraryRepository
from app.data.listing_repository import ListingRepository
from app.models.itinerary import Itinerary, ItineraryItem
from app.models.listing import Listing
from app.services.activity_log import ActivityLog
from app.services.scheduler import Scheduler


class ItineraryError(Exception):
    """Base class for itinerary workflow errors."""


class NotAllowed(ItineraryError):
    """The tourist may not perform this action."""


class ItineraryNotFound(ItineraryError):
    """The requested itinerary does not exist."""


class ListingNotFound(ItineraryError):
    """The requested listing does not exist."""


class InvalidItinerary(ItineraryError):
    """The submitted itinerary details failed validation."""

    def __init__(self, errors):
        """Keep field errors for the route to render."""
        super().__init__("The itinerary details are not valid.")
        self.errors = errors


class ScheduleConflict(ItineraryError):
    """A proposed item conflicts with the schedule or listing hours."""

    def __init__(self, clashes):
        """Keep all Scheduler clash reasons."""
        super().__init__("The proposed time conflicts with the itinerary.")
        self.clashes = clashes


class ItineraryManager:
    """Coordinate itinerary and itinerary-item business rules."""

    def __init__(self, store, repository=None, listing_repository=None,
                 scheduler=None, today=date.today, activity_log=None):
        """Create a manager with repository and scheduling collaborators.

        Args:
            store: The DataStore.
            repository: An ItineraryRepository; one is created if not given.
            listing_repository: A ListingRepository; one is created if
                not given.
            scheduler: A Scheduler; one is created if not given.
            today: Function returning today's date, replaced in tests.
            activity_log: An ActivityLog, or any object with
                ``record(user_id, action, item)``; one is created if not
                given.
        """
        self._repository = repository or ItineraryRepository(store)
        self._listings = listing_repository or ListingRepository(store)
        self._scheduler = scheduler or Scheduler()
        self._today = today
        self._activity_log = activity_log or ActivityLog(store)

    def list_itineraries(self, user):
        """Return all itineraries owned by a tourist."""
        self._require_tourist(user)
        rows = self._repository.list_for_tourist(user.user_id)
        return [Itinerary.from_row(row) for row in rows]

    def get_itinerary(self, user, itinerary_id):
        """Return an owned itinerary with its items."""
        self._require_tourist(user)
        row = self._repository.find_itinerary(itinerary_id)
        if row is None:
            raise ItineraryNotFound("That itinerary no longer exists.")
        if row["tourist_id"] != user.user_id:
            raise NotAllowed("You may access only your own itineraries.")
        items = self._load_items(row["id"])
        return Itinerary.from_row(row, items)

    def create_itinerary(self, user, form):
        """Validate and save a new itinerary."""
        self._require_tourist(user)
        errors = self._validate_dates(form)
        if errors:
            raise InvalidItinerary(errors)
        title = form["title"].strip()
        start_date = form["start_date"].strip()
        end_date = form["end_date"].strip()
        itinerary_id = self._repository.create(
            user.user_id, title, start_date, end_date)
        row = self._repository.find_itinerary(itinerary_id)
        itinerary = Itinerary.from_row(row)
        self._record(user, "itinerary.created", itinerary)
        return itinerary

    def update_itinerary(self, user, itinerary_id, form):
        """Validate and update an owned itinerary."""
        itinerary = self.get_itinerary(user, itinerary_id)
        errors = self._validate_dates(form)
        if errors:
            raise InvalidItinerary(errors)
        start_date = form["start_date"].strip()
        end_date = form["end_date"].strip()
        for item in itinerary.items:
            if item.day < start_date or item.day > end_date:
                errors["end_date"] = (
                    "The date range must include every planned item.")
                raise InvalidItinerary(errors)
        title = form["title"].strip()
        self._repository.update(
            itinerary_id, title, start_date, end_date)
        row = self._repository.find_itinerary(itinerary_id)
        updated = Itinerary.from_row(row, itinerary.items)
        self._record(user, "itinerary.updated", updated)
        return updated

    def delete_itinerary(self, user, itinerary_id):
        """Delete an owned itinerary and its items."""
        itinerary = self.get_itinerary(user, itinerary_id)
        self._repository.delete(itinerary.itinerary_id)
        self._record(user, "itinerary.deleted", itinerary)

    def find_listing(self, listing_id):
        """Return an active Listing object for itinerary scheduling."""
        row = self._listings.find_by_id(listing_id)
        if row is None or not bool(row["is_active"]):
            return None
        return Listing.from_row(row)

    def list_listings(self, text=""):
        """Return active listings for the item form."""
        return [Listing.from_row(row)
                for row in self._repository.find_active_listings(text)]

    def add_item(self, user, itinerary_id, form):
        """Validate and add an item to an owned itinerary."""
        itinerary = self.get_itinerary(user, itinerary_id)
        item = self._save_item(itinerary, None, form)
        self._record(user, "itinerary.item_added", itinerary)
        return item

    def move_item(self, user, itinerary_id, item_id, form):
        """Move or edit an owned itinerary item."""
        itinerary = self.get_itinerary(user, itinerary_id)
        row = self._repository.find_item(item_id, itinerary_id)
        if row is None:
            raise ItineraryNotFound("That itinerary item no longer exists.")
        item = self._save_item(itinerary, row["id"], form)
        self._record(user, "itinerary.item_moved", itinerary)
        return item

    def get_item(self, user, itinerary_id, item_id):
        """Return an owned itinerary item row."""
        self.get_itinerary(user, itinerary_id)
        row = self._repository.find_item(item_id, itinerary_id)
        if row is None:
            raise ItineraryNotFound("That itinerary item no longer exists.")
        return row

    def remove_item(self, user, itinerary_id, item_id):
        """Remove an item from an owned itinerary."""
        itinerary = self.get_itinerary(user, itinerary_id)
        row = self._repository.find_item(item_id, itinerary.itinerary_id)
        if row is None:
            raise ItineraryNotFound("That itinerary item no longer exists.")
        self._repository.delete_item(item_id)
        self._record(user, "itinerary.item_removed", itinerary)

    def _record(self, user, action, itinerary):
        """Record who changed which itinerary, and when."""
        item = f"{itinerary.title} (itinerary #{itinerary.itinerary_id})"
        self._activity_log.record(user.user_id, action, item)

    @staticmethod
    def _require_tourist(user):
        """Reject users who are not tourists."""
        if user is None or user.role != "tourist":
            raise NotAllowed("You must be signed in as a tourist.")

    def _validate_dates(self, form):
        """Validate itinerary title and ISO date range."""
        errors = {}
        title = (form.get("title") or "").strip()
        start_text = (form.get("start_date") or "").strip()
        end_text = (form.get("end_date") or "").strip()
        if not title:
            errors["title"] = "Title cannot be blank."
        elif len(title) > 100:
            errors["title"] = "Title must be at most 100 characters."
        try:
            start = date.fromisoformat(start_text)
        except (TypeError, ValueError):
            errors["start_date"] = "Enter a valid start date."
            start = None
        try:
            end = date.fromisoformat(end_text)
        except (TypeError, ValueError):
            errors["end_date"] = "Enter a valid end date."
            end = None
        if start and end:
            if end < start:
                errors["end_date"] = "End date must be on or after start date."
        return errors

    def _load_items(self, itinerary_id):
        """Load item models, attaching Listing subtype objects."""
        items = []
        for row in self._repository.list_items(itinerary_id):
            listing_row = self._listings.find_by_id(row["listing_id"])
            listing = Listing.from_row(listing_row) if listing_row else None
            items.append(ItineraryItem.from_row(row, listing))
        return items

    def _save_item(self, itinerary, item_id, form):
        """Validate and save a new or changed item."""
        listing_id = self._parse_listing_id(form.get("listing_id"))
        day = (form.get("day") or "").strip()
        start = (form.get("start_time") or "").strip()
        end = (form.get("end_time") or "").strip()
        errors = {}
        if listing_id is None:
            errors["listing_id"] = "Choose a listing."
        try:
            day_date = date.fromisoformat(day)
        except (TypeError, ValueError):
            errors["day"] = "Enter a valid day."
            day_date = None
        if day_date:
            if day < itinerary.start_date or day > itinerary.end_date:
                errors["day"] = (
                    "The day must be within the itinerary date range.")
        if not self._valid_time(start):
            errors["start_time"] = "Enter a start time as HH:MM."
        if not self._valid_time(end):
            errors["end_time"] = "Enter an end time as HH:MM."
        if self._valid_time(start) and self._valid_time(end) and end <= start:
            errors["end_time"] = "End time must be after start time."
        if errors:
            raise InvalidItinerary(errors)

        listing = self.find_listing(listing_id)
        if listing is None:
            raise ListingNotFound(
                "That listing no longer exists or is not active.")
        proposed = {
            "listing_id": listing_id,
            "day": day,
            "start_time": start,
            "end_time": end,
        }
        existing = [item for item in itinerary.items
                    if item_id is None or item.item_id != item_id]
        clashes = self._scheduler.check(proposed, existing, listing)
        if clashes:
            raise ScheduleConflict(clashes)

        if item_id is None:
            item_id = self._repository.insert_item(
                itinerary.itinerary_id, listing_id, day, start, end)
        else:
            self._repository.update_item(
                item_id, listing_id, day, start, end)
        row = self._repository.find_item(item_id)
        return ItineraryItem.from_row(row, listing)

    @staticmethod
    def _parse_listing_id(value):
        """Parse a submitted listing id or return None."""
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _valid_time(value):
        """Say whether a value is a well-formed HH:MM time."""
        try:
            datetime.strptime(value or "", "%H:%M")
            return True
        except (TypeError, ValueError):
            return False
