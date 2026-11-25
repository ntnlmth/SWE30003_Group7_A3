"""Time-slot clash and listing-hours checks for itineraries."""

from datetime import datetime


class ScheduleClash:
    """One reason a proposed itinerary item cannot be saved."""

    def __init__(self, kind, message, items=None):
        """Create a clash description."""
        self.kind = kind
        self.message = message
        self.items = list(items or [])


class Scheduler:
    """Check itinerary items for overlap and opening-hours conflicts."""

    @staticmethod
    def _minutes(time_text):
        """Parse an HH:MM time into minutes after midnight."""
        return datetime.strptime(time_text, "%H:%M").hour * 60 + \
            datetime.strptime(time_text, "%H:%M").minute

    def check(self, proposed, existing_items, listing):
        """Return a list of clashes for a proposed item."""
        clashes = []
        if not listing.is_visible_to_tourists:
            clashes.append(ScheduleClash(
                "inactive", "This listing is no longer visible to tourists.",
                [proposed]))

        proposed_start = self._minutes(proposed["start_time"])
        proposed_end = self._minutes(proposed["end_time"])
        for item in existing_items:
            if item.day != proposed["day"]:
                continue
            existing_start = self._minutes(item.start_time)
            existing_end = self._minutes(item.end_time)
            if (proposed_start < existing_end
                    and existing_start < proposed_end):
                clashes.append(ScheduleClash(
                    "overlap",
                    "This time overlaps another planned activity.",
                    [item]))

        if listing.HAS_OPENING_HOURS:
            if not listing.opening_time or not listing.closing_time:
                clashes.append(ScheduleClash(
                    "hours", "This listing has no opening hours recorded.",
                    [proposed]))
            else:
                opening = self._minutes(listing.opening_time)
                closing = self._minutes(listing.closing_time)
                if proposed_start < opening or proposed_end > closing:
                    clashes.append(ScheduleClash(
                        "hours",
                        f"This listing is open from "
                        f"{listing.opening_time} to {listing.closing_time}.",
                        [proposed]))
        return clashes
