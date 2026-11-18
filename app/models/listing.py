"""Listing and its five subtypes (CRC cards 5.14 to 5.19).

Listing is the abstract superclass of everything a tourist can find on
the system. It holds what every listing has in common, and each subtype
answers for its own differences, so no other class has to ask which type
of listing it is dealing with.
"""

from abc import ABC


class Listing(ABC):
    """Anything a tourist can find: the abstract superclass (card 5.14)."""

    LISTING_TYPE = ""
    TYPE_LABEL = ""
    PRICE_LABEL = "Price (RM)"
    BOOKABLE = False
    REVIEWABLE = True
    HAS_OPENING_HOURS = False
    HAS_ROOMS = False

    def __init__(self, listing_id, name, location, description="",
                 price=0.0, contact_phone="", operator_id=None,
                 is_active=True, opening_time=None, closing_time=None,
                 room_count=None):
        """Create a listing from its stored details."""
        self.listing_id = listing_id
        self.name = name
        self.location = location
        self.description = description
        self.price = price
        self.contact_phone = contact_phone
        self.operator_id = operator_id
        self.is_active = is_active
        self.opening_time = opening_time
        self.closing_time = closing_time
        self.room_count = room_count

    @property
    def listing_type(self):
        """Return the type name stored in the listings table."""
        return self.LISTING_TYPE

    @property
    def type_label(self):
        """Return the type as shown in the user interface."""
        return self.TYPE_LABEL

    @property
    def status_label(self):
        """Return 'Active' or 'Deactivated' for the user interface."""
        return "Active" if self.is_active else "Deactivated"

    @property
    def is_bookable(self):
        """Say whether tourists can book this type of listing."""
        return self.BOOKABLE

    @property
    def is_reviewable(self):
        """Say whether tourists can review this type of listing."""
        return self.REVIEWABLE

    @property
    def is_visible_to_tourists(self):
        """Say whether tourists can see this listing (active only)."""
        return self.is_active

    @staticmethod
    def subtype_for(listing_type):
        """Return the Listing subclass for a stored type name."""
        subtypes = {cls.LISTING_TYPE: cls for cls in (
            Attraction, Accommodation, TransportOption, DiningOutlet,
            EventPromotion)}
        return subtypes[listing_type]

    def form_values(self):
        """Return the details as the text a listing form shows."""
        return {
            "name": self.name,
            "location": self.location,
            "description": self.description or "",
            "price": f"{self.price:.2f}",
            "contact_phone": self.contact_phone or "",
            "opening_time": self.opening_time or "",
            "closing_time": self.closing_time or "",
            "room_count": ("" if self.room_count is None
                           else str(self.room_count)),
        }

    @staticmethod
    def from_row(row):
        """Build the right Listing subtype from a listings table row."""
        listing_class = Listing.subtype_for(row["listing_type"])
        return listing_class(
            listing_id=row["id"],
            name=row["name"],
            location=row["location"],
            description=row["description"],
            price=row["price"],
            contact_phone=row["contact_phone"],
            operator_id=row["operator_id"],
            is_active=bool(row["is_active"]),
            opening_time=row["opening_time"],
            closing_time=row["closing_time"],
            room_count=row["room_count"],
        )


class _OpeningHoursMixin:
    """Shared answer to 'are you open at this time?' (cards 5.15, 5.18)."""

    HAS_OPENING_HOURS = True

    def is_open_at(self, time_text):
        """Say whether the listing is open at ``time_text`` (``HH:MM``).

        A listing with no recorded hours is treated as always open.
        """
        if not self.opening_time or not self.closing_time:
            return True
        return self.opening_time <= time_text < self.closing_time


class Attraction(_OpeningHoursMixin, Listing):
    """A place of interest; browsed and saved, never booked (card 5.15)."""

    LISTING_TYPE = "attraction"
    TYPE_LABEL = "Attraction"
    PRICE_LABEL = "Entry fee (RM)"


class Accommodation(Listing):
    """A hotel, resort or homestay that can be booked (card 5.16)."""

    LISTING_TYPE = "accommodation"
    TYPE_LABEL = "Accommodation"
    PRICE_LABEL = "Price per night (RM)"
    BOOKABLE = True
    HAS_ROOMS = True


class TransportOption(Listing):
    """A bus, ferry or flight service that can be booked (card 5.17)."""

    LISTING_TYPE = "transport"
    TYPE_LABEL = "Transport"
    PRICE_LABEL = "Fare (RM)"
    BOOKABLE = True


class DiningOutlet(_OpeningHoursMixin, Listing):
    """A restaurant or cafe; searched and saved, never booked (5.18)."""

    LISTING_TYPE = "dining"
    TYPE_LABEL = "Dining"
    PRICE_LABEL = "Average price per person (RM)"


class EventPromotion(Listing):
    """An event or promotion; it cannot be reviewed (card 5.19)."""

    LISTING_TYPE = "event"
    TYPE_LABEL = "Event or promotion"
    REVIEWABLE = False
