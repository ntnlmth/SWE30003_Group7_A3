"""ListingRepository: every SQL statement for the Manage listings area.

ListingManager and DataValidator decide what should happen; this class
only knows how to ask the database. Keeping the SQL here means the rules
can be read, and tested, without any SQL in the way. It reaches the
database through the DataStore, as every other class does.

Rows are returned exactly as DataStore returns them (dict-like); turning
a row into a Listing object is the caller's job.
"""

_DETAIL_COLUMNS = ("name", "location", "description", "price",
                   "contact_phone", "opening_time", "closing_time",
                   "room_count")


class ListingRepository:
    """Find, save and remove rows of the ``listings`` table."""

    def __init__(self, store):
        """Create a repository that talks to the database via ``store``."""
        self._store = store

    # ------------------------------------------------------------------
    # Finding listings

    def find_by_id(self, listing_id):
        """Return the listing row with this id, or None."""
        return self._store.find_one(
            "SELECT * FROM listings WHERE id = ?", (listing_id,))

    def search(self, listing_types, operator_id=None, listing_type="",
               status="", text=""):
        """Return listing rows that match every filter that is given.

        Args:
            listing_types: The types the caller may see at all.
            operator_id: Only this operator's listings, when given.
            listing_type: Only this type, when it is one of
                ``listing_types``.
            status: ``"active"`` or ``"deactivated"``; anything else
                means both.
            text: Part of the name or location.
        """
        sql = "SELECT * FROM listings WHERE listing_type IN ({})".format(
            ", ".join("?" for _ in listing_types))
        params = list(listing_types)
        if operator_id is not None:
            sql += " AND operator_id = ?"
            params.append(operator_id)
        if listing_type in listing_types:
            sql += " AND listing_type = ?"
            params.append(listing_type)
        if status in ("active", "deactivated"):
            sql += " AND is_active = ?"
            params.append(1 if status == "active" else 0)
        if text.strip():
            sql += " AND (name LIKE ? OR location LIKE ?)"
            like = f"%{text.strip()}%"
            params.extend([like, like])
        sql += " ORDER BY lower(name)"
        return self._store.find_all(sql, tuple(params))

    def find_duplicate(self, listing_type, name, location, exclude_id=None):
        """Return a row of the same type, name and location, or None.

        Case and surrounding spaces are ignored. ``exclude_id`` leaves
        out the listing being edited.
        """
        return self._store.find_one(
            "SELECT * FROM listings WHERE listing_type = ? "
            "AND lower(trim(name)) = lower(trim(?)) "
            "AND lower(trim(location)) = lower(trim(?)) "
            "AND id != ?",
            (listing_type, name or "", location or "", exclude_id or 0))

    # ------------------------------------------------------------------
    # Saving and removing listings

    def insert(self, listing_type, operator_id, values):
        """Add a listing row and return its new id.

        ``values`` holds one entry for each detail column.
        """
        return self._store.execute(
            "INSERT INTO listings (listing_type, operator_id, name, "
            "location, description, price, contact_phone, opening_time, "
            "closing_time, room_count) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (listing_type, operator_id,
             *(values[column] for column in _DETAIL_COLUMNS)))

    def update_details(self, listing_id, values):
        """Replace the editable details of a listing."""
        self._store.execute(
            "UPDATE listings SET name = ?, location = ?, description = ?, "
            "price = ?, contact_phone = ?, opening_time = ?, "
            "closing_time = ?, room_count = ? WHERE id = ?",
            (*(values[column] for column in _DETAIL_COLUMNS), listing_id))

    def set_active(self, listing_id, is_active):
        """Show (True) or hide (False) a listing for tourists."""
        self._store.execute(
            "UPDATE listings SET is_active = ? WHERE id = ?",
            (1 if is_active else 0, listing_id))

    def delete(self, listing_id):
        """Remove a listing row for good."""
        self._store.execute(
            "DELETE FROM listings WHERE id = ?", (listing_id,))

    # ------------------------------------------------------------------
    # What refers to a listing

    def find_upcoming_bookings(self, listing_id, today):
        """Return live bookings that end on or after ``today`` (ISO date)."""
        return self._store.find_all(
            "SELECT b.id, b.check_in, b.check_out, b.status, "
            "u.name AS tourist_name FROM bookings b "
            "JOIN users u ON u.id = b.tourist_id "
            "WHERE b.listing_id = ? AND b.status != 'cancelled' "
            "AND b.check_out >= ? ORDER BY b.check_in",
            (listing_id, today))

    def find_upcoming_items(self, listing_id, today):
        """Return itinerary items planned on or after ``today``."""
        return self._store.find_all(
            "SELECT ii.id, ii.day, ii.start_time, ii.end_time, "
            "i.title AS itinerary_title, u.name AS tourist_name "
            "FROM itinerary_items ii "
            "JOIN itineraries i ON i.id = ii.itinerary_id "
            "JOIN users u ON u.id = i.tourist_id "
            "WHERE ii.listing_id = ? AND ii.day >= ? ORDER BY ii.day",
            (listing_id, today))

    def has_any_booking(self, listing_id):
        """Say whether any booking, past or future, uses this listing."""
        return self._store.find_one(
            "SELECT id FROM bookings WHERE listing_id = ? LIMIT 1",
            (listing_id,)) is not None

    def has_any_itinerary_item(self, listing_id):
        """Say whether any itinerary item, past or future, uses it."""
        return self._store.find_one(
            "SELECT id FROM itinerary_items WHERE listing_id = ? LIMIT 1",
            (listing_id,)) is not None
