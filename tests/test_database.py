"""Database integration tests; every test uses a disposable SQLite database."""

import sqlite3

import pytest

from app.data.data_store import DataStore
from app.data.seed import seed_sample_data


@pytest.fixture
def store(app):
    """Use the existing app fixture's isolated database."""
    return DataStore.get_instance(app.config["DATABASE"])


def test_linked_demo_scenarios(store):
    rows = store.find_all(
        "SELECT b.*, p.status AS payment_status, p.amount, u.role, "
        "l.listing_type, l.price FROM bookings b "
        "JOIN users u ON u.id = b.tourist_id "
        "JOIN listings l ON l.id = b.listing_id "
        "LEFT JOIN payments p ON p.booking_id = b.id ORDER BY b.check_in")
    assert [(r["status"], r["payment_status"]) for r in rows] == [
        ("pending", None), ("confirmed", "success"),
        ("pending", "failed"), ("cancelled", None)]
    for row in rows:
        assert row["role"] == "tourist"
        assert row["listing_type"] == "accommodation"
        assert row["check_in"] < row["check_out"]
        assert row["total_price"] == row["price"] * 2
        if row["payment_status"]:
            assert row["amount"] == row["total_price"]
    assert store.find_all("PRAGMA foreign_key_check") == []
    assert store.find_one("PRAGMA integrity_check")["integrity_check"] == "ok"
    assert len(store.find_all("SELECT * FROM notifications")) == 5


def test_itinerary_dates_and_no_overlaps(store):
    itinerary = store.find_one("SELECT * FROM itineraries")
    items = store.find_all(
        "SELECT * FROM itinerary_items WHERE itinerary_id = ? "
        "ORDER BY day, start_time", (itinerary["id"],))
    assert len(items) == 4
    for item in items:
        assert itinerary["start_date"] <= item["day"] <= itinerary["end_date"]
        assert item["start_time"] < item["end_time"]
    for previous, current in zip(items, items[1:]):
        if previous["day"] == current["day"]:
            assert previous["end_time"] <= current["start_time"]


def test_reseed_preserves_existing_and_edited_records(store):
    store.execute("UPDATE bookings SET guests = 3 WHERE id = 1")
    tables = ("users", "listings", "bookings", "payments", "itineraries",
              "itinerary_items", "activity_log", "notifications")
    before = {t: store.find_all(f"SELECT * FROM {t}") for t in tables}
    seed_sample_data(store)
    assert before == {t: store.find_all(f"SELECT * FROM {t}") for t in tables}


def test_notification_crud_and_persistence(store):
    user = store.find_one("SELECT id FROM users WHERE role = 'tourist'")
    row_id = store.execute(
        "INSERT INTO notifications (user_id, message) VALUES (?, ?)",
        (user["id"], "Test notification"))
    assert store.find_one("SELECT message FROM notifications WHERE id = ?",
                          (row_id,))["message"] == "Test notification"
    store.execute("UPDATE notifications SET message = ? WHERE id = ?",
                  ("Changed", row_id))
    assert store.find_one("SELECT message FROM notifications WHERE id = ?",
                          (row_id,))["message"] == "Changed"
    store.execute("DELETE FROM notifications WHERE id = ?", (row_id,))
    assert store.find_one("SELECT id FROM notifications WHERE id = ?",
                          (row_id,)) is None


@pytest.mark.parametrize("sql", [
    "UPDATE bookings SET tourist_id = -1",
    "UPDATE bookings SET listing_id = -1",
    "UPDATE payments SET booking_id = -1",
    "UPDATE itineraries SET tourist_id = -1",
    "UPDATE itinerary_items SET itinerary_id = -1",
    "UPDATE itinerary_items SET listing_id = -1",
    "UPDATE activity_log SET user_id = -1",
    "UPDATE notifications SET user_id = -1",
    "UPDATE bookings SET guests = 0",
    "UPDATE notifications SET message = NULL",
])
def test_invalid_data_rejected(store, sql):
    with pytest.raises(sqlite3.IntegrityError):
        store.execute(sql)
    assert store.find_all("PRAGMA foreign_key_check") == []


def test_itinerary_delete_cascades(store):
    itinerary = store.find_one("SELECT id FROM itineraries")
    store.execute("DELETE FROM itineraries WHERE id = ?", (itinerary["id"],))
    assert store.find_all("SELECT * FROM itinerary_items") == []
    assert len(store.find_all("SELECT * FROM listings")) == 5


def test_booking_with_payment_cannot_be_deleted(store):
    payment = store.find_one("SELECT booking_id FROM payments")
    with pytest.raises(sqlite3.IntegrityError):
        store.execute("DELETE FROM bookings WHERE id = ?",
                      (payment["booking_id"],))


def test_transaction_commits_and_closes(store):
    with store.transaction() as connection:
        connection.execute("UPDATE bookings SET guests = 3 WHERE id = 1")
        connection.execute("UPDATE bookings SET guests = 4 WHERE id = 2")
        assert connection.execute(
            "SELECT guests FROM bookings WHERE id = 1").fetchone()[0] == 3
        assert store.find_one(
            "SELECT guests FROM bookings WHERE id = 1")["guests"] != 3
    assert store.find_one(
        "SELECT guests FROM bookings WHERE id = 1")["guests"] == 3
    assert store.find_one(
        "SELECT guests FROM bookings WHERE id = 2")["guests"] == 4
    with pytest.raises(sqlite3.ProgrammingError):
        connection.execute("SELECT 1")


@pytest.mark.parametrize("sql_error", [True, False])
def test_transaction_rolls_back_and_closes(store, sql_error):
    before = store.find_all("SELECT * FROM bookings ORDER BY id")
    error = sqlite3.IntegrityError if sql_error else ValueError
    with pytest.raises(error):
        with store.transaction() as connection:
            connection.execute("UPDATE bookings SET guests = 3 WHERE id = 1")
            if sql_error:
                connection.execute("UPDATE bookings SET tourist_id = -1")
            else:
                raise ValueError("Cancel operation")
    assert store.find_all("SELECT * FROM bookings ORDER BY id") == before
    with pytest.raises(sqlite3.ProgrammingError):
        connection.execute("SELECT 1")
