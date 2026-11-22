"""Tests for PaymentManager and the payment gateway (Area 2)."""

from datetime import date

import pytest

from app import create_app
from app.controllers.payment_manager import (BookingNotFound, CannotPay,
                                             InvalidCard, NotAllowed,
                                             PaymentDeclined, PaymentManager,
                                             PaymentNotFound, luhn_valid)
from app.data.data_store import DataStore
from app.models.payment import Payment
from app.services.authenticator import Authenticator
from app.services.payment_gateway import (CardDetails, PaymentGatewayAdapter,
                                          SimulatedPaymentGateway)

TODAY = date(2026, 12, 1)
GOOD_CARD = "4242 4242 4242 4242"


def today():
    """Return a fixed 'today' so date checks are deterministic."""
    return TODAY


@pytest.fixture
def app(tmp_path, isolated_store):
    """Use users and listings without linked demonstration records."""
    return create_app({
        "TESTING": True,
        "DATABASE": str(tmp_path / "payment-manager.db"),
        "SECRET_KEY": "test",
        "SEED_DEMO_DATA": False,
    })


@pytest.fixture
def store(app):
    """Return the DataStore on the test database."""
    return DataStore.get_instance()


@pytest.fixture
def manager(store):
    """Return a PaymentManager on the test database, with a fixed date."""
    return PaymentManager(store, today=today)


@pytest.fixture
def people(store):
    """Return the sample users by short name."""
    authenticator = Authenticator(store)
    return {
        "tasha": authenticator.find_by_email("tourist@example.com"),
        "omar": authenticator.find_by_email("operator@example.com"),
    }


def add_booking(store, tourist, status="pending", check_in="2026-12-10",
                check_out="2026-12-12", total=440.0):
    """Insert a booking of the Riverside hotel and return its id."""
    listing = store.find_one(
        "SELECT id FROM listings WHERE name = 'Riverside Kuching Hotel'")
    return store.execute(
        "INSERT INTO bookings (tourist_id, listing_id, check_in, "
        "check_out, guests, total_price, status) "
        "VALUES (?, ?, ?, ?, 2, ?, ?)",
        (tourist.user_id, listing["id"], check_in, check_out, total,
         status))


def card_form(**changes):
    """Return valid card form data."""
    form = {"holder_name": "Tasha Tourist", "card_number": GOOD_CARD,
            "expiry": "08/28", "cvv": "123"}
    form.update(changes)
    return form


def booking_status(store, booking_id):
    """Return the stored status of a booking."""
    return store.find_one(
        "SELECT status FROM bookings WHERE id = ?", (booking_id,))["status"]


# ------------------------------------------------------------ paying

def test_successful_payment_confirms_the_booking(store, manager, people):
    """An approved card saves a Payment and confirms the booking."""
    booking_id = add_booking(store, people["tasha"])
    payment = manager.pay(people["tasha"], booking_id, card_form())
    assert isinstance(payment, Payment)
    assert payment.succeeded
    assert payment.amount == 440.0
    assert payment.reference.startswith("SIM-")
    assert booking_status(store, booking_id) == "confirmed"


def test_amount_comes_from_the_booking_not_the_form(store, manager, people):
    """A tampered amount in the form is ignored."""
    booking_id = add_booking(store, people["tasha"], total=760.0)
    payment = manager.pay(people["tasha"], booking_id,
                          card_form(amount="1.00"))
    assert payment.amount == 760.0


def test_success_notifies_and_logs(store, manager, people):
    """The tourist is notified and the payment is in the audit trail."""
    booking_id = add_booking(store, people["tasha"])
    manager.pay(people["tasha"], booking_id, card_form())
    note = store.find_one("SELECT message FROM notifications")
    assert "RM 440.00 received" in note["message"]
    assert "card ending 4242" in note["message"]
    entry = store.find_one("SELECT action, item FROM activity_log")
    assert entry["action"] == "payment.succeeded"
    assert f"booking #{booking_id}" in entry["item"]


def test_card_number_is_never_saved(store, manager, people):
    """No column in any payment-related table holds the card number."""
    booking_id = add_booking(store, people["tasha"])
    manager.pay(people["tasha"], booking_id, card_form())
    for table in ("payments", "notifications", "activity_log"):
        for row in store.find_all(f"SELECT * FROM {table}"):
            assert "4242424242424242" not in str(row)


@pytest.mark.parametrize("number, message", [
    ("4000 0000 0000 0002", "declined by the bank"),
    ("4000 0000 0000 9995", "insufficient funds"),
])
def test_declined_payment_is_saved_and_booking_stays_pending(
        store, manager, people, number, message):
    """A declined card is recorded as failed; the tourist can retry."""
    booking_id = add_booking(store, people["tasha"])
    with pytest.raises(PaymentDeclined) as caught:
        manager.pay(people["tasha"], booking_id,
                    card_form(card_number=number))
    assert message in str(caught.value)
    assert caught.value.payment.status == "failed"
    assert booking_status(store, booking_id) == "pending"
    assert store.find_one(
        "SELECT action FROM activity_log")["action"] == "payment.failed"
    # Retrying with a good card then works.
    assert manager.pay(people["tasha"], booking_id, card_form()).succeeded


def test_booking_cannot_be_paid_twice(store, manager, people):
    """Once paid, a second payment is refused."""
    booking_id = add_booking(store, people["tasha"])
    manager.pay(people["tasha"], booking_id, card_form())
    with pytest.raises(CannotPay, match="already been paid"):
        manager.pay(people["tasha"], booking_id, card_form())
    assert store.find_one(
        "SELECT COUNT(*) AS n FROM payments")["n"] == 1


def test_cancelled_booking_cannot_be_paid(store, manager, people):
    """A cancelled booking is refused before the card is charged."""
    booking_id = add_booking(store, people["tasha"], status="cancelled")
    with pytest.raises(CannotPay, match="cancelled"):
        manager.pay(people["tasha"], booking_id, card_form())


def test_booking_cannot_be_paid_after_check_in(store, manager, people):
    """A booking whose check-in date has passed cannot be paid."""
    booking_id = add_booking(store, people["tasha"],
                             check_in="2026-11-20", check_out="2026-11-22")
    with pytest.raises(CannotPay, match="check-in date has passed"):
        manager.pay(people["tasha"], booking_id, card_form())


def test_only_the_owner_can_pay(store, manager, people):
    """Paying for someone else's booking, or as a non-tourist, fails."""
    booking_id = add_booking(store, people["tasha"])
    with pytest.raises(NotAllowed):
        manager.pay(people["omar"], booking_id, card_form())


def test_unknown_booking(manager, people):
    """A booking id that does not exist is reported clearly."""
    with pytest.raises(BookingNotFound):
        manager.pay(people["tasha"], 9999, card_form())


# --------------------------------------------------------- validation

@pytest.mark.parametrize("changes, field, message", [
    ({"holder_name": ""}, "holder_name", "cannot be blank"),
    ({"card_number": ""}, "card_number", "cannot be blank"),
    ({"card_number": "4242abcd"}, "card_number", "13 to 19 digits"),
    ({"card_number": "4242 4242 4242 4241"}, "card_number", "not valid"),
    ({"expiry": "2028-08"}, "expiry", "MM/YY"),
    ({"expiry": "13/28"}, "expiry", "between 01 and 12"),
    ({"expiry": "11/26"}, "expiry", "expired"),
    ({"cvv": "12"}, "cvv", "3 or 4 digits"),
])
def test_bad_card_details_are_rejected(store, manager, people, changes,
                                       field, message):
    """Each bad field gets its own message and nothing is charged."""
    booking_id = add_booking(store, people["tasha"])
    with pytest.raises(InvalidCard) as caught:
        manager.pay(people["tasha"], booking_id, card_form(**changes))
    assert message in caught.value.errors[field]
    assert store.find_one("SELECT COUNT(*) AS n FROM payments")["n"] == 0


def test_card_expiring_this_month_is_accepted(store, manager, people):
    """A card is valid until the end of its expiry month."""
    booking_id = add_booking(store, people["tasha"])
    assert manager.pay(people["tasha"], booking_id,
                       card_form(expiry="12/26")).succeeded


def test_luhn_check():
    """The Luhn check accepts real test numbers and rejects typos."""
    assert luhn_valid("4242424242424242")
    assert not luhn_valid("4242424242424241")


# ------------------------------------------------------------ listings

def test_lists_only_unpaid_future_bookings(store, manager, people):
    """The 'waiting for payment' list skips paid, cancelled and past."""
    pending = add_booking(store, people["tasha"])
    add_booking(store, people["tasha"], status="confirmed")
    add_booking(store, people["tasha"], status="cancelled")
    add_booking(store, people["tasha"], check_in="2026-11-20",
                check_out="2026-11-22")
    unpaid = manager.list_unpaid(people["tasha"])
    assert [item.booking.booking_id for item in unpaid] == [pending]


def test_receipt_only_for_own_successful_payment(store, manager, people):
    """Receipts exist only for the owner's successful payments."""
    booking_id = add_booking(store, people["tasha"])
    payment = manager.pay(people["tasha"], booking_id, card_form())
    view = manager.get_receipt(people["tasha"], payment.payment_id)
    assert view.listing_name == "Riverside Kuching Hotel"
    with pytest.raises(PaymentNotFound):
        manager.get_receipt(people["omar"], payment.payment_id)


# ------------------------------------------------------------- adapter

def test_adapter_translates_to_the_gateway_interface():
    """The adapter sends cents and MM/YY, and maps the reply back."""
    sent = {}

    class RecordingGateway(SimulatedPaymentGateway):
        def submit_transaction(self, request):
            sent.update(request)
            return super().submit_transaction(request)

    adapter = PaymentGatewayAdapter(RecordingGateway())
    card = CardDetails("Tasha", "4242424242424242", 8, 2028, "123")
    result = adapter.charge(440.5, card)
    assert sent["amount_cents"] == 44050
    assert sent["currency"] == "MYR"
    assert sent["exp"] == "08/28"
    assert result.approved and result.reference == "SIM-000001"
