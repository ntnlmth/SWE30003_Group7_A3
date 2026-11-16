"""ListingManager: coordinates the life of every listing (card 5.21).

It checks who may do what, has details validated, saves the outcome and
records who changed what. It holds no listing data of its own: the
details live in the Listing classes and in the database, reached through
DataStore.

Detailed-design changes from Assignment 2 (for the report):

* Problems are reported by raising small exceptions (``NotAllowed``,
  ``InvalidListing``, ``PossibleDuplicate``) instead of returning codes,
  so the route modules contain no business rules.
* A listing is deleted only when no booking or itinerary item has ever
  referred to it, because the database would refuse the delete. If any
  record refers to it, it is deactivated. The upcoming ones are listed as
  the affected items.
* The audit record goes to ``activity_log`` through ``activity_log.record``
  when an ActivityLog object is supplied, and straight to the table
  otherwise.
"""

from dataclasses import dataclass, field
from datetime import date

from app.models.listing import Listing
from app.services.authenticator import Authenticator
from app.services.data_validator import (MANAGEABLE_TYPES, TYPES_WITH_HOURS,
                                         DataValidator, parse_time)

# Assumption A-1: attractions are maintained by admin staff only.
OPERATOR_TYPES = tuple(t for t in MANAGEABLE_TYPES if t != "attraction")


class ListingError(Exception):
    """Base class for problems ListingManager reports."""


class NotAllowed(ListingError):
    """The user may not do this action."""


class ListingNotFound(ListingError):
    """No listing has the requested id."""


class InvalidListing(ListingError):
    """The submitted details failed validation."""

    def __init__(self, errors):
        """Keep the dict of field errors for the form to show."""
        super().__init__("The listing details are not valid.")
        self.errors = errors


class PossibleDuplicate(ListingError):
    """The details look like a listing that already exists."""

    def __init__(self, existing):
        """Keep the existing Listing so the screen can show it."""
        super().__init__("This looks like an existing listing.")
        self.existing = existing


@dataclass
class References:
    """What still refers to a listing."""

    upcoming_bookings: list = field(default_factory=list)
    upcoming_items: list = field(default_factory=list)
    has_records: bool = False

    @property
    def has_upcoming(self):
        """Say whether any booking or itinerary item is still ahead."""
        return bool(self.upcoming_bookings or self.upcoming_items)


@dataclass
class RemovalResult:
    """The outcome of removing a listing."""

    outcome: str
    listing_name: str
    references: References


class ListingManager:
    """Add, change, deactivate and delete listings for operators/admins."""

    def __init__(self, store, validator=None, activity_log=None,
                 today=date.today):
        """Create a manager that saves through ``store``.

        Args:
            store: The DataStore.
            validator: A DataValidator; one is created if not given.
            activity_log: Optional object with ``record(user_id, action,
                item)``. Without it, entries are written to the table.
            today: Function returning today's date, replaced in tests.
        """
        self._store = store
        self._validator = validator or DataValidator(store)
        self._activity_log = activity_log
        self._today = today

    # ------------------------------------------------------------------
    # Questions

    @staticmethod
    def creatable_types(user):
        """Return the listing types ``user`` may add."""
        if user is None:
            return ()
        if user.role == "admin":
            return MANAGEABLE_TYPES
        if user.role == "operator":
            return OPERATOR_TYPES
        return ()

    def find_listing(self, listing_id):
        """Return the Listing with this id, or None."""
        row = self._store.find_one(
            "SELECT * FROM listings WHERE id = ?", (listing_id,))
        return Listing.from_row(row) if row else None

    def get_listing_for_change(self, user, listing_id):
        """Return the Listing if ``user`` may change it.

        Raises:
            ListingNotFound: No listing has this id.
            NotAllowed: The user may not change this listing.
        """
        listing = self.find_listing(listing_id)
        if listing is None:
            raise ListingNotFound("That listing no longer exists.")
        self._require_may_change(user, listing)
        return listing

    def list_listings(self, user, listing_type="", status="", search=""):
        """Return the listings ``user`` manages, optionally filtered.

        Admin staff see every listing; an operator sees only its own.
        """
        sql = "SELECT * FROM listings WHERE listing_type IN ({})".format(
            ", ".join("?" for _ in MANAGEABLE_TYPES))
        params = list(MANAGEABLE_TYPES)
        if user.role == "operator":
            sql += " AND operator_id = ?"
            params.append(user.user_id)
        if listing_type in MANAGEABLE_TYPES:
            sql += " AND listing_type = ?"
            params.append(listing_type)
        if status in ("active", "deactivated"):
            sql += " AND is_active = ?"
            params.append(1 if status == "active" else 0)
        if search.strip():
            sql += " AND (name LIKE ? OR location LIKE ?)"
            like = f"%{search.strip()}%"
            params.extend([like, like])
        sql += " ORDER BY lower(name)"
        return [Listing.from_row(row)
                for row in self._store.find_all(sql, tuple(params))]

    def find_references(self, listing_id):
        """Return the bookings and itinerary items that refer to a listing.

        ``upcoming_*`` hold those still ahead (shown to the admin);
        ``has_records`` is True if any booking or itinerary item at all
        refers to the listing, which decides delete versus deactivate.
        """
        today = self._today().isoformat()
        bookings = self._store.find_all(
            "SELECT b.id, b.check_in, b.check_out, b.status, "
            "u.name AS tourist_name FROM bookings b "
            "JOIN users u ON u.id = b.tourist_id "
            "WHERE b.listing_id = ? AND b.status != 'cancelled' "
            "AND b.check_out >= ? ORDER BY b.check_in",
            (listing_id, today))
        items = self._store.find_all(
            "SELECT ii.id, ii.day, ii.start_time, ii.end_time, "
            "i.title AS itinerary_title, u.name AS tourist_name "
            "FROM itinerary_items ii "
            "JOIN itineraries i ON i.id = ii.itinerary_id "
            "JOIN users u ON u.id = i.tourist_id "
            "WHERE ii.listing_id = ? AND ii.day >= ? ORDER BY ii.day",
            (listing_id, today))
        any_booking = self._store.find_one(
            "SELECT id FROM bookings WHERE listing_id = ? LIMIT 1",
            (listing_id,))
        any_item = self._store.find_one(
            "SELECT id FROM itinerary_items WHERE listing_id = ? LIMIT 1",
            (listing_id,))
        return References(bookings, items,
                          any_booking is not None or any_item is not None)

    # ------------------------------------------------------------------
    # Changes

    def create_listing(self, user, listing_type, form,
                       confirm_duplicate=False):
        """Validate and add a new listing, returning the saved Listing.

        Raises:
            NotAllowed: The user may not add this type of listing.
            InvalidListing: A field failed validation.
            PossibleDuplicate: It looks like an existing listing and
                ``confirm_duplicate`` is False.
        """
        if listing_type not in self.creatable_types(user):
            raise NotAllowed("You may not add that type of listing.")
        self._check_details(listing_type, form, confirm_duplicate)
        values = self._clean(listing_type, form)
        operator_id = user.user_id if user.role == "operator" else None
        listing_id = self._store.execute(
            "INSERT INTO listings (listing_type, operator_id, name, "
            "location, description, price, contact_phone, opening_time, "
            "closing_time, room_count) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (listing_type, operator_id, values["name"],
             values["location"], values["description"], values["price"],
             values["contact_phone"], values["opening_time"],
             values["closing_time"], values["room_count"]))
        listing = self.find_listing(listing_id)
        self._record(user, "listing.created", listing)
        return listing

    def update_listing(self, user, listing_id, form,
                       confirm_duplicate=False):
        """Validate and save changes to a listing; return the Listing.

        The listing's type cannot be changed.
        """
        listing = self.get_listing_for_change(user, listing_id)
        self._check_details(listing.listing_type, form, confirm_duplicate,
                            exclude_id=listing.listing_id)
        values = self._clean(listing.listing_type, form)
        self._store.execute(
            "UPDATE listings SET name = ?, location = ?, description = ?, "
            "price = ?, contact_phone = ?, opening_time = ?, "
            "closing_time = ?, room_count = ? WHERE id = ?",
            (values["name"], values["location"], values["description"],
             values["price"], values["contact_phone"],
             values["opening_time"], values["closing_time"],
             values["room_count"], listing.listing_id))
        updated = self.find_listing(listing.listing_id)
        self._record(user, "listing.updated", updated)
        return updated

    def remove_listing(self, user, listing_id):
        """Deactivate a listing that is referred to, otherwise delete it.

        A deactivated listing is hidden from tourists but its record is
        kept, so existing bookings and itineraries stay intact.

        Returns:
            A RemovalResult saying which happened and what refers to it.
        """
        listing = self.get_listing_for_change(user, listing_id)
        references = self.find_references(listing.listing_id)
        if references.has_records:
            self._store.execute(
                "UPDATE listings SET is_active = 0 WHERE id = ?",
                (listing.listing_id,))
            outcome = "deactivated"
            self._record(user, "listing.deactivated", listing)
        else:
            self._store.execute(
                "DELETE FROM listings WHERE id = ?", (listing.listing_id,))
            outcome = "deleted"
            self._record(user, "listing.deleted", listing)
        return RemovalResult(outcome, listing.name, references)

    def reactivate_listing(self, user, listing_id):
        """Make a deactivated listing visible to tourists again."""
        listing = self.get_listing_for_change(user, listing_id)
        self._store.execute(
            "UPDATE listings SET is_active = 1 WHERE id = ?",
            (listing.listing_id,))
        self._record(user, "listing.reactivated", listing)
        return self.find_listing(listing.listing_id)

    # ------------------------------------------------------------------
    # Helpers

    @staticmethod
    def _require_may_change(user, listing):
        """Raise NotAllowed unless ``user`` may change ``listing``."""
        if not Authenticator.may_change_listing(user, listing.operator_id):
            raise NotAllowed("You may change only your own listings.")

    def _check_details(self, listing_type, form, confirm_duplicate,
                       exclude_id=None):
        """Validate details, then look for a duplicate unless confirmed."""
        errors = self._validator.validate(listing_type, form)
        if errors:
            raise InvalidListing(errors)
        if not confirm_duplicate:
            existing = self._validator.find_possible_duplicate(
                listing_type, form.get("name"), form.get("location"),
                exclude_id=exclude_id)
            if existing:
                raise PossibleDuplicate(Listing.from_row(existing))

    @staticmethod
    def _clean(listing_type, form):
        """Return the validated form as the values to store."""
        has_hours = listing_type in TYPES_WITH_HOURS
        return {
            "name": form["name"].strip(),
            "location": form["location"].strip(),
            "description": (form.get("description") or "").strip(),
            "price": float(form["price"]),
            "contact_phone": form["contact_phone"].strip(),
            "opening_time": (parse_time(form["opening_time"])
                             if has_hours else None),
            "closing_time": (parse_time(form["closing_time"])
                             if has_hours else None),
            "room_count": (int(form["room_count"])
                           if listing_type == "accommodation" else None),
        }

    def _record(self, user, action, listing):
        """Record who did what to which listing, and when."""
        item = f"{listing.name} (#{listing.listing_id})"
        if self._activity_log is not None:
            self._activity_log.record(user.user_id, action, item)
        else:
            self._store.execute(
                "INSERT INTO activity_log (user_id, action, item) "
                "VALUES (?, ?, ?)", (user.user_id, action, item))
