"""PaymentManager: coordinates paying for a booking (Area 2).

It checks the tourist may pay for this booking, has the card details
validated, charges the card through PaymentGatewayAdapter, saves the
outcome as a Payment, confirms the booking, notifies the tourist
through Notifier and records the action in ActivityLog. Like
BookingManager and ListingManager, it holds no data of its own.

Detailed-design changes from Assignment 2 (for the report):

* PaymentManager is new. In Assignment 2 paying was one of
  BookingManager's responsibilities. It was split out so that
  BookingManager does not grow into a god class (Section 6.4), so the
  two areas could be built in parallel by different members, and so
  each controller has one reason to change: booking rules or payment
  rules.
* The amount charged is always the booking's stored ``total_price``,
  never a value sent by the browser, so it cannot be tampered with.
* A booking can be paid only while it is ``pending`` and its check-in
  date has not passed. A successful payment moves it to ``confirmed``.
  A declined payment is still saved (status ``failed``) for the audit
  trail, and the booking stays ``pending`` so the tourist can retry.
* Card details are validated and passed to the gateway, but never
  saved. Only the gateway's reference is stored.
* Problems are reported by raising small exceptions, as in the other
  areas, so route handlers contain no business rules.
"""

from dataclasses import dataclass
from datetime import date

from app.data.payment_repository import PaymentRepository
from app.models.booking import Booking
from app.models.payment import Payment
from app.services.activity_log import ActivityLog
from app.services.form_validation import check_length, first_error, require
from app.services.notifier import Notifier
from app.services.payment_gateway import CardDetails, PaymentGatewayAdapter


class PaymentError(Exception):
    """Base class for problems PaymentManager reports."""


class NotAllowed(PaymentError):
    """The user may not do this action."""


class BookingNotFound(PaymentError):
    """No booking has the requested id."""


class PaymentNotFound(PaymentError):
    """No payment has the requested id, or it is not the user's."""


class CannotPay(PaymentError):
    """The booking is not in a state that can be paid."""


class InvalidCard(PaymentError):
    """The submitted card details failed validation."""

    def __init__(self, errors):
        """Keep the dict of field errors for the form to show."""
        super().__init__("The card details are not valid.")
        self.errors = errors


class PaymentDeclined(PaymentError):
    """The gateway refused the charge; the attempt has been saved."""

    def __init__(self, message, payment):
        """Keep the gateway's message and the saved failed Payment."""
        super().__init__(message)
        self.payment = payment


@dataclass
class PayableBooking:
    """A booking together with the display details a screen needs."""

    booking: Booking
    listing_name: str
    listing_location: str


@dataclass
class PaymentView:
    """A payment together with the name of what was paid for."""

    payment: Payment
    listing_name: str


def luhn_valid(number):
    """Say whether ``number`` passes the Luhn check card numbers use."""
    total = 0
    for position, char in enumerate(reversed(number)):
        digit = int(char)
        if position % 2 == 1:
            digit *= 2
            if digit > 9:
                digit -= 9
        total += digit
    return total % 10 == 0


def clean_card_number(value):
    """Return the card number without spaces or dashes."""
    return (value or "").replace(" ", "").replace("-", "")


class PaymentManager:
    """Take payment for tourists' pending bookings."""

    def __init__(self, store, gateway=None, notifier=None,
                 activity_log=None, today=date.today, repository=None):
        """Create a manager that saves through ``store``.

        Args:
            store: The DataStore.
            gateway: A PaymentGatewayAdapter; one wrapping the simulated
                gateway is created if not given.
            notifier: A Notifier; one is created if not given.
            activity_log: An ActivityLog; one is created if not given.
            today: Function returning today's date, replaced in tests.
            repository: A PaymentRepository; one is created if not given.
        """
        self._repository = repository or PaymentRepository(store)
        self._gateway = gateway or PaymentGatewayAdapter()
        self._notifier = notifier or Notifier(store)
        self._activity_log = activity_log or ActivityLog(store)
        self._today = today

    # ------------------------------------------------------------------
    # Looking things up

    def list_unpaid(self, user):
        """Return this tourist's bookings that are waiting for payment."""
        today = self._today().isoformat()
        return [
            self._payable(row) for row in
            self._repository.find_unpaid_for_tourist(user.user_id)
            if row["check_in"] >= today
        ]

    def list_payments(self, user):
        """Return this tourist's payment attempts, newest first."""
        return [
            PaymentView(Payment.from_row(row), row["listing_name"])
            for row in self._repository.find_for_tourist(user.user_id)
        ]

    def recent_notifications(self, user):
        """Return this user's newest notifications."""
        return self._notifier.recent_for(user.user_id)

    def get_payable_booking(self, user, booking_id):
        """Return the booking if ``user`` may pay for it now.

        Raises:
            NotAllowed: ``user`` is not a tourist, or the booking
                belongs to someone else.
            BookingNotFound: No booking has this id.
            CannotPay: The booking is not pending, or check-in passed.
        """
        if user is None or user.role != "tourist":
            raise NotAllowed("Only tourists can pay for bookings.")
        row = self._repository.find_booking(booking_id)
        if row is None:
            raise BookingNotFound("That booking no longer exists.")
        payable = self._payable(row)
        booking = payable.booking
        if booking.tourist_id != user.user_id:
            raise NotAllowed("You may pay only for your own bookings.")
        if booking.status == "confirmed":
            raise CannotPay("This booking has already been paid.")
        if booking.status != "pending":
            raise CannotPay("A cancelled booking cannot be paid.")
        if booking.check_in < self._today().isoformat():
            raise CannotPay(
                "The check-in date has passed, so this booking can no "
                "longer be paid.")
        return payable

    def get_receipt(self, user, payment_id):
        """Return the successful Payment's view if it is ``user``'s.

        Raises:
            PaymentNotFound: No successful payment by this user has
                this id.
        """
        row = self._repository.find_by_id(payment_id)
        if row is None or row["tourist_id"] != user.user_id \
                or row["status"] != "success":
            raise PaymentNotFound("That receipt could not be found.")
        return PaymentView(Payment.from_row(row), row["listing_name"])

    # ------------------------------------------------------------------
    # Paying

    def pay(self, user, booking_id, form):
        """Validate the card, charge it and record the outcome.

        Raises:
            NotAllowed, BookingNotFound, CannotPay: See
                :meth:`get_payable_booking`.
            InvalidCard: A card field failed validation.
            PaymentDeclined: The gateway refused the charge.

        Returns:
            The saved, successful Payment.
        """
        payable = self.get_payable_booking(user, booking_id)
        booking = payable.booking
        card = self._check_card(form)
        amount = booking.total_price
        result = self._gateway.charge(amount, card)
        item = (f"{payable.listing_name} (booking #{booking.booking_id})")

        if not result.approved:
            payment_id = self._repository.record_failure(
                booking.booking_id, amount, result.reference)
            payment = Payment.from_row(self._repository.find_by_id(
                payment_id))
            self._activity_log.record(user.user_id, "payment.failed", item)
            self._notifier.notify(
                user.user_id,
                f"Payment of RM {amount:.2f} for {item} was declined. "
                "Your booking is still pending; you can try again.")
            raise PaymentDeclined(result.message, payment)

        payment_id = self._repository.record_success(
            booking.booking_id, amount, result.reference)
        if payment_id is None:
            raise CannotPay("This booking is no longer waiting for "
                            "payment.")
        self._activity_log.record(user.user_id, "payment.succeeded", item)
        self._notifier.notify(
            user.user_id,
            f"Payment of RM {amount:.2f} received for {item}, card ending "
            f"{card.last_four}. Your booking is confirmed.")
        return Payment.from_row(self._repository.find_by_id(payment_id))

    # ------------------------------------------------------------------
    # Helpers

    @staticmethod
    def _payable(row):
        """Build a PayableBooking from a joined booking row."""
        return PayableBooking(Booking.from_row(row), row["listing_name"],
                              row["listing_location"])

    def _check_card(self, form):
        """Validate the card form and return a CardDetails.

        Raises:
            InvalidCard: One or more fields failed validation.
        """
        errors = {}
        holder = (form.get("holder_name") or "").strip()
        name_error = first_error(
            require(holder, "Name on card"),
            check_length(holder, "Name on card", maximum=60))
        if name_error:
            errors["holder_name"] = name_error

        number = clean_card_number(form.get("card_number"))
        if not number:
            errors["card_number"] = "Card number cannot be blank."
        elif not number.isdigit() or not 13 <= len(number) <= 19:
            errors["card_number"] = (
                "Card number must be 13 to 19 digits, such as "
                "4242 4242 4242 4242.")
        elif not luhn_valid(number):
            errors["card_number"] = (
                "That card number is not valid. Check it for typing "
                "mistakes.")

        month, year = self._check_expiry(form.get("expiry"), errors)

        cvv = (form.get("cvv") or "").strip()
        if not (cvv.isdigit() and len(cvv) in (3, 4)):
            errors["cvv"] = "Security code must be 3 or 4 digits."

        if errors:
            raise InvalidCard(errors)
        return CardDetails(holder, number, month, year, cvv)

    def _check_expiry(self, value, errors):
        """Check an ``MM/YY`` expiry date; return (month, full year)."""
        text = (value or "").strip()
        parts = text.split("/")
        if len(parts) != 2 or not all(
                part.strip().isdigit() for part in parts):
            errors["expiry"] = "Enter the expiry date as MM/YY, such as 08/28."
            return None, None
        month, year = int(parts[0]), 2000 + int(parts[1]) % 100
        if not 1 <= month <= 12:
            errors["expiry"] = "Expiry month must be between 01 and 12."
            return None, None
        today = self._today()
        if (year, month) < (today.year, today.month):
            errors["expiry"] = "This card has expired."
            return None, None
        return month, year
