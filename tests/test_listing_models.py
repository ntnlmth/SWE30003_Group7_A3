"""Tests for the Listing classes (CRC cards 5.14 to 5.19)."""

import pytest

from app.models.listing import (Accommodation, Attraction, DiningOutlet,
                                EventPromotion, Listing, TransportOption)


def make_row(listing_type, **changes):
    """Return a listings table row for ``listing_type``."""
    row = {
        "id": 7, "listing_type": listing_type, "operator_id": 2,
        "name": "Sample", "location": "Kuching", "description": "",
        "price": 100.0, "contact_phone": "082-123456",
        "opening_time": None, "closing_time": None, "room_count": None,
        "is_active": 1,
    }
    row.update(changes)
    return row


@pytest.mark.parametrize("listing_type, expected", [
    ("attraction", Attraction),
    ("accommodation", Accommodation),
    ("transport", TransportOption),
    ("dining", DiningOutlet),
    ("event", EventPromotion),
])
def test_from_row_builds_the_right_subtype(listing_type, expected):
    """Listing.from_row picks the subtype from the stored type name."""
    listing = Listing.from_row(make_row(listing_type))
    assert isinstance(listing, expected)
    assert listing.listing_type == listing_type
    assert listing.listing_id == 7


def test_only_accommodation_and_transport_can_be_booked():
    """Assumption A-2: attractions, dining and events are not booked."""
    bookable = {t: Listing.from_row(make_row(t)).is_bookable for t in (
        "attraction", "accommodation", "transport", "dining", "event")}
    assert bookable == {"attraction": False, "accommodation": True,
                        "transport": True, "dining": False, "event": False}


def test_events_cannot_be_reviewed():
    """Assumption A-8: every type except events can be reviewed."""
    assert not Listing.from_row(make_row("event")).is_reviewable
    assert Listing.from_row(make_row("accommodation")).is_reviewable


def test_deactivated_listing_is_hidden_from_tourists():
    """A deactivated listing reports its status and is not visible."""
    listing = Listing.from_row(make_row("accommodation", is_active=0))
    assert listing.status_label == "Deactivated"
    assert not listing.is_visible_to_tourists
    active = Listing.from_row(make_row("accommodation", is_active=1))
    assert active.status_label == "Active"
    assert active.is_visible_to_tourists


def test_attraction_knows_whether_it_is_open():
    """An attraction is open from opening time up to closing time."""
    attraction = Listing.from_row(make_row(
        "attraction", opening_time="09:00", closing_time="17:00"))
    assert attraction.is_open_at("09:00")
    assert attraction.is_open_at("16:59")
    assert not attraction.is_open_at("17:00")
    assert not attraction.is_open_at("08:30")


def test_listing_without_hours_counts_as_always_open():
    """No recorded hours means the listing is never reported closed."""
    assert Listing.from_row(make_row("dining")).is_open_at("03:00")


def test_accommodation_keeps_its_room_count():
    """Accommodation holds the number of rooms it offers."""
    listing = Listing.from_row(make_row("accommodation", room_count=20))
    assert listing.room_count == 20


def test_subtype_for_returns_the_class_for_a_type_name():
    """Listing.subtype_for maps a stored type name to its subclass."""
    assert Listing.subtype_for("dining") is DiningOutlet
    assert Listing.subtype_for("accommodation") is Accommodation


def test_form_values_gives_the_text_a_form_shows():
    """form_values turns stored details into form text."""
    listing = Listing.from_row(make_row(
        "accommodation", price=220.0, room_count=20, description=None))
    values = listing.form_values()
    assert values["price"] == "220.00"
    assert values["room_count"] == "20"
    assert values["description"] == ""
    assert values["opening_time"] == ""
