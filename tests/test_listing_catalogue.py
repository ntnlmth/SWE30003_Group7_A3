"""Tests for ListingCatalogue (Area 1: search and book accommodation)."""

import pytest

from app import create_app
from app.controllers.listing_catalogue import ListingCatalogue
from app.data.data_store import DataStore


@pytest.fixture
def app(tmp_path, isolated_store):
    """Use the sample listings without linked demonstration records."""
    return create_app({
        "TESTING": True,
        "DATABASE": str(tmp_path / "catalogue.db"),
        "SECRET_KEY": "test",
        "SEED_DEMO_DATA": False,
    })


@pytest.fixture
def catalogue(app):
    """Return a ListingCatalogue on the test database."""
    return ListingCatalogue(DataStore.get_instance())


def listing_id_named(name):
    """Return the id of the sample listing with this name."""
    return DataStore.get_instance().find_one(
        "SELECT id FROM listings WHERE name = ?", (name,))["id"]


def test_search_returns_only_active_accommodation(catalogue):
    """Attractions and dining never appear; deactivated hotels do not."""
    store = DataStore.get_instance()
    store.execute("UPDATE listings SET is_active = 0 WHERE name = ?",
                  ("Miri City Inn",))
    names = {r.listing.name for r in catalogue.search_accommodation()}
    assert names == {"Riverside Kuching Hotel", "Damai Beach Resort"}


def test_search_filters_by_location_text(catalogue):
    """The location filter matches name or location, like listings."""
    names = {r.listing.name
             for r in catalogue.search_accommodation(location="Santubong")}
    assert names == {"Damai Beach Resort"}


def test_search_without_dates_has_no_availability_count(catalogue):
    """No dates means availability is not computed (always bookable)."""
    result = catalogue.search_accommodation()[0]
    assert result.available_rooms is None
    assert result.has_availability


def test_search_with_dates_counts_free_rooms(catalogue):
    """Overlapping bookings reduce the free-room count for those dates."""
    store = DataStore.get_instance()
    listing_id = listing_id_named("Miri City Inn")  # 30 rooms
    for _ in range(3):
        store.execute(
            "INSERT INTO bookings (tourist_id, listing_id, check_in, "
            "check_out, guests, total_price, status) VALUES "
            "(1, ?, '2026-12-10', '2026-12-12', 2, 300.0, 'pending')",
            (listing_id,))
    results = {r.listing.name: r.available_rooms for r in
               catalogue.search_accommodation(
                   check_in="2026-12-10", check_out="2026-12-12")}
    assert results["Miri City Inn"] == 27
    assert results["Riverside Kuching Hotel"] == 20


def test_find_bookable_rejects_inactive_and_non_accommodation(catalogue):
    """A deactivated hotel and a non-accommodation listing are refused."""
    store = DataStore.get_instance()
    hotel_id = listing_id_named("Riverside Kuching Hotel")
    store.execute("UPDATE listings SET is_active = 0 WHERE id = ?",
                  (hotel_id,))
    attraction_id = listing_id_named("Sarawak Cultural Village")
    assert catalogue.find_bookable(hotel_id) is None
    assert catalogue.find_bookable(attraction_id) is None
    assert catalogue.find_bookable(9999) is None


def test_find_bookable_returns_an_active_accommodation(catalogue):
    """An active accommodation is returned for booking."""
    listing_id = listing_id_named("Damai Beach Resort")
    found = catalogue.find_bookable(listing_id)
    assert found.name == "Damai Beach Resort"
    assert found.is_bookable
