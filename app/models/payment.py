"""Payment: one attempt to pay for a booking.

Detailed-design note (Assignment 3, Area 2 - Zaferah): Payment holds
only what was stored about one payment attempt. It does not talk to the
payment gateway or change the booking: PaymentManager does that, for
the same reason Booking does not decide its own rules (heuristic H3).
Card details are never kept on a Payment, only the gateway's
reference, so no card data reaches the database.
"""


class Payment:
    """One attempt, successful or not, to pay for a booking."""

    STATUSES = ("success", "failed", "pending")

    def __init__(self, payment_id, booking_id, amount, status,
                 reference=None, created_at=None):
        """Create a Payment from its stored details."""
        self.payment_id = payment_id
        self.booking_id = booking_id
        self.amount = amount
        self.status = status
        self.reference = reference
        self.created_at = created_at

    @property
    def succeeded(self):
        """Say whether the gateway accepted this payment."""
        return self.status == "success"

    @property
    def status_label(self):
        """Return the status as shown in the user interface."""
        return {
            "success": "Paid",
            "failed": "Declined",
            "pending": "Processing",
        }.get(self.status, self.status.capitalize())

    @staticmethod
    def from_row(row):
        """Build a Payment from a ``payments`` table row."""
        return Payment(
            payment_id=row["id"],
            booking_id=row["booking_id"],
            amount=row["amount"],
            status=row["status"],
            reference=row["reference"],
            created_at=row["created_at"],
        )
