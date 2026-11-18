"""Tests for DataValidator (CRC card 5.22)."""

import pytest

from app.data.data_store import DataStore
from app.services.data_validator import DataValidator


@pytest.fixture
def validator(app):
    """Return a DataValidator on the test app's database."""
    return DataValidator(DataStore.get_instance())


def good_form(**changes):
    """Return a valid accommodation form, with ``changes`` applied."""
    form = {
        "name": "Bako Lodge", "location": "Bako", "description": "Quiet.",
        "price": "180", "contact_phone": "082-555123", "room_count": "10",
        "opening_time": "", "closing_time": "",
    }
    form.update(changes)
    return form


def test_valid_accommodation_has_no_errors(validator):
    """A complete, correct form passes."""
    assert validator.validate("accommodation", good_form()) == {}


def test_blank_required_fields_are_each_reported(validator):
    """Every blank mandatory field gets its own message."""
    errors = validator.validate("accommodation", good_form(
        name="", location=" ", price="", contact_phone="",
        room_count=""))
    assert errors["name"] == "Name cannot be blank."
    assert errors["location"] == "Location cannot be blank."
    assert errors["price"] == "Price cannot be blank."
    assert errors["contact_phone"] == "Phone number cannot be blank."
    assert errors["room_count"] == "Number of rooms cannot be blank."


@pytest.mark.parametrize("price", ["abc", "-5"])
def test_price_must_be_a_number_of_zero_or_more(validator, price):
    """A non-number or a negative price is refused."""
    errors = validator.validate("accommodation", good_form(price=price))
    assert "price" in errors


def test_phone_format_is_checked(validator):
    """Letters in a phone number are refused."""
    errors = validator.validate(
        "accommodation", good_form(contact_phone="call me"))
    assert "valid phone number" in errors["contact_phone"]


@pytest.mark.parametrize("rooms", ["0", "2.5", "many"])
def test_room_count_must_be_a_whole_number_of_one_or_more(
        validator, rooms):
    """Accommodation needs a whole number of rooms."""
    errors = validator.validate("accommodation", good_form(room_count=rooms))
    assert "room_count" in errors


def test_name_length_is_limited(validator):
    """A name over 100 characters is refused."""
    errors = validator.validate("accommodation", good_form(name="x" * 101))
    assert "at most 100" in errors["name"]


def test_attraction_needs_valid_opening_hours(validator):
    """Attractions and dining outlets must give opening and closing times."""
    form = good_form(opening_time="9am", closing_time="")
    errors = validator.validate("attraction", form)
    assert "HH:MM" in errors["opening_time"]
    assert "HH:MM" in errors["closing_time"]


def test_closing_time_must_be_after_opening_time(validator):
    """Date and time logic: closing cannot be before opening."""
    form = good_form(opening_time="17:00", closing_time="09:00")
    errors = validator.validate("dining", form)
    assert errors["closing_time"] == (
        "Closing time must be after the opening time.")


def test_valid_attraction_passes_without_rooms(validator):
    """Room count is only required for accommodation."""
    form = good_form(opening_time="09:00", closing_time="17:00",
                     room_count="")
    assert validator.validate("attraction", form) == {}


def test_unknown_listing_type_is_refused(validator):
    """Only the manageable types are accepted."""
    errors = validator.validate("spaceship", good_form())
    assert errors == {"listing_type": "Choose a listing type."}


def test_duplicate_is_found_ignoring_case_and_spaces(validator):
    """The same name and location of the same type is a likely duplicate."""
    match = validator.find_possible_duplicate(
        "accommodation", "  riverside kuching hotel ", "KUCHING")
    assert match is not None
    assert match["name"] == "Riverside Kuching Hotel"


def test_same_name_in_another_place_is_not_a_duplicate(validator):
    """A different location means a different listing."""
    assert validator.find_possible_duplicate(
        "accommodation", "Riverside Kuching Hotel", "Miri") is None


def test_editing_a_listing_does_not_clash_with_itself(validator):
    """The listing being edited is left out of the duplicate check."""
    own = validator.find_possible_duplicate(
        "accommodation", "Riverside Kuching Hotel", "Kuching")
    assert validator.find_possible_duplicate(
        "accommodation", "Riverside Kuching Hotel", "Kuching",
        exclude_id=own["id"]) is None
