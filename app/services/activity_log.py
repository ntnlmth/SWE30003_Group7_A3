"""ActivityLog: the audit trail of who did what, and when.

Implements the ActivityLog CRC card; each saved row is one
ActivityLogEntry (a data-holder in Assignment 2). Its ``record`` method
matches the ``activity_log`` argument BookingManager already accepts,
so the booking area can switch to it without other changes.
"""


class ActivityLog:
    """Record and look up audit entries."""

    def __init__(self, store):
        """Create an ActivityLog that saves through ``store``."""
        self._store = store

    def record(self, user_id, action, item):
        """Save one entry: ``user_id`` did ``action`` to ``item``."""
        return self._store.execute(
            "INSERT INTO activity_log (user_id, action, item) "
            "VALUES (?, ?, ?)", (user_id, action, item))

    def entries_for(self, user_id):
        """Return this user's entries, newest first."""
        return self._store.find_all(
            "SELECT * FROM activity_log WHERE user_id = ? "
            "ORDER BY created_at DESC, id DESC", (user_id,))
