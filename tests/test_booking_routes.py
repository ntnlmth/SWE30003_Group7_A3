"""Tests for the Search and book accommodation screens (Scenario 1)."""

import pytest

from app import create_app
from app.data.data_store import DataStore
from app.services.activity_log import ActivityLog


@pytest.fixture
def app(tmp_path, isolated_store):
    """Use users and listings without linked demonstration records."""
    return create_app({
        "TESTING": True,
        "DATABASE": str(tmp_path / "booking-routes.db"),
        "SECRET_KEY": "test",
        "SEED_DEMO_DATA": False,
    })


def listing_id_named(name):
    """Return the id of the sample listing with this name."""
    return DataStore.get_instance().find_one(
        "SELECT id FROM listings WHERE name = ?", (name,))["id"]


def page(response):
    """Return the response body as text."""
    return response.get_data(as_text=True)


def booking_form(**changes):
    """Return valid form data for a new booking."""
    form = {"check_in": "2026-12-10", "check_out": "2026-12-12",
            "guests": "2"}
    form.update(changes)
    return form


# ----------------------------------------------------------------- search

def test_signed_out_user_is_sent_to_sign_in(client):
    """The booking screens need a signed-in tourist."""
    response = client.get("/bookings/")
    assert response.status_code == 302
    assert "/auth/sign-in" in response.headers["Location"]


def test_operator_cannot_open_the_booking_screens(client, sign_in):
    """Only tourists search and book accommodation."""
    sign_in("operator@example.com")
    assert client.get("/bookings/").status_code == 302


def test_search_screen_starts_empty(client, sign_in):
    """The empty screen at the start of the scenario shows no results."""
    sign_in("tourist@example.com")
    text = page(client.get("/bookings/"))
    assert "Search by location" in text
    assert "Riverside Kuching Hotel" not in text


def test_search_with_no_filters_shows_every_active_accommodation(
        client, sign_in):
    """Searching with everything blank lists every active hotel."""
    sign_in("tourist@example.com")
    text = page(client.get(
        "/bookings/?location=&check_in=&check_out=2026-12-12"))
    assert "Riverside Kuching Hotel" in text
    assert "Miri City Inn" in text


def test_search_filters_by_location(client, sign_in):
    """A location filter narrows the results."""
    sign_in("tourist@example.com")
    text = page(client.get("/bookings/?location=Santubong"))
    assert "Damai Beach Resort" in text
    assert "Riverside Kuching Hotel" not in text


# ------------------------------------------------------------------ book

def test_booking_form_starts_with_the_accommodation_shown(client, sign_in):
    """The booking form names the accommodation and its price."""
    sign_in("tourist@example.com")
    listing_id = listing_id_named("Riverside Kuching Hotel")
    text = page(client.get(f"/bookings/{listing_id}/book"))
    assert "Book: Riverside Kuching Hotel" in text
    assert "220.00" in text


def test_correct_input_creates_a_pending_booking(client, sign_in):
    """Correct input books the room and shows a success message."""
    sign_in("tourist@example.com")
    listing_id = listing_id_named("Riverside Kuching Hotel")
    response = client.post(f"/bookings/{listing_id}/book",
                           data=booking_form(), follow_redirects=True)
    text = page(response)
    assert "has been created and is pending payment" in text
    assert "Pending payment" in text
    assert "440.00" in text


def test_rejected_input_shows_each_error_and_keeps_the_values(
        client, sign_in):
    """Bad input is refused with field messages; typed text is kept."""
    sign_in("tourist@example.com")
    listing_id = listing_id_named("Riverside Kuching Hotel")
    text = page(client.post(f"/bookings/{listing_id}/book", data=booking_form(
        check_out="2026-12-05", guests="0")))
    assert "Check-out must be after check-in." in text
    assert "Number of guests must be 1 or more." in text
    assert "Some details need fixing" in text


def test_fully_booked_dates_show_the_available_room_count(
        client, sign_in):
    """When every room is taken, the screen explains why, not a crash."""
    sign_in("tourist@example.com")
    store = DataStore.get_instance()
    listing_id = listing_id_named("Damai Beach Resort")  # 12 rooms
    tourist = store.find_one(
        "SELECT id FROM users WHERE email = 'tourist@example.com'")
    for _ in range(12):
        store.execute(
            "INSERT INTO bookings (tourist_id, listing_id, check_in, "
            "check_out, guests, total_price, status) VALUES "
            "(?, ?, '2026-12-10', '2026-12-12', 2, 760.0, 'pending')",
            (tourist["id"], listing_id))
    text = page(client.post(f"/bookings/{listing_id}/book",
                            data=booking_form()))
    assert "No room is free for those dates" in text


# --------------------------------------------------------------- my bookings

def test_my_bookings_starts_empty(client, sign_in):
    """A tourist with no bookings sees the empty message."""
    sign_in("tourist@example.com")
    assert "no bookings yet" in page(client.get("/bookings/mine"))


def test_cancel_confirmation_then_cancellation(client, sign_in):
    """A change of mind: confirm, then the booking is cancelled."""
    sign_in("tourist@example.com")
    listing_id = listing_id_named("Riverside Kuching Hotel")
    client.post(f"/bookings/{listing_id}/book", data=booking_form())
    booking_id = DataStore.get_instance().find_one(
        "SELECT id FROM bookings ORDER BY id DESC")["id"]

    confirm_text = page(client.get(f"/bookings/{booking_id}/cancel"))
    assert "Cancel booking" in confirm_text

    response = client.post(f"/bookings/{booking_id}/cancel",
                           follow_redirects=True)
    text = page(response)
    assert "Booking cancelled." in text
    assert "Cancelled" in text


def test_tourist_cannot_cancel_another_tourists_booking(client, sign_in):
    """Cancelling someone else's booking id is refused."""
    sign_in("tourist@example.com")
    listing_id = listing_id_named("Riverside Kuching Hotel")
    client.post(f"/bookings/{listing_id}/book", data=booking_form())
    booking_id = DataStore.get_instance().find_one(
        "SELECT id FROM bookings ORDER BY id DESC")["id"]
    client.post("/auth/sign-out")
    sign_in("operator@example.com")
    client.post("/auth/sign-out")
    client.post("/auth/register", data={
        "name": "Other Tourist", "email": "other@example.com",
        "password": "Password1!", "role": "tourist"})
    response = client.get(f"/bookings/{booking_id}/cancel",
                          follow_redirects=True)
    assert "You may cancel only your own bookings." in page(response)


# ------------------------------------------------------------ audit trail

def test_booking_is_recorded_by_the_activity_log(client, sign_in):
    """Booking a room leaves an entry the ActivityLog can read back."""
    sign_in("tourist@example.com")
    listing_id = listing_id_named("Riverside Kuching Hotel")
    client.post(f"/bookings/{listing_id}/book", data=booking_form())
    store = DataStore.get_instance()
    tourist = store.find_one(
        "SELECT id FROM users WHERE email = 'tourist@example.com'")
    entries = ActivityLog(store).entries_for(tourist["id"])
    assert entries[0]["action"] == "booking.created"
    assert entries[0]["item"].startswith("Riverside Kuching Hotel")
