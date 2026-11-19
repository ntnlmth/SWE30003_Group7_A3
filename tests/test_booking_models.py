"""Tests for the Booking class (Area 1: search and book accommodation)."""

from app.models.booking import Booking


def make_row(**changes):
    """Return a bookings table row."""
    row = {
        "id": 3, "tourist_id": 1, "listing_id": 7, "check_in": "2026-12-05",
        "check_out": "2026-12-07", "guests": 2, "total_price": 440.0,
        "status": "pending", "created_at": "2026-11-01 10:00:00",
    }
    row.update(changes)
    return row


def test_from_row_builds_a_booking():
    """Booking.from_row reads every stored column."""
    booking = Booking.from_row(make_row())
    assert booking.booking_id == 3
    assert booking.tourist_id == 1
    assert booking.listing_id == 7
    assert booking.guests == 2
    assert booking.total_price == 440.0
    assert booking.status == "pending"


def test_nights_counts_the_date_range():
    """nights is the number of nights between check-in and check-out."""
    assert Booking.from_row(make_row(
        check_in="2026-12-05", check_out="2026-12-07")).nights == 2
    assert Booking.from_row(make_row(
        check_in="2026-12-05", check_out="2026-12-06")).nights == 1


def test_status_label_is_shown_in_plain_language():
    """Each stored status has a tourist-facing label."""
    assert Booking.from_row(
        make_row(status="pending")).status_label == "Pending payment"
    assert Booking.from_row(
        make_row(status="confirmed")).status_label == "Confirmed"
    assert Booking.from_row(
        make_row(status="cancelled")).status_label == "Cancelled"
