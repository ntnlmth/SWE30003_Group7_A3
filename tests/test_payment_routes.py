"""Tests for the Pay for a booking screens (Scenario 2)."""

import pytest

from app import create_app
from app.data.data_store import DataStore


@pytest.fixture
def app(tmp_path, isolated_store):
    """Use users and listings without linked demonstration records."""
    return create_app({
        "TESTING": True,
        "DATABASE": str(tmp_path / "payment-routes.db"),
        "SECRET_KEY": "test",
        "SEED_DEMO_DATA": False,
    })


def page(response):
    """Return the response body as text."""
    return response.get_data(as_text=True)


def make_booking(client):
    """Book the Riverside hotel through the booking screen; return id."""
    store = DataStore.get_instance()
    listing_id = store.find_one(
        "SELECT id FROM listings WHERE name = 'Riverside Kuching Hotel'"
    )["id"]
    client.post(f"/bookings/{listing_id}/book", data={
        "check_in": "2027-01-10", "check_out": "2027-01-12",
        "guests": "2"})
    return store.find_one("SELECT id FROM bookings ORDER BY id DESC")["id"]


def card_form(**changes):
    """Return valid card form data."""
    form = {"holder_name": "Tasha Tourist",
            "card_number": "4242 4242 4242 4242",
            "expiry": "08/30", "cvv": "123"}
    form.update(changes)
    return form


def test_signed_out_user_is_sent_to_sign_in(client):
    """The payment screens need a signed-in tourist."""
    response = client.get("/payments/")
    assert response.status_code == 302
    assert "/auth/sign-in" in response.headers["Location"]


def test_new_booking_is_waiting_for_payment(client, sign_in):
    """A just-made booking shows on the payments screen."""
    sign_in("tourist@example.com")
    booking_id = make_booking(client)
    assert f"/payments/booking/{booking_id}" in page(
        client.get("/payments/"))


def test_payment_form_shows_amount_due(client, sign_in):
    """The form shows the booking and the amount to pay."""
    sign_in("tourist@example.com")
    booking_id = make_booking(client)
    text = page(client.get(f"/payments/booking/{booking_id}"))
    assert "Amount due: RM 440.00" in text
    assert "Riverside Kuching Hotel" in text


def test_successful_payment_shows_receipt_and_confirms(client, sign_in):
    """Paying shows the receipt, and the booking becomes confirmed."""
    sign_in("tourist@example.com")
    booking_id = make_booking(client)
    response = client.post(f"/payments/booking/{booking_id}",
                           data=card_form(), follow_redirects=True)
    text = page(response)
    assert "Payment successful" in text
    assert "Payment receipt" in text
    assert "SIM-" in text
    assert "Confirmed" in page(client.get("/bookings/mine"))


def test_declined_card_shows_message_and_allows_retry(client, sign_in):
    """A declined card explains why and leaves the booking payable."""
    sign_in("tourist@example.com")
    booking_id = make_booking(client)
    text = page(client.post(
        f"/payments/booking/{booking_id}",
        data=card_form(card_number="4000 0000 0000 0002")))
    assert "Payment declined." in text
    assert 'value="4000' not in text  # card number is not echoed back
    assert "Declined" in page(client.get("/payments/"))
    assert "Pending payment" in page(client.get("/bookings/mine"))


def test_bad_card_details_show_field_errors(client, sign_in):
    """Bad input is refused with a message per field."""
    sign_in("tourist@example.com")
    booking_id = make_booking(client)
    text = page(client.post(f"/payments/booking/{booking_id}",
                            data=card_form(cvv="1", expiry="99/99")))
    assert "Some card details need fixing" in text
    assert "Security code must be 3 or 4 digits." in text
    assert "Expiry month must be between 01 and 12." in text


def test_paid_booking_cannot_be_paid_again(client, sign_in):
    """Opening the form for a paid booking goes back with a message."""
    sign_in("tourist@example.com")
    booking_id = make_booking(client)
    client.post(f"/payments/booking/{booking_id}", data=card_form())
    response = client.get(f"/payments/booking/{booking_id}",
                          follow_redirects=True)
    assert "already been paid" in page(response)


def test_another_tourist_cannot_pay_or_see_receipt(client, sign_in):
    """Someone else's booking and receipt are refused."""
    sign_in("tourist@example.com")
    booking_id = make_booking(client)
    client.post(f"/payments/booking/{booking_id}", data=card_form())
    payment_id = DataStore.get_instance().find_one(
        "SELECT id FROM payments")["id"]
    client.post("/auth/sign-out")
    client.post("/auth/register", data={
        "name": "Other Tourist", "email": "other@example.com",
        "password": "Password1!", "role": "tourist"})
    assert "only for your own bookings" in page(client.get(
        f"/payments/booking/{booking_id}", follow_redirects=True))
    assert "receipt could not be found" in page(client.get(
        f"/payments/{payment_id}/receipt", follow_redirects=True))
