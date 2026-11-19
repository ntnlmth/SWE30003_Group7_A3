"""Tests for BookingManager (Area 1: search and book accommodation)."""

from datetime import date

import pytest

from app import create_app
from app.controllers.booking_manager import (BookingManager, BookingNotFound,
                                             CannotCancel, InvalidBooking,
                                             ListingNotFound, NotAllowed,
                                             NotAvailable)
from app.data.data_store import DataStore
from app.services.authenticator import Authenticator

TODAY = date(2026, 12, 1)


def today():
    """Return a fixed 'today' so date checks are deterministic."""
    return TODAY


@pytest.fixture
def app(tmp_path, isolated_store):
    """Use users and listings without linked demonstration records."""
    return create_app({
        "TESTING": True,
        "DATABASE": str(tmp_path / "booking-manager.db"),
        "SECRET_KEY": "test",
        "SEED_DEMO_DATA": False,
    })


@pytest.fixture
def store(app):
    """Return the DataStore on the test database."""
    return DataStore.get_instance()


@pytest.fixture
def manager(store):
    """Return a BookingManager on the test database, with a fixed date."""
    return BookingManager(store, today=today)


@pytest.fixture
def people(store):
    """Return the sample users by short name."""
    authenticator = Authenticator(store)
    return {
        "tasha": authenticator.find_by_email("tourist@example.com"),
        "omar": authenticator.find_by_email("operator@example.com"),
    }


def listing_id_named(store, name):
    """Return the id of the sample listing with this name."""
    return store.find_one(
        "SELECT id FROM listings WHERE name = ?", (name,))["id"]


def booking_form(**changes):
    """Return a valid booking form with ``changes`` applied."""
    form = {"check_in": "2026-12-10", "check_out": "2026-12-12",
            "guests": "2"}
    form.update(changes)
    return form


# ----------------------------------------------------------------- book

def test_tourist_books_accommodation_and_the_price_is_computed(
        manager, people, store):
    """A valid booking is saved with the right nights and price."""
    # 220/night.
    listing_id = listing_id_named(store, "Riverside Kuching Hotel")
    booking = manager.book(people["tasha"], listing_id, booking_form())
    assert booking.status == "pending"
    assert booking.nights == 2
    assert booking.total_price == 440.0
    assert booking.tourist_id == people["tasha"].user_id


def test_only_a_tourist_can_book(manager, people, store):
    """Operators and admin staff do not book accommodation."""
    listing_id = listing_id_named(store, "Riverside Kuching Hotel")
    with pytest.raises(NotAllowed):
        manager.book(people["omar"], listing_id, booking_form())


def test_cannot_book_a_non_accommodation_listing(manager, people, store):
    """Attractions and dining are not bookable through this area."""
    listing_id = listing_id_named(store, "Sarawak Cultural Village")
    with pytest.raises(ListingNotFound):
        manager.book(people["tasha"], listing_id, booking_form())


def test_cannot_book_a_deactivated_listing(manager, people, store):
    """A hidden listing cannot be found to book."""
    listing_id = listing_id_named(store, "Riverside Kuching Hotel")
    store.execute("UPDATE listings SET is_active = 0 WHERE id = ?",
                  (listing_id,))
    with pytest.raises(ListingNotFound):
        manager.book(people["tasha"], listing_id, booking_form())


@pytest.mark.parametrize("changes, field", [
    ({"check_in": "not-a-date"}, "check_in"),
    ({"check_in": "2026-11-01"}, "check_in"),  # before TODAY
    ({"check_out": "2026-12-05"}, "check_out"),  # before check-in
    ({"check_out": "2026-12-10"}, "check_out"),  # equal to check-in
    ({"guests": "0"}, "guests"),
    ({"guests": "abc"}, "guests"),
    ({"guests": ""}, "guests"),
])
def test_invalid_details_are_refused_and_nothing_is_saved(
        manager, people, store, changes, field):
    """Each bad field is reported and no booking row is written."""
    listing_id = listing_id_named(store, "Riverside Kuching Hotel")
    before = len(store.find_all("SELECT id FROM bookings"))
    with pytest.raises(InvalidBooking) as caught:
        manager.book(people["tasha"], listing_id, booking_form(**changes))
    assert field in caught.value.errors
    assert len(store.find_all("SELECT id FROM bookings")) == before


def test_booking_every_room_blocks_the_next_booking_for_those_dates(
        manager, people, store):
    """Assumption: each booking occupies one of the accommodation's rooms."""
    listing_id = listing_id_named(store, "Riverside Kuching Hotel")  # 20 rooms
    for _ in range(20):
        store.execute(
            "INSERT INTO bookings (tourist_id, listing_id, check_in, "
            "check_out, guests, total_price, status) VALUES "
            "(?, ?, '2026-12-10', '2026-12-12', 2, 440.0, 'pending')",
            (people["tasha"].user_id, listing_id))
    with pytest.raises(NotAvailable) as caught:
        manager.book(people["tasha"], listing_id, booking_form())
    assert caught.value.available_rooms == 0


def test_cancelled_bookings_do_not_count_against_availability(
        manager, people, store):
    """A cancelled booking frees its room back up."""
    listing_id = listing_id_named(store, "Damai Beach Resort")  # 12 rooms
    for _ in range(12):
        store.execute(
            "INSERT INTO bookings (tourist_id, listing_id, check_in, "
            "check_out, guests, total_price, status) VALUES "
            "(?, ?, '2026-12-10', '2026-12-12', 2, 760.0, 'cancelled')",
            (people["tasha"].user_id, listing_id))
    booking = manager.book(people["tasha"], listing_id, booking_form())
    assert booking.status == "pending"


def test_non_overlapping_dates_do_not_count_against_availability(
        manager, people, store):
    """A booking that ends before the new one starts does not clash."""
    listing_id = listing_id_named(store, "Damai Beach Resort")
    for _ in range(12):
        store.execute(
            "INSERT INTO bookings (tourist_id, listing_id, check_in, "
            "check_out, guests, total_price, status) VALUES "
            "(?, ?, '2026-12-01', '2026-12-10', 2, 760.0, 'pending')",
            (people["tasha"].user_id, listing_id))
    booking = manager.book(people["tasha"], listing_id, booking_form(
        check_in="2026-12-10", check_out="2026-12-12"))
    assert booking.status == "pending"


# --------------------------------------------------------------- cancel

def test_tourist_cancels_their_own_pending_booking(manager, people, store):
    """Cancelling sets the status without deleting the row."""
    listing_id = listing_id_named(store, "Riverside Kuching Hotel")
    booking = manager.book(people["tasha"], listing_id, booking_form())
    cancelled = manager.cancel_booking(people["tasha"], booking.booking_id)
    assert cancelled.status == "cancelled"
    assert store.find_one("SELECT id FROM bookings WHERE id = ?",
                          (booking.booking_id,)) is not None


def test_cancelling_frees_the_room_for_another_tourist(
        manager, people, store):
    """A change of mind: cancelling lets someone else book the room."""
    listing_id = listing_id_named(store, "Damai Beach Resort")
    for _ in range(12):
        store.execute(
            "INSERT INTO bookings (tourist_id, listing_id, check_in, "
            "check_out, guests, total_price, status) VALUES "
            "(?, ?, '2026-12-10', '2026-12-12', 2, 760.0, 'pending')",
            (people["tasha"].user_id, listing_id))
    full = store.find_all(
        "SELECT id FROM bookings WHERE listing_id = ? AND check_in = "
        "'2026-12-10'", (listing_id,))
    with pytest.raises(NotAvailable):
        manager.book(people["tasha"], listing_id, booking_form())
    manager.cancel_booking(people["tasha"], full[0]["id"])
    booking = manager.book(people["tasha"], listing_id, booking_form())
    assert booking.status == "pending"


def test_cannot_cancel_someone_elses_booking(manager, people, store):
    """Only the tourist who made a booking may cancel it."""
    listing_id = listing_id_named(store, "Riverside Kuching Hotel")
    booking = manager.book(people["tasha"], listing_id, booking_form())
    other = Authenticator(store).register(
        "Other Tourist", "other@example.com", "Password1!", "tourist")
    with pytest.raises(NotAllowed):
        manager.cancel_booking(other, booking.booking_id)


def test_cannot_cancel_an_already_cancelled_booking(manager, people, store):
    """A second cancel attempt is refused, not silently repeated."""
    listing_id = listing_id_named(store, "Riverside Kuching Hotel")
    booking = manager.book(people["tasha"], listing_id, booking_form())
    manager.cancel_booking(people["tasha"], booking.booking_id)
    with pytest.raises(CannotCancel):
        manager.cancel_booking(people["tasha"], booking.booking_id)


def test_cannot_cancel_a_booking_whose_check_in_has_passed(
        manager, people, store):
    """A booking cannot be cancelled once its stay has started."""
    listing_id = listing_id_named(store, "Riverside Kuching Hotel")
    store.execute(
        "INSERT INTO bookings (tourist_id, listing_id, check_in, "
        "check_out, guests, total_price, status) VALUES "
        "(?, ?, '2026-11-20', '2026-11-22', 2, 440.0, 'confirmed')",
        (people["tasha"].user_id, listing_id))
    booking_id = store.find_one(
        "SELECT id FROM bookings WHERE check_in = '2026-11-20'")["id"]
    with pytest.raises(CannotCancel):
        manager.cancel_booking(people["tasha"], booking_id)


def test_cancelling_an_unknown_booking_is_not_found(manager, people):
    """Cancelling an id that does not exist raises BookingNotFound."""
    with pytest.raises(BookingNotFound):
        manager.cancel_booking(people["tasha"], 9999)


# ---------------------------------------------------------- list_bookings

def test_list_bookings_flags_which_can_still_be_cancelled(
        manager, people, store):
    """may_cancel is true only for a future, non-cancelled booking."""
    listing_id = listing_id_named(store, "Riverside Kuching Hotel")
    booking = manager.book(people["tasha"], listing_id, booking_form())
    manager.cancel_booking(
        people["tasha"],
        manager.book(people["tasha"], listing_id, booking_form(
            check_in="2026-12-20", check_out="2026-12-21")).booking_id)
    views = {v.booking.check_in: v.may_cancel
             for v in manager.list_bookings(people["tasha"])}
    assert views[booking.check_in] is True
    assert views["2026-12-20"] is False
