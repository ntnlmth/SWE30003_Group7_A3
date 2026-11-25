"""Tests for the Plan an itinerary screens (Scenario 3)."""

import re
from datetime import date, timedelta

import pytest

from app import create_app
from app.data.data_store import DataStore
from app.services.activity_log import ActivityLog


@pytest.fixture
def app(tmp_path, isolated_store):
    """Use sample users and listings without demo itineraries."""
    return create_app({
        "TESTING": True,
        "DATABASE": str(tmp_path / "itinerary-routes.db"),
        "SECRET_KEY": "test",
        "SEED_DEMO_DATA": False,
    })


def page(response):
    """Return the response body as text."""
    return response.get_data(as_text=True)


def trip_dates():
    """Return a valid future start and end date as ISO text."""
    start = date.today() + timedelta(days=7)
    return start.isoformat(), (start + timedelta(days=2)).isoformat()


def hotel_id():
    """Return the id of a sample listing that has no opening hours."""
    return DataStore.get_instance().find_one(
        "SELECT id FROM listings WHERE name = ?",
        ("Riverside Kuching Hotel",))["id"]


def create_trip(client, title="Kuching trip"):
    """Create an itinerary through the screen and return its id."""
    start, end = trip_dates()
    response = client.post("/itineraries/new", data={
        "title": title, "start_date": start, "end_date": end})
    return int(re.search(r"/itineraries/(\d+)",
                         response.headers["Location"]).group(1))


def item_form(**changes):
    """Return valid form data for an itinerary item."""
    form = {"listing_id": str(hotel_id()), "day": trip_dates()[0],
            "start_time": "09:00", "end_time": "11:00"}
    form.update(changes)
    return form


def item_ids(client, itinerary_id):
    """Return the ids of the items shown on an itinerary's screen."""
    text = page(client.get(f"/itineraries/{itinerary_id}"))
    return sorted(set(re.findall(
        rf"/itineraries/{itinerary_id}/items/(\d+)/", text)))


# ---------------------------------------------------------------- access

def test_signed_out_user_is_sent_to_sign_in(client):
    """The itinerary screens need a signed-in tourist."""
    response = client.get("/itineraries/")
    assert response.status_code == 302
    assert "/auth/sign-in" in response.headers["Location"]


def test_operator_cannot_open_the_itinerary_screens(client, sign_in):
    """Only tourists plan itineraries."""
    sign_in("operator@example.com")
    response = client.get("/itineraries/", follow_redirects=True)
    assert "You do not have access to that page." in page(response)


def test_tourist_cannot_open_another_tourists_itinerary(client, sign_in):
    """An itinerary belongs to the tourist who created it."""
    sign_in("tourist@example.com")
    itinerary_id = create_trip(client)
    client.post("/auth/sign-out")
    client.post("/auth/register", data={
        "name": "Other Tourist", "email": "other@example.com",
        "password": "Password1!", "role": "tourist"})
    response = client.get(f"/itineraries/{itinerary_id}",
                          follow_redirects=True)
    assert "You may access only your own itineraries." in page(response)


# ------------------------------------------------------------ itineraries

def test_correct_input_creates_an_itinerary(client, sign_in):
    """A valid title and date range creates the itinerary."""
    sign_in("tourist@example.com")
    itinerary_id = create_trip(client)
    text = page(client.get(f"/itineraries/{itinerary_id}"))
    assert "has been created" in text
    assert "Kuching trip" in text


def test_rejected_itinerary_shows_each_error(client, sign_in):
    """A blank title and a reversed date range are both reported."""
    sign_in("tourist@example.com")
    start, end = trip_dates()
    response = client.post("/itineraries/new", data={
        "title": "", "start_date": end, "end_date": start})
    text = page(response)
    assert response.status_code == 200
    assert "Title cannot be blank." in text
    assert "End date must be on or after start date." in text


def test_itinerary_can_be_renamed_and_deleted(client, sign_in):
    """A tourist who changes their mind can edit or delete the plan."""
    sign_in("tourist@example.com")
    itinerary_id = create_trip(client)
    start, end = trip_dates()
    response = client.post(f"/itineraries/{itinerary_id}/edit", data={
        "title": "Bako weekend", "start_date": start, "end_date": end},
        follow_redirects=True)
    assert "Bako weekend" in page(response)
    response = client.post(f"/itineraries/{itinerary_id}/delete",
                           follow_redirects=True)
    assert "Itinerary deleted." in page(response)
    assert "Bako weekend" not in page(response)


# ------------------------------------------------------------------ items

def test_activity_can_be_added_moved_and_removed(client, sign_in):
    """Items can be added, then moved or removed on a change of mind."""
    sign_in("tourist@example.com")
    itinerary_id = create_trip(client)
    response = client.post(f"/itineraries/{itinerary_id}/items/new",
                           data=item_form(), follow_redirects=True)
    assert "Activity added to the itinerary." in page(response)
    (item_id,) = item_ids(client, itinerary_id)
    response = client.post(
        f"/itineraries/{itinerary_id}/items/{item_id}/edit",
        data=item_form(start_time="13:00", end_time="15:00"),
        follow_redirects=True)
    assert "Activity updated." in page(response)
    response = client.post(
        f"/itineraries/{itinerary_id}/items/{item_id}/delete",
        follow_redirects=True)
    assert "Activity removed." in page(response)
    assert item_ids(client, itinerary_id) == []


def test_overlapping_activity_is_rejected_as_a_clash(client, sign_in):
    """Scheduler refuses a time slot that overlaps a planned one."""
    sign_in("tourist@example.com")
    itinerary_id = create_trip(client)
    client.post(f"/itineraries/{itinerary_id}/items/new", data=item_form())
    response = client.post(
        f"/itineraries/{itinerary_id}/items/new",
        data=item_form(start_time="10:00", end_time="12:00"))
    assert "This time overlaps another planned activity." in page(response)
    assert len(item_ids(client, itinerary_id)) == 1


def test_rejected_activity_shows_each_error(client, sign_in):
    """A day outside the trip and a reversed time are both reported."""
    sign_in("tourist@example.com")
    itinerary_id = create_trip(client)
    outside = (date.today() + timedelta(days=30)).isoformat()
    response = client.post(
        f"/itineraries/{itinerary_id}/items/new",
        data=item_form(day=outside, start_time="12:00", end_time="10:00"))
    text = page(response)
    assert "The day must be within the itinerary date range." in text
    assert "End time must be after start time." in text


# ------------------------------------------------------------ audit trail

def test_itinerary_changes_are_recorded_by_the_activity_log(
        client, sign_in):
    """Creating an itinerary leaves an entry the ActivityLog can read."""
    sign_in("tourist@example.com")
    create_trip(client)
    store = DataStore.get_instance()
    tourist = store.find_one(
        "SELECT id FROM users WHERE email = 'tourist@example.com'")
    entries = ActivityLog(store).entries_for(tourist["id"])
    assert entries[0]["action"] == "itinerary.created"
    assert entries[0]["item"].startswith("Kuching trip")
