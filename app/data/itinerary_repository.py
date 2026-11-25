"""SQL access for itinerary and itinerary-item records."""


class ItineraryRepository:
    """Find and save itineraries through DataStore."""

    def __init__(self, store):
        """Create a repository that talks to ``store``."""
        self._store = store

    def find_itinerary(self, itinerary_id):
        """Return one itinerary row, or None."""
        return self._store.find_one(
            "SELECT * FROM itineraries WHERE id = ?", (itinerary_id,))

    def list_for_tourist(self, tourist_id):
        """Return itinerary rows owned by a tourist, newest first."""
        return self._store.find_all(
            "SELECT * FROM itineraries WHERE tourist_id = ? "
            "ORDER BY start_date DESC, id DESC",
            (tourist_id,))

    def create(self, tourist_id, title, start_date, end_date):
        """Insert an itinerary and return its id."""
        return self._store.execute(
            "INSERT INTO itineraries "
            "(tourist_id, title, start_date, end_date) "
            "VALUES (?, ?, ?, ?)",
            (tourist_id, title, start_date, end_date))

    def update(self, itinerary_id, title, start_date, end_date):
        """Replace an itinerary's editable details."""
        self._store.execute(
            "UPDATE itineraries SET title = ?, start_date = ?, end_date = ? "
            "WHERE id = ?", (title, start_date, end_date, itinerary_id))

    def delete(self, itinerary_id):
        """Delete an itinerary and cascade its items."""
        self._store.execute(
            "DELETE FROM itineraries WHERE id = ?", (itinerary_id,))

    def list_items(self, itinerary_id):
        """Return item rows joined to listing details."""
        return self._store.find_all(
            "SELECT ii.*, l.name AS listing_name, l.listing_type, "
            "l.location, l.is_active, l.opening_time, l.closing_time "
            "FROM itinerary_items ii "
            "JOIN listings l ON l.id = ii.listing_id "
            "WHERE ii.itinerary_id = ? "
            "ORDER BY ii.day, ii.start_time, ii.id",
            (itinerary_id,))

    def find_item(self, item_id, itinerary_id=None):
        """Return one item row, optionally restricted to an itinerary."""
        if itinerary_id is None:
            return self._store.find_one(
                "SELECT * FROM itinerary_items WHERE id = ?", (item_id,))
        return self._store.find_one(
            "SELECT * FROM itinerary_items "
            "WHERE id = ? AND itinerary_id = ?",
            (item_id, itinerary_id))

    def insert_item(self, itinerary_id, listing_id, day,
                    start_time, end_time):
        """Insert an itinerary item and return its id."""
        return self._store.execute(
            "INSERT INTO itinerary_items "
            "(itinerary_id, listing_id, day, start_time, end_time) "
            "VALUES (?, ?, ?, ?, ?)",
            (itinerary_id, listing_id, day, start_time, end_time))

    def update_item(self, item_id, listing_id, day, start_time, end_time):
        """Replace an itinerary item's details."""
        self._store.execute(
            "UPDATE itinerary_items SET listing_id = ?, day = ?, "
            "start_time = ?, end_time = ? WHERE id = ?",
            (listing_id, day, start_time, end_time, item_id))

    def delete_item(self, item_id):
        """Delete one itinerary item."""
        self._store.execute(
            "DELETE FROM itinerary_items WHERE id = ?", (item_id,))

    def find_active_listings(self, text=""):
        """Return active listing rows for the item picker."""
        sql = "SELECT * FROM listings WHERE is_active = 1"
        params = []
        if text.strip():
            sql += " AND (name LIKE ? OR location LIKE ?)"
            params.extend([f"%{text.strip()}%", f"%{text.strip()}%"])
        sql += " ORDER BY lower(name)"
        return self._store.find_all(sql, tuple(params))
