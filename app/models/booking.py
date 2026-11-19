"""Booking: a tourist's reservation of an accommodation listing.

Detailed-design note (Assignment 3, Area 1 - Badrul): Booking holds only
its own stored details and the one calculation (``nights``) that follows
directly from them. Deciding whether a booking is allowed, available or
cancellable is BookingManager's job, not this class's, for the same
reason Listing does not run its own lifecycle (Assignment 2, Section
6.2, heuristic H3): Booking would otherwise also have to check
permissions, check room availability and know today's date, none of
which is "a booking's own business".
"""

from datetime import date


class Booking:
    """A tourist's reservation of an accommodation for a date range."""

    STATUSES = ("pending", "confirmed", "cancelled")

    def __init__(self, booking_id, tourist_id, listing_id, check_in,
                 check_out, guests, total_price, status, created_at=None):
        """Create a Booking from its stored details."""
        self.booking_id = booking_id
        self.tourist_id = tourist_id
        self.listing_id = listing_id
        self.check_in = check_in
        self.check_out = check_out
        self.guests = guests
        self.total_price = total_price
        self.status = status
        self.created_at = created_at

    @property
    def nights(self):
        """Return the number of nights this booking covers."""
        return (date.fromisoformat(self.check_out)
                - date.fromisoformat(self.check_in)).days

    @property
    def status_label(self):
        """Return the status as shown in the user interface."""
        return {
            "pending": "Pending payment",
            "confirmed": "Confirmed",
            "cancelled": "Cancelled",
        }.get(self.status, self.status.capitalize())

    @staticmethod
    def from_row(row):
        """Build a Booking from a ``bookings`` table row."""
        return Booking(
            booking_id=row["id"],
            tourist_id=row["tourist_id"],
            listing_id=row["listing_id"],
            check_in=row["check_in"],
            check_out=row["check_out"],
            guests=row["guests"],
            total_price=row["total_price"],
            status=row["status"],
            created_at=row["created_at"],
        )
