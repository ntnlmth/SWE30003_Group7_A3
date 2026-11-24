"""Notifier: tells users about things that happened to their records.

Implements the Notifier CRC card. In this release a notification is a
message saved in the ``notifications`` table and shown on screen; no
email or SMS is sent. Other areas can reuse it through the same
``notify`` call.
"""


class Notifier:
    """Send and list notifications for users."""

    def __init__(self, store):
        """Create a Notifier that saves through ``store``."""
        self._store = store

    def notify(self, user_id, message):
        """Save a notification for ``user_id``; return its id."""
        return self._store.execute(
            "INSERT INTO notifications (user_id, message) VALUES (?, ?)",
            (user_id, message))

    def recent_for(self, user_id, limit=5):
        """Return the user's newest notifications, newest first."""
        return self._store.find_all(
            "SELECT * FROM notifications WHERE user_id = ? "
            "ORDER BY created_at DESC, id DESC LIMIT ?",
            (user_id, limit))
