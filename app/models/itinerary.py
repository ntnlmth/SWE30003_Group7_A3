"""Itinerary domain model and its owned item data holder."""

from datetime import date, datetime


class ItineraryItem:
    """A listing planned at one time slot inside an itinerary."""

    def __init__(self, item_id, itinerary_id, listing_id, day,
                 start_time, end_time, listing=None):
        """Create an itinerary item from stored or loaded details."""
        self.item_id = item_id
        self.itinerary_id = itinerary_id
        self.listing_id = listing_id
        self.day = day
        self.start_time = start_time
        self.end_time = end_time
        self.listing = listing

    @property
    def is_upcoming(self):
        """Say whether this item is scheduled today or later."""
        return date.fromisoformat(self.day) >= date.today()

    @property
    def duration_minutes(self):
        """Return the length of this item in minutes."""
        start = datetime.strptime(self.start_time, "%H:%M")
        end = datetime.strptime(self.end_time, "%H:%M")
        return int((end - start).total_seconds() // 60)

    @staticmethod
    def from_row(row, listing=None):
        """Build an item from a repository row."""
        return ItineraryItem(
            item_id=row["id"],
            itinerary_id=row["itinerary_id"],
            listing_id=row["listing_id"],
            day=row["day"],
            start_time=row["start_time"],
            end_time=row["end_time"],
            listing=listing,
        )


class Itinerary:
    """A tourist's trip plan containing dated time slots."""

    def __init__(self, itinerary_id, tourist_id, title, start_date,
                 end_date, items=None):
        """Create an itinerary from stored details."""
        self.itinerary_id = itinerary_id
        self.tourist_id = tourist_id
        self.title = title
        self.start_date = start_date
        self.end_date = end_date
        self.items = list(items or [])

    @property
    def day_count(self):
        """Return the number of inclusive calendar days in the trip."""
        start = date.fromisoformat(self.start_date)
        end = date.fromisoformat(self.end_date)
        return (end - start).days + 1

    def add_item(self, item):
        """Append an item to this itinerary."""
        self.items.append(item)

    def remove_item(self, item_id):
        """Remove an item from this in-memory plan."""
        self.items = [item for item in self.items if item.item_id != item_id]

    @staticmethod
    def from_row(row, items=None):
        """Build an itinerary from a repository row."""
        return Itinerary(
            itinerary_id=row["id"],
            tourist_id=row["tourist_id"],
            title=row["title"],
            start_date=row["start_date"],
            end_date=row["end_date"],
            items=items,
        )
