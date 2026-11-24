"""PaymentRepository: every SQL statement for the Pay for a booking area.

Mirrors BookingRepository and ListingRepository: PaymentManager decides
the rules, this class only knows how to ask the database, through
DataStore.
"""


class PaymentRepository:
    """Find and save rows of the ``payments`` table."""

    def __init__(self, store):
        """Create a repository that talks to the database via ``store``."""
        self._store = store

    def find_booking(self, booking_id):
        """Return the booking row with its listing's name, or None."""
        return self._store.find_one(
            "SELECT b.*, l.name AS listing_name, "
            "l.location AS listing_location "
            "FROM bookings b JOIN listings l ON l.id = b.listing_id "
            "WHERE b.id = ?", (booking_id,))

    def find_unpaid_for_tourist(self, tourist_id):
        """Return this tourist's pending bookings, soonest check-in first."""
        return self._store.find_all(
            "SELECT b.*, l.name AS listing_name, "
            "l.location AS listing_location "
            "FROM bookings b JOIN listings l ON l.id = b.listing_id "
            "WHERE b.tourist_id = ? AND b.status = 'pending' "
            "ORDER BY b.check_in", (tourist_id,))

    def find_by_id(self, payment_id):
        """Return the payment row with its booking and listing details."""
        return self._store.find_one(
            "SELECT p.*, b.tourist_id, b.check_in, b.check_out, "
            "b.guests, l.name AS listing_name "
            "FROM payments p JOIN bookings b ON b.id = p.booking_id "
            "JOIN listings l ON l.id = b.listing_id "
            "WHERE p.id = ?", (payment_id,))

    def find_for_tourist(self, tourist_id):
        """Return every payment attempt by this tourist, newest first."""
        return self._store.find_all(
            "SELECT p.*, l.name AS listing_name "
            "FROM payments p JOIN bookings b ON b.id = p.booking_id "
            "JOIN listings l ON l.id = b.listing_id "
            "WHERE b.tourist_id = ? "
            "ORDER BY p.created_at DESC, p.id DESC", (tourist_id,))

    def record_failure(self, booking_id, amount, reference):
        """Save a declined payment attempt; return its id."""
        return self._store.execute(
            "INSERT INTO payments (booking_id, amount, status, reference) "
            "VALUES (?, ?, 'failed', ?)", (booking_id, amount, reference))

    def record_success(self, booking_id, amount, reference):
        """Save a successful payment and confirm the booking, together.

        Both changes are made in one transaction, so a payment is never
        saved without its booking being confirmed, or the reverse.

        Returns:
            The new payment's id, or None if the booking was no longer
            pending (nothing is saved in that case).
        """
        with self._store.transaction() as connection:
            updated = connection.execute(
                "UPDATE bookings SET status = 'confirmed' "
                "WHERE id = ? AND status = 'pending'", (booking_id,))
            if updated.rowcount != 1:
                return None
            return connection.execute(
                "INSERT INTO payments (booking_id, amount, status, "
                "reference) VALUES (?, ?, 'success', ?)",
                (booking_id, amount, reference)).lastrowid
