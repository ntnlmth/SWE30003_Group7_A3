"""BookingRepository: every SQL statement for the Search and book area.

Mirrors ListingRepository (Manage listings area): BookingManager decides
the rules, this class only knows how to ask the database. It reaches the
database through DataStore, as every other repository does.

Rows are returned exactly as DataStore returns them (dict-like); turning
a row into a Booking object is the caller's job.
"""


class BookingRepository:
    """Find, save and count rows of the ``bookings`` table."""

    def __init__(self, store):
        """Create a repository that talks to the database via ``store``."""
        self._store = store

    def find_by_id(self, booking_id):
        """Return the booking row with this id, or None."""
        return self._store.find_one(
            "SELECT * FROM bookings WHERE id = ?", (booking_id,))

    def find_for_tourist(self, tourist_id):
        """Return this tourist's bookings, most recent first.

        Each row is joined with its listing's name and location so the
        "My bookings" screen needs no second lookup.
        """
        return self._store.find_all(
            "SELECT b.*, l.name AS listing_name, "
            "l.location AS listing_location "
            "FROM bookings b JOIN listings l ON l.id = b.listing_id "
            "WHERE b.tourist_id = ? ORDER BY b.created_at DESC",
            (tourist_id,))

    def count_overlapping(self, listing_id, check_in, check_out,
                          exclude_booking_id=None):
        """Count live bookings of ``listing_id`` that overlap this range.

        Two date ranges overlap when one starts before the other ends,
        in both directions. Cancelled bookings never count, since they
        no longer hold a room.
        """
        sql = (
            "SELECT COUNT(*) AS n FROM bookings "
            "WHERE listing_id = ? AND status != 'cancelled' "
            "AND check_in < ? AND check_out > ?"
        )
        params = [listing_id, check_out, check_in]
        if exclude_booking_id is not None:
            sql += " AND id != ?"
            params.append(exclude_booking_id)
        return self._store.find_one(sql, tuple(params))["n"]

    def insert(self, tourist_id, listing_id, check_in, check_out, guests,
               total_price, status="pending"):
        """Add a booking row and return its new id."""
        return self._store.execute(
            "INSERT INTO bookings (tourist_id, listing_id, check_in, "
            "check_out, guests, total_price, status) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (tourist_id, listing_id, check_in, check_out, guests,
             total_price, status))

    def set_status(self, booking_id, status):
        """Change a booking's status (pending, confirmed or cancelled)."""
        self._store.execute(
            "UPDATE bookings SET status = ? WHERE id = ?",
            (status, booking_id))

    # ------------------------------------------------------------------
    # Audit trail

    def add_audit_entry(self, user_id, action, item):
        """Write one line to the ``activity_log`` table.

        Mirrors ListingRepository.add_audit_entry (Manage listings area):
        duplicated rather than shared, so this area's repository does not
        depend on another area's.
        """
        self._store.execute(
            "INSERT INTO activity_log (user_id, action, item) "
            "VALUES (?, ?, ?)", (user_id, action, item))
