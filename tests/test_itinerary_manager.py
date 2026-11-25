"""Tests for ItineraryManager and Scheduler."""

from datetime import date, timedelta

import pytest

from app import create_app
from app.controllers.itinerary_manager import (
    InvalidItinerary,
    ItineraryManager,
    NotAllowed,
    ScheduleConflict,
)
from app.data.data_store import DataStore
from app.services.authenticator import Authenticator


@pytest.fixture
def app(tmp_path, isolated_store):
    """Use sample users and listings without demo itineraries."""
    return create_app({
        "TESTING": True,
        "DATABASE": str(tmp_path / "itinerary-manager.db"),
        "SECRET_KEY": "test",
        "SEED_DEMO_DATA": False,
    })


@pytest.fixture
def store(app):
    """Return the isolated DataStore."""
    return DataStore.get_instance()


@pytest.fixture
def manager(store):
    """Return an ItineraryManager."""
    return ItineraryManager(store)


@pytest.fixture
def people(store):
    """Return the sample tourist and operator."""
    auth = Authenticator(store)
    return {
        "tourist": auth.find_by_email("tourist@example.com"),
        "operator": auth.find_by_email("operator@example.com"),
    }


def date_range(days_ahead=1, length=2):
    """Return valid future ISO dates."""
    start = date.today() + timedelta(days=days_ahead)
    end = start + timedelta(days=length)
    return start.isoformat(), end.isoformat()


def test_create_and_get_itinerary(manager, people):
    """A tourist can create and retrieve an owned itinerary."""
    start, end = date_range()
    itinerary = manager.create_itinerary(
        people["tourist"],
        {"title": "Kuching trip", "start_date": start, "end_date": end},
    )
    loaded = manager.get_itinerary(
        people["tourist"], itinerary.itinerary_id)
    assert loaded.title == "Kuching trip"
    assert loaded.day_count == 3


def test_invalid_date_range_is_refused(manager, people):
    """End date cannot precede start date."""
    start, _ = date_range()
    with pytest.raises(InvalidItinerary) as caught:
        manager.create_itinerary(
            people["tourist"],
            {"title": "Bad trip", "start_date": start,
             "end_date": (date.fromisoformat(start)
                          - timedelta(days=1)).isoformat()},
        )
    assert "end_date" in caught.value.errors


def test_operator_cannot_create_itinerary(manager, people):
    """Only tourists may plan itineraries."""
    start, end = date_range()
    with pytest.raises(NotAllowed):
        manager.create_itinerary(
            people["operator"],
            {"title": "No", "start_date": start, "end_date": end},
        )


def test_overlap_is_not_saved(manager, people, store):
    """Overlapping slots on the same day are rejected."""
    start, end = date_range()
    itinerary = manager.create_itinerary(
        people["tourist"],
        {"title": "Schedule test", "start_date": start, "end_date": end},
    )
    attraction = store.find_one(
        "SELECT id FROM listings WHERE name = ?", (
            "Sarawak Cultural Village",))
    dining = store.find_one(
        "SELECT id FROM listings WHERE name = ?", (
            "Top Spot Food Court",))
    manager.add_item(
        people["tourist"], itinerary.itinerary_id,
        {"listing_id": str(attraction["id"]), "day": start,
         "start_time": "09:00", "end_time": "11:00"},
    )
    with pytest.raises(ScheduleConflict):
        manager.add_item(
            people["tourist"], itinerary.itinerary_id,
            {"listing_id": str(dining["id"]), "day": start,
             "start_time": "10:30", "end_time": "12:00"},
        )
    assert len(manager.get_itinerary(
        people["tourist"], itinerary.itinerary_id).items) == 1


def test_adjacent_slots_are_allowed(manager, people, store):
    """A half-open time interval allows back-to-back activities."""
    start, end = date_range()
    itinerary = manager.create_itinerary(
        people["tourist"],
        {"title": "Adjacent", "start_date": start, "end_date": end},
    )
    attraction = store.find_one(
        "SELECT id FROM listings WHERE name = ?", (
            "Sarawak Cultural Village",))
    dining = store.find_one(
        "SELECT id FROM listings WHERE name = ?", (
            "Top Spot Food Court",))
    manager.add_item(
        people["tourist"], itinerary.itinerary_id,
        {"listing_id": str(attraction["id"]), "day": start,
         "start_time": "09:00", "end_time": "17:00"},
    )
    item = manager.add_item(
        people["tourist"], itinerary.itinerary_id,
        {"listing_id": str(dining["id"]), "day": start,
         "start_time": "17:00", "end_time": "18:00"},
    )
    assert item.start_time == "17:00"


def test_listing_hours_are_enforced(manager, people, store):
    """Dining outside opening hours is rejected."""
    start, end = date_range()
    itinerary = manager.create_itinerary(
        people["tourist"],
        {"title": "Hours", "start_date": start, "end_date": end},
    )
    dining = store.find_one(
        "SELECT id FROM listings WHERE name = ?", (
            "Top Spot Food Court",))
    with pytest.raises(ScheduleConflict) as caught:
        manager.add_item(
            people["tourist"], itinerary.itinerary_id,
            {"listing_id": str(dining["id"]), "day": start,
             "start_time": "12:00", "end_time": "13:00"},
        )
    assert caught.value.clashes[0].kind == "hours"


def test_item_must_be_inside_itinerary_dates(manager, people, store):
    """A day outside the selected range is refused."""
    start, end = date_range()
    itinerary = manager.create_itinerary(
        people["tourist"],
        {"title": "Range", "start_date": start, "end_date": end},
    )
    attraction = store.find_one(
        "SELECT id FROM listings WHERE name = ?", (
            "Sarawak Cultural Village",))
    outside = (date.fromisoformat(end) + timedelta(days=1)).isoformat()
    with pytest.raises(InvalidItinerary) as caught:
        manager.add_item(
            people["tourist"], itinerary.itinerary_id,
            {"listing_id": str(attraction["id"]), "day": outside,
             "start_time": "09:00", "end_time": "10:00"},
        )
    assert "day" in caught.value.errors
