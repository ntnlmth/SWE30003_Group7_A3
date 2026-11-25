"""Tests for the Manage listings screens (Scenario 4)."""

from datetime import date, timedelta

import pytest

from app import create_app
from app.data.data_store import DataStore
from app.services.activity_log import ActivityLog


@pytest.fixture
def app(tmp_path, isolated_store):
    """Use users and listings without linked demonstration records."""
    return create_app({
        "TESTING": True,
        "DATABASE": str(tmp_path / "listing-routes.db"),
        "SECRET_KEY": "test",
        "SEED_DEMO_DATA": False,
    })


def lodge_form(**changes):
    """Return valid form data for a new accommodation listing."""
    form = {
        "name": "Bako Lodge", "location": "Bako", "description": "Quiet.",
        "price": "180", "contact_phone": "082-555123", "room_count": "10",
    }
    form.update(changes)
    return form


def listing_id_named(name):
    """Return the id of the sample listing with this name."""
    return DataStore.get_instance().find_one(
        "SELECT id FROM listings WHERE name = ?", (name,))["id"]


def page(response):
    """Return the response body as text."""
    return response.get_data(as_text=True)


# ------------------------------------------------------ the list screen

def test_signed_out_user_is_sent_to_sign_in(client):
    """The listing screens need a signed-in operator or admin."""
    response = client.get("/listings/")
    assert response.status_code == 302
    assert "/auth/sign-in" in response.headers["Location"]


def test_operator_list_shows_only_own_listings(client, sign_in):
    """Omar sees his hotels and not Olivia's inn."""
    sign_in("operator@example.com")
    text = page(client.get("/listings/"))
    assert "Riverside Kuching Hotel" in text
    assert "Miri City Inn" not in text
    assert "+ Attraction" not in text


def test_admin_list_shows_all_and_can_add_attractions(client, sign_in):
    """Admin sees every listing and an Add Attraction button."""
    sign_in("admin@example.com")
    text = page(client.get("/listings/"))
    assert "Miri City Inn" in text and "Sarawak Cultural Village" in text
    assert "+ Attraction" in text


def test_filters_narrow_the_list(client, sign_in):
    """The type and search filters change what is shown."""
    sign_in("admin@example.com")
    text = page(client.get("/listings/?type=dining"))
    assert "Top Spot Food Court" in text
    assert "Miri City Inn" not in text
    text = page(client.get("/listings/?q=nothing-matches"))
    assert "No listings match" in text


# --------------------------------------------------------- adding

def test_add_form_starts_empty(client, sign_in):
    """The empty screen at the start of the scenario."""
    sign_in("operator@example.com")
    text = page(client.get("/listings/new/accommodation"))
    assert "Add a listing: accommodation" in text
    assert "Number of rooms" in text
    assert "Opening time" not in text


def test_add_listing_succeeds_and_shows_in_the_list(client, sign_in):
    """Correct input is saved and confirmed on the list screen."""
    sign_in("operator@example.com")
    response = client.post("/listings/new/accommodation",
                           data=lodge_form(), follow_redirects=True)
    text = page(response)
    assert "“Bako Lodge” has been added." in text
    assert "Bako Lodge" in text


def test_rejected_input_shows_each_error_and_keeps_the_values(
        client, sign_in):
    """Bad input is refused with field messages; typed text is kept."""
    sign_in("operator@example.com")
    text = page(client.post("/listings/new/accommodation", data=lodge_form(
        name="", price="abc", contact_phone="call me", room_count="0")))
    assert "Name cannot be blank." in text
    assert "Price must be a number." in text
    assert "Enter a valid phone number" in text
    assert "Number of rooms must be 1 or more." in text
    assert 'value="Bako"' in text
    assert "Some details need fixing" in text


def test_attraction_form_asks_for_opening_hours(client, sign_in):
    """Hours fields appear for attractions and are validated."""
    sign_in("admin@example.com")
    text = page(client.post("/listings/new/attraction", data=lodge_form(
        name="Fort Margherita", location="Kuching",
        opening_time="17:00", closing_time="09:00")))
    assert "Closing time must be after the opening time." in text


def test_duplicate_warning_then_add_anyway(client, sign_in):
    """A likely duplicate warns first and saves only when confirmed."""
    sign_in("operator@example.com")
    data = lodge_form(name="Riverside Kuching Hotel", location="Kuching")
    text = page(client.post("/listings/new/accommodation", data=data))
    assert "This looks like a listing that already exists" in text
    assert "Add anyway" in text
    confirmed = client.post(
        "/listings/new/accommodation",
        data={**data, "confirm_duplicate": "1"}, follow_redirects=True)
    assert "has been added" in page(confirmed)


def test_operator_cannot_open_the_attraction_form_action(client, sign_in):
    """Posting an attraction as an operator is refused, not saved."""
    sign_in("operator@example.com")
    response = client.post(
        "/listings/new/attraction", data=lodge_form(
            opening_time="09:00", closing_time="17:00"),
        follow_redirects=True)
    assert "You may not add that type of listing." in page(response)


def test_unknown_listing_type_is_a_404(client, sign_in):
    """Only the manageable types have a form."""
    sign_in("admin@example.com")
    assert client.get("/listings/new/spaceship").status_code == 404


# --------------------------------------------------------- editing

def test_edit_form_is_filled_with_the_saved_details(client, sign_in):
    """Editing starts from what is stored."""
    sign_in("operator@example.com")
    listing_id = listing_id_named("Riverside Kuching Hotel")
    text = page(client.get(f"/listings/{listing_id}/edit"))
    assert 'value="Riverside Kuching Hotel"' in text
    assert 'value="220.00"' in text
    assert 'value="20"' in text


def test_edit_saves_changes(client, sign_in):
    """A valid edit is saved and confirmed."""
    sign_in("operator@example.com")
    listing_id = listing_id_named("Riverside Kuching Hotel")
    response = client.post(
        f"/listings/{listing_id}/edit",
        data=lodge_form(name="Riverside Kuching Hotel",
                        location="Kuching", price="250"),
        follow_redirects=True)
    text = page(response)
    assert "has been updated" in text
    assert "250.00" in text


def test_edit_with_errors_does_not_change_the_listing(client, sign_in):
    """A refused edit leaves the stored price alone."""
    sign_in("operator@example.com")
    listing_id = listing_id_named("Riverside Kuching Hotel")
    text = page(client.post(f"/listings/{listing_id}/edit", data=lodge_form(
        name="Riverside Kuching Hotel", location="Kuching", price="-5")))
    assert "Price must be 0 or more." in text
    stored = DataStore.get_instance().find_one(
        "SELECT price FROM listings WHERE id = ?", (listing_id,))
    assert stored["price"] == 220.0


def test_operator_cannot_edit_another_operators_listing(client, sign_in):
    """The ownership rule blocks the edit screen as well."""
    sign_in("operator@example.com")
    listing_id = listing_id_named("Miri City Inn")
    response = client.get(f"/listings/{listing_id}/edit",
                          follow_redirects=True)
    assert "You may change only your own listings." in page(response)


# --------------------------------------------------------- removing

def test_remove_unreferenced_listing_asks_then_deletes(client, sign_in):
    """Nothing refers to it: confirmation says delete, then it is gone."""
    sign_in("operator@example.com")
    listing_id = listing_id_named("Damai Beach Resort")
    text = page(client.get(f"/listings/{listing_id}/remove"))
    assert "permanently deleted" in text
    response = client.post(f"/listings/{listing_id}/remove",
                           follow_redirects=True)
    assert "has been deleted" in page(response)
    assert "Damai Beach Resort" not in page(client.get("/listings/"))


def test_remove_listing_with_booking_shows_affected_then_deactivates(
        client, sign_in):
    """Variant 6a: the booking is shown, and the listing is only hidden."""
    store = DataStore.get_instance()
    listing_id = listing_id_named("Riverside Kuching Hotel")
    tourist = store.find_one(
        "SELECT id FROM users WHERE email = 'tourist@example.com'")
    check_out = (date.today() + timedelta(days=12)).isoformat()
    check_in = (date.today() + timedelta(days=10)).isoformat()
    store.execute(
        "INSERT INTO bookings (tourist_id, listing_id, check_in, "
        "check_out, guests, total_price, status) "
        "VALUES (?, ?, ?, ?, 2, 440.0, 'pending')",
        (tourist["id"], listing_id, check_in, check_out))
    sign_in("operator@example.com")
    text = page(client.get(f"/listings/{listing_id}/remove"))
    assert "cannot be deleted" in text
    assert "Tasha Tourist" in text
    response = client.post(f"/listings/{listing_id}/remove",
                           follow_redirects=True)
    text = page(response)
    assert "now hidden from tourists" in text
    assert "1 upcoming booking(s)" in text
    assert "Deactivated" in text


def test_reactivate_brings_a_hidden_listing_back(client, sign_in):
    """A change of mind: Reactivate makes the listing active again."""
    store = DataStore.get_instance()
    listing_id = listing_id_named("Riverside Kuching Hotel")
    store.execute("UPDATE listings SET is_active = 0 WHERE id = ?",
                  (listing_id,))
    sign_in("operator@example.com")
    response = client.post(f"/listings/{listing_id}/reactivate",
                           follow_redirects=True)
    assert "visible to tourists again" in page(response)


def test_removing_a_missing_listing_returns_to_the_list(client, sign_in):
    """An id that does not exist gives a message, not an error page."""
    sign_in("admin@example.com")
    response = client.get("/listings/9999/remove", follow_redirects=True)
    assert "That listing no longer exists." in page(response)


# ---------------------------------------------------------- audit trail

def test_listing_changes_are_recorded_by_the_activity_log(client, sign_in):
    """Adding a listing leaves an entry the ActivityLog can read back."""
    sign_in("operator@example.com")
    client.post("/listings/new/accommodation", data=lodge_form())
    store = DataStore.get_instance()
    operator = store.find_one(
        "SELECT id FROM users WHERE email = 'operator@example.com'")
    entries = ActivityLog(store).entries_for(operator["id"])
    assert entries[0]["action"] == "listing.created"
    assert entries[0]["item"].startswith("Bako Lodge")
