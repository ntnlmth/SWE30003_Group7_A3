"""Tests for ListingManager (CRC card 5.21)."""

from datetime import date, timedelta

import pytest

from app.controllers.listing_manager import (InvalidListing, ListingManager,
                                             ListingNotFound, NotAllowed,
                                             PossibleDuplicate)
from app import create_app
from app.data.data_store import DataStore
from app.services.authenticator import Authenticator


@pytest.fixture
def app(tmp_path, isolated_store):
    """Use users and listings without linked demonstration records."""
    return create_app({
        "TESTING": True,
        "DATABASE": str(tmp_path / "listing-manager.db"),
        "SECRET_KEY": "test",
        "SEED_DEMO_DATA": False,
    })


@pytest.fixture
def store(app):
    """Return the DataStore on the test database."""
    return DataStore.get_instance()


@pytest.fixture
def manager(store):
    """Return a ListingManager on the test database."""
    return ListingManager(store)


@pytest.fixture
def people(store):
    """Return the sample users by short name."""
    authenticator = Authenticator(store)
    return {
        "admin": authenticator.find_by_email("admin@example.com"),
        "omar": authenticator.find_by_email("operator@example.com"),
        "olivia": authenticator.find_by_email("operator2@example.com"),
        "tasha": authenticator.find_by_email("tourist@example.com"),
    }


def lodge_form(**changes):
    """Return a valid accommodation form with ``changes`` applied."""
    form = {
        "name": "Bako Lodge", "location": "Bako", "description": "Quiet.",
        "price": "180", "contact_phone": "082-555123", "room_count": "10",
        "opening_time": "", "closing_time": "",
    }
    form.update(changes)
    return form


def listing_id_named(store, name):
    """Return the id of the sample listing with this name."""
    return store.find_one(
        "SELECT id FROM listings WHERE name = ?", (name,))["id"]


def add_booking(store, tourist_id, listing_id, check_out, status="pending"):
    """Insert a booking that ends on ``check_out``."""
    check_in = (date.fromisoformat(check_out) - timedelta(days=2)).isoformat()
    store.execute(
        "INSERT INTO bookings (tourist_id, listing_id, check_in, "
        "check_out, guests, total_price, status) VALUES (?,?,?,?,?,?,?)",
        (tourist_id, listing_id, check_in, check_out, 2, 400.0, status))


def future(days=10):
    """Return an ISO date this many days from today."""
    return (date.today() + timedelta(days=days)).isoformat()


def past(days=10):
    """Return an ISO date this many days before today."""
    return (date.today() - timedelta(days=days)).isoformat()


# ---------------------------------------------------------------- adding

def test_operator_adds_listing_it_then_owns(manager, people, store):
    """A valid form saves the listing under the operator's id."""
    listing = manager.create_listing(
        people["omar"], "accommodation", lodge_form())
    assert listing.name == "Bako Lodge"
    assert listing.operator_id == people["omar"].user_id
    assert listing.is_active
    assert listing.room_count == 10


def test_admin_adds_attraction_with_normalised_times(manager, people):
    """Admin may add attractions; times are stored as HH:MM."""
    listing = manager.create_listing(
        people["admin"], "attraction",
        lodge_form(name="Fort Margherita", location="Kuching",
                   opening_time="9:00", closing_time="17:30",
                   room_count=""))
    assert listing.opening_time == "09:00"
    assert listing.closing_time == "17:30"
    assert listing.room_count is None
    assert listing.operator_id is None


def test_operator_cannot_add_an_attraction(manager, people):
    """Assumption A-1: attractions are admin-only."""
    with pytest.raises(NotAllowed):
        manager.create_listing(people["omar"], "attraction", lodge_form())


def test_tourist_cannot_add_anything(manager, people):
    """Tourists have no listing management rights."""
    with pytest.raises(NotAllowed):
        manager.create_listing(people["tasha"], "accommodation",
                               lodge_form())


def test_invalid_details_are_refused_and_nothing_is_saved(
        manager, people, store):
    """Errors come back per field and no row is written."""
    before = len(store.find_all("SELECT id FROM listings"))
    with pytest.raises(InvalidListing) as caught:
        manager.create_listing(people["omar"], "accommodation",
                               lodge_form(name="", price="-1"))
    assert "name" in caught.value.errors
    assert "price" in caught.value.errors
    assert len(store.find_all("SELECT id FROM listings")) == before


def test_duplicate_is_flagged_until_the_user_confirms(manager, people):
    """A likely duplicate stops the save unless confirmed."""
    form = lodge_form(name="Riverside Kuching Hotel", location="Kuching")
    with pytest.raises(PossibleDuplicate) as caught:
        manager.create_listing(people["omar"], "accommodation", form)
    assert caught.value.existing.name == "Riverside Kuching Hotel"
    listing = manager.create_listing(
        people["omar"], "accommodation", form, confirm_duplicate=True)
    assert listing.listing_id != caught.value.existing.listing_id


# --------------------------------------------------------------- updating

def test_operator_updates_own_listing(manager, people, store):
    """Changes are saved and the type stays the same."""
    listing_id = listing_id_named(store, "Riverside Kuching Hotel")
    updated = manager.update_listing(
        people["omar"], listing_id,
        lodge_form(name="Riverside Kuching Hotel", location="Kuching",
                   price="250", room_count="22"),
        confirm_duplicate=False)
    assert updated.price == 250.0
    assert updated.room_count == 22
    assert updated.listing_type == "accommodation"


def test_operator_cannot_update_another_operators_listing(
        manager, people, store):
    """Solution 1 rule: operators change only their own listings."""
    listing_id = listing_id_named(store, "Miri City Inn")
    with pytest.raises(NotAllowed):
        manager.update_listing(people["omar"], listing_id, lodge_form())


def test_admin_updates_any_listing(manager, people, store):
    """Admin staff may change a listing an operator owns."""
    listing_id = listing_id_named(store, "Miri City Inn")
    updated = manager.update_listing(
        people["admin"], listing_id,
        lodge_form(name="Miri City Inn", location="Miri", price="160"))
    assert updated.price == 160.0


def test_failed_update_keeps_the_stored_listing(manager, people, store):
    """A rejected update leaves the saved details untouched."""
    listing_id = listing_id_named(store, "Miri City Inn")
    with pytest.raises(InvalidListing):
        manager.update_listing(people["olivia"], listing_id,
                               lodge_form(contact_phone="abc"))
    assert manager.find_listing(listing_id).contact_phone == "085-345678"


def test_update_unknown_listing_is_not_found(manager, people):
    """Updating an id that does not exist raises ListingNotFound."""
    with pytest.raises(ListingNotFound):
        manager.update_listing(people["admin"], 9999, lodge_form())


# ---------------------------------------------------------------- removing

def test_unreferenced_listing_is_deleted(manager, people, store):
    """Nothing refers to the listing, so it is really deleted."""
    listing_id = listing_id_named(store, "Damai Beach Resort")
    result = manager.remove_listing(people["omar"], listing_id)
    assert result.outcome == "deleted"
    assert manager.find_listing(listing_id) is None


def test_listing_with_upcoming_booking_is_deactivated_not_deleted(
        manager, people, store):
    """Variant 6a: it is hidden but kept, and the booking is listed."""
    listing_id = listing_id_named(store, "Riverside Kuching Hotel")
    add_booking(store, people["tasha"].user_id, listing_id, future())
    result = manager.remove_listing(people["omar"], listing_id)
    assert result.outcome == "deactivated"
    assert len(result.references.upcoming_bookings) == 1
    assert result.references.upcoming_bookings[0]["tourist_name"] == (
        "Tasha Tourist")
    kept = manager.find_listing(listing_id)
    assert kept is not None and not kept.is_active


def test_past_booking_still_prevents_delete(manager, people, store):
    """A finished booking still refers to the listing, so keep the row."""
    listing_id = listing_id_named(store, "Riverside Kuching Hotel")
    add_booking(store, people["tasha"].user_id, listing_id, past())
    result = manager.remove_listing(people["omar"], listing_id)
    assert result.outcome == "deactivated"
    assert not result.references.has_upcoming


def test_cancelled_booking_is_not_listed_as_upcoming(
        manager, people, store):
    """A cancelled booking is not an affected booking."""
    listing_id = listing_id_named(store, "Riverside Kuching Hotel")
    add_booking(store, people["tasha"].user_id, listing_id, future(),
                status="cancelled")
    references = manager.find_references(listing_id)
    assert references.upcoming_bookings == []
    assert references.has_records


def test_itinerary_item_makes_the_listing_deactivate(
        manager, people, store):
    """An upcoming itinerary item is listed and blocks deletion."""
    listing_id = listing_id_named(store, "Sarawak Cultural Village")
    itinerary_id = store.execute(
        "INSERT INTO itineraries (tourist_id, title, start_date, "
        "end_date) VALUES (?, 'Santubong trip', ?, ?)",
        (people["tasha"].user_id, future(), future(2)))
    store.execute(
        "INSERT INTO itinerary_items (itinerary_id, listing_id, day, "
        "start_time, end_time) VALUES (?, ?, ?, '10:00', '12:00')",
        (itinerary_id, listing_id, future()))
    result = manager.remove_listing(people["admin"], listing_id)
    assert result.outcome == "deactivated"
    assert result.references.upcoming_items[0]["itinerary_title"] == (
        "Santubong trip")


def test_operator_cannot_remove_another_operators_listing(
        manager, people, store):
    """The ownership rule also covers removal."""
    listing_id = listing_id_named(store, "Miri City Inn")
    with pytest.raises(NotAllowed):
        manager.remove_listing(people["omar"], listing_id)
    assert manager.find_listing(listing_id) is not None


def test_deactivated_listing_can_be_reactivated(manager, people, store):
    """A change of mind: the listing becomes visible again."""
    listing_id = listing_id_named(store, "Riverside Kuching Hotel")
    add_booking(store, people["tasha"].user_id, listing_id, future())
    manager.remove_listing(people["omar"], listing_id)
    restored = manager.reactivate_listing(people["omar"], listing_id)
    assert restored.is_active


# ------------------------------------------------------------- listing

def test_operator_sees_only_own_listings(manager, people):
    """An operator's list leaves out other operators' listings."""
    names = [item.name for item in manager.list_listings(people["omar"])]
    assert names == ["Damai Beach Resort", "Riverside Kuching Hotel"]


def test_admin_sees_every_listing_and_can_filter(manager, people):
    """Admin sees all five sample listings; filters narrow them."""
    assert len(manager.list_listings(people["admin"])) == 5
    dining = manager.list_listings(people["admin"], listing_type="dining")
    assert [item.name for item in dining] == ["Top Spot Food Court"]
    found = manager.list_listings(people["admin"], search="miri")
    assert [item.name for item in found] == ["Miri City Inn"]


def test_status_filter_separates_active_and_deactivated(
        manager, people, store):
    """The status filter shows only deactivated listings when asked."""
    listing_id = listing_id_named(store, "Riverside Kuching Hotel")
    add_booking(store, people["tasha"].user_id, listing_id, future())
    manager.remove_listing(people["omar"], listing_id)
    hidden = manager.list_listings(people["omar"], status="deactivated")
    assert [item.name for item in hidden] == ["Riverside Kuching Hotel"]
    active = manager.list_listings(people["omar"], status="active")
    assert [item.name for item in active] == ["Damai Beach Resort"]


# -------------------------------------------------------------- audit

def test_every_change_is_recorded_with_who_and_what(
        manager, people, store):
    """The audit trail names the user, the action and the listing."""
    manager.create_listing(people["omar"], "accommodation", lodge_form())
    rows = store.find_all(
        "SELECT user_id, ACTION, item FROM activity_log")
    assert rows == [{"user_id": people["omar"].user_id,
                     "action": "listing.created",
                     "item": rows[0]["item"]}]
    assert rows[0]["item"].startswith("Bako Lodge (#")


def test_a_failed_change_leaves_no_audit_entry(manager, people, store):
    """Nothing is logged when validation refuses the change."""
    with pytest.raises(InvalidListing):
        manager.create_listing(people["omar"], "accommodation",
                               lodge_form(name=""))
    assert store.find_all("SELECT id FROM activity_log") == []


def test_supplied_activity_log_is_used_instead_of_the_table(
        store, people):
    """An ActivityLog object, when given, receives the entries."""

    class FakeLog:
        """Collect calls so the test can inspect them."""

        def __init__(self):
            self.calls = []

        def record(self, user_id, action, item):
            self.calls.append((user_id, action, item))

    log = FakeLog()
    manager = ListingManager(store, activity_log=log)
    manager.create_listing(people["omar"], "accommodation", lodge_form())
    assert log.calls[0][:2] == (people["omar"].user_id, "listing.created")
    assert store.find_all("SELECT id FROM activity_log") == []
