"""BookingManager: coordinates booking an accommodation (Area 1).

It checks who may do what, has the dates and guest count validated,
checks there is a free room, saves the outcome and records who booked
or cancelled what. It holds no booking data of its own: the details
live in Booking and in the database, reached through BookingRepository.
This mirrors ListingManager (Manage listings area) by design, so the
two controllers read the same way even though they were built by
different members.

Detailed-design changes from Assignment 2 (for the report):

* Problems are reported by raising small exceptions (``InvalidBooking``,
  ``NotAvailable``, ...) instead of returning codes, for the same reason
  ListingManager does: so route handlers contain no business rules.
* Assignment 2 did not say how many rooms a booking occupies. The
  detailed design treats each booking as occupying exactly one of the
  accommodation's ``room_count`` rooms for its date range; two bookings
  "clash" when their date ranges overlap. This is a simplification
  (no specific room is assigned, and group bookings do not combine
  into one room), documented here rather than left implicit.
* A tourist cancels their own pending or confirmed booking at any point
  before check-in; Assignment 2 did not define a cancellation rule for
  this area, so this is new. Cancelling never deletes the row (an
  audit trail would otherwise lose it), only moves it to the
  ``cancelled`` status already defined in the database schema.
* No separate validator class was added for this area: the dates and
  guest count are simple enough to check with the same
  ``app.services.form_validation`` helpers Authenticator already uses
  for registration, so a second validator class would only duplicate
  DataValidator's role without adding a distinct responsibility.
"""

from dataclasses import dataclass
from datetime import date, datetime

from app.data.booking_repository import BookingRepository
from app.models.booking import Booking
from app.services.form_validation import first_error, require

DATE_FORMAT = "%Y-%m-%d"


class BookingError(Exception):
    """Base class for problems BookingManager reports."""


class NotAllowed(BookingError):
    """The user may not do this action."""


class ListingNotFound(BookingError):
    """No bookable accommodation has the requested id."""


class BookingNotFound(BookingError):
    """No booking has the requested id."""


class InvalidBooking(BookingError):
    """The submitted dates or guest count failed validation."""

    def __init__(self, errors):
        """Keep the dict of field errors for the form to show."""
        super().__init__("The booking details are not valid.")
        self.errors = errors


class NotAvailable(BookingError):
    """No room is free for the requested dates."""

    def __init__(self, available_rooms):
        """Keep the number of rooms that were actually free (0 or more)."""
        super().__init__("No room is available for those dates.")
        self.available_rooms = available_rooms


class CannotCancel(BookingError):
    """This booking is not in a state that can be cancelled."""


@dataclass
class BookingView:
    """A booking together with the display details a screen needs."""

    booking: Booking
    listing_name: str
    listing_location: str
    may_cancel: bool


def parse_date(value):
    """Return ``value`` as ``YYYY-MM-DD`` text, or None if not a date."""
    try:
        return datetime.strptime((value or "").strip(), DATE_FORMAT) \
            .strftime(DATE_FORMAT)
    except ValueError:
        return None


def _check_whole_number(value, label, minimum):
    """Return an error if ``value`` is not a whole number >= minimum."""
    try:
        number = int(str(value).strip())
    except (TypeError, ValueError):
        return f"{label} must be a whole number."
    if number < minimum:
        return f"{label} must be {minimum} or more."
    return None


class BookingManager:
    """Book and cancel accommodation for tourists."""

    def __init__(self, store, catalogue=None, activity_log=None,
                 today=date.today, repository=None):
        """Create a manager that saves through ``store``.

        Args:
            store: The DataStore.
            catalogue: A ListingCatalogue; one is created if not given.
            activity_log: Optional object with ``record(user_id, action,
                item)``. Without it, entries are written to the table.
            today: Function returning today's date, replaced in tests.
            repository: A BookingRepository; one is created if not given.
        """
        # Imported here, not at module level, to avoid a circular import
        # between the two controllers in this area.
        from app.controllers.listing_catalogue import ListingCatalogue

        self._repository = repository or BookingRepository(store)
        self._catalogue = catalogue or ListingCatalogue(store)
        self._activity_log = activity_log
        self._today = today

    # ------------------------------------------------------------------
    # Booking

    def book(self, user, listing_id, form):
        """Validate, check availability and save a new booking.

        Raises:
            NotAllowed: ``user`` is not a tourist.
            ListingNotFound: No bookable accommodation has this id.
            InvalidBooking: A field failed validation.
            NotAvailable: No room is free for the requested dates.

        Returns:
            The saved Booking.
        """
        if user is None or user.role != "tourist":
            raise NotAllowed("Only tourists can book accommodation.")
        accommodation = self._catalogue.find_bookable(listing_id)
        if accommodation is None:
            raise ListingNotFound("That accommodation is not available.")
        check_in, check_out, guests = self._check_details(form)
        available = self._available_rooms(
            accommodation, check_in, check_out)
        if available <= 0:
            raise NotAvailable(available)
        nights = (date.fromisoformat(check_out)
                  - date.fromisoformat(check_in)).days
        total_price = round(nights * accommodation.price, 2)
        booking_id = self._repository.insert(
            user.user_id, listing_id, check_in, check_out, guests,
            total_price)
        booking = Booking.from_row(self._repository.find_by_id(booking_id))
        self._record(user, "booking.created", booking, accommodation.name)
        return booking

    def list_bookings(self, user):
        """Return this tourist's bookings, most recent first."""
        rows = self._repository.find_for_tourist(user.user_id)
        today = self._today().isoformat()
        views = []
        for row in rows:
            booking = Booking.from_row(row)
            views.append(BookingView(
                booking=booking,
                listing_name=row["listing_name"],
                listing_location=row["listing_location"],
                may_cancel=self._may_cancel(booking, today)))
        return views

    def get_booking_for_cancel(self, user, booking_id):
        """Return the Booking if ``user`` owns it, for the confirm screen.

        Raises:
            BookingNotFound: No booking has this id.
            NotAllowed: The booking belongs to a different tourist.
        """
        row = self._repository.find_by_id(booking_id)
        if row is None:
            raise BookingNotFound("That booking no longer exists.")
        booking = Booking.from_row(row)
        if booking.tourist_id != user.user_id:
            raise NotAllowed("You may cancel only your own bookings.")
        return booking

    def cancel_booking(self, user, booking_id):
        """Cancel ``user``'s own pending or confirmed booking.

        Raises:
            BookingNotFound: No booking has this id.
            NotAllowed: The booking belongs to a different tourist.
            CannotCancel: The booking is already cancelled, or its
                check-in date has passed.

        Returns:
            The updated Booking.
        """
        booking = self.get_booking_for_cancel(user, booking_id)
        if not self._may_cancel(booking, self._today().isoformat()):
            raise CannotCancel("This booking can no longer be cancelled.")
        self._repository.set_status(booking.booking_id, "cancelled")
        updated = Booking.from_row(
            self._repository.find_by_id(booking.booking_id))
        accommodation = self._catalogue.find_bookable(booking.listing_id)
        item_name = (accommodation.name if accommodation is not None
                     else f"listing #{booking.listing_id}")
        self._record(user, "booking.cancelled", updated, item_name)
        return updated

    # ------------------------------------------------------------------
    # Helpers

    @staticmethod
    def _may_cancel(booking, today_iso):
        """Say whether ``booking`` can still be cancelled today."""
        return booking.status in ("pending", "confirmed") \
            and booking.check_in >= today_iso

    def _available_rooms(self, accommodation, check_in, check_out):
        """Return how many of the accommodation's rooms are still free."""
        booked = self._repository.count_overlapping(
            accommodation.listing_id, check_in, check_out)
        return accommodation.room_count - booked

    def _check_details(self, form):
        """Validate the booking form; return (check_in, check_out, guests).

        Raises:
            InvalidBooking: One or more fields failed validation.
        """
        errors = {}
        check_in = parse_date(form.get("check_in"))
        check_out = parse_date(form.get("check_out"))
        today = self._today().isoformat()
        if check_in is None:
            errors["check_in"] = (
                "Enter the check-in date as YYYY-MM-DD, such as "
                "2026-12-24.")
        elif check_in < today:
            errors["check_in"] = "Check-in cannot be in the past."
        if check_out is None:
            errors["check_out"] = (
                "Enter the check-out date as YYYY-MM-DD, such as "
                "2026-12-26.")
        elif check_in and check_out <= check_in:
            errors["check_out"] = "Check-out must be after check-in."
        guests_error = first_error(
            require(form.get("guests"), "Number of guests"),
            _check_whole_number(form.get("guests"), "Number of guests", 1))
        if guests_error:
            errors["guests"] = guests_error
        if errors:
            raise InvalidBooking(errors)
        return check_in, check_out, int(form["guests"])

    def _record(self, user, action, booking, item_name):
        """Record who booked or cancelled what, and when."""
        item = f"{item_name} (booking #{booking.booking_id})"
        if self._activity_log is not None:
            self._activity_log.record(user.user_id, action, item)
        else:
            self._repository.add_audit_entry(user.user_id, action, item)
