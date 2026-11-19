"""ListingCatalogue: lets a tourist browse and search accommodation.

Detailed-design changes from Assignment 2 (for the report):

* Assignment 2 gave ListingCatalogue browsing/search responsibility over
  every listing type. Area 1 of Assignment 3 implements only the
  accommodation slice of that (Section 1.2: implemented areas), so this
  class is scoped to accommodation search; browsing the other four
  listing types is left for whichever area implements them.
* It is read-only and never changes a listing, unlike ListingManager
  (Manage listings area), which is the only class that writes to the
  ``listings`` table. The two controllers share the same
  ListingRepository instead of duplicating its SQL, which is why a
  search here only ever returns active listings: ListingCatalogue has no
  way, and no need, to see a deactivated one.
* It also answers "how many rooms are free for these dates", which
  Assignment 2 did not call out as a separate question. This needs
  BookingRepository as well as ListingRepository, so ListingCatalogue
  collaborates with both (Section 2.3: responsibility and collaborator
  changes).
"""

from dataclasses import dataclass

from app.data.booking_repository import BookingRepository
from app.data.listing_repository import ListingRepository
from app.models.listing import Accommodation, Listing

ACCOMMODATION_TYPES = (Accommodation.LISTING_TYPE,)


@dataclass
class AccommodationResult:
    """One accommodation in a search result, with its free-room count."""

    listing: Accommodation
    available_rooms: int = None

    @property
    def has_availability(self):
        """Say whether this result still has a free room, if known."""
        return self.available_rooms is None or self.available_rooms > 0


class ListingCatalogue:
    """Search active accommodation listings for tourists."""

    def __init__(self, store, listing_repository=None,
                 booking_repository=None):
        """Create a catalogue that reads through ``store``."""
        self._listings = listing_repository or ListingRepository(store)
        self._bookings = booking_repository or BookingRepository(store)

    def search_accommodation(self, location="", check_in=None,
                             check_out=None):
        """Return active accommodation listings matching the filters.

        Args:
            location: Part of the name or location to search for.
            check_in: Optional ISO check-in date; when given with
                ``check_out``, each result's ``available_rooms`` is the
                number of rooms still free for that date range.

        Returns:
            A list of :class:`AccommodationResult`, ordered by name.
        """
        rows = self._listings.search(
            ACCOMMODATION_TYPES, status="active", text=location)
        results = []
        for row in rows:
            listing = Listing.from_row(row)
            available = None
            if check_in and check_out:
                booked = self._bookings.count_overlapping(
                    listing.listing_id, check_in, check_out)
                available = max(listing.room_count - booked, 0)
            results.append(AccommodationResult(listing, available))
        return results

    def find_bookable(self, listing_id):
        """Return the Accommodation with this id, or None.

        Returns None for an id that does not exist, is not an
        accommodation, or is not active, so the caller does not need to
        know which of the three happened: there is nothing a tourist can
        book either way.
        """
        row = self._listings.find_by_id(listing_id)
        if row is None or row["listing_type"] not in ACCOMMODATION_TYPES:
            return None
        listing = Listing.from_row(row)
        return listing if listing.is_visible_to_tourists else None
