"""DataValidator: checks listing details before anything is saved.

Implements CRC card 5.22. It only judges the data: it never saves or
changes anything. Like Authenticator.validate_registration, it returns a
dict of field errors so a form can show every problem at once.
"""

import re
from datetime import datetime

from app.services.form_validation import (check_length, check_number,
                                          first_error, require)

# Listing types an operator or admin can manage in this release.
MANAGEABLE_TYPES = ("accommodation", "attraction", "dining", "transport")
TYPES_WITH_HOURS = ("attraction", "dining")

PHONE_PATTERN = re.compile(r"^\+?[0-9][0-9\s\-()]{6,19}$")
TIME_FORMAT = "%H:%M"


def _check_phone(value):
    """Return an error if ``value`` is not a plausible phone number."""
    if not PHONE_PATTERN.match((value or "").strip()):
        return ("Enter a valid phone number, such as 082-123456 "
                "or +6082123456.")
    return None


def parse_time(value):
    """Return the time as ``HH:MM`` text, or None if it is not a time."""
    try:
        return datetime.strptime((value or "").strip(), TIME_FORMAT) \
            .strftime(TIME_FORMAT)
    except ValueError:
        return None


def _check_whole_number(value, label, minimum):
    """Return an error if ``value`` is not a whole number >= minimum."""
    try:
        number = int(str(value).strip())
    except (TypeError, ValueError):
        return f"{label} must be a whole number."
    if number < minimum:
        return f"{label} must be {minimum} or more."
    return None


class DataValidator:
    """Check listing details for completeness, format and duplicates."""

    def __init__(self, store):
        """Create a DataValidator that looks up listings in ``store``."""
        self._store = store

    def validate(self, listing_type, form):
        """Return a dict of field errors for a listing form.

        Args:
            listing_type: One of :data:`MANAGEABLE_TYPES`.
            form: Mapping of the submitted field values.

        Returns:
            A dict of field name to error message; empty when the details
            are acceptable.
        """
        errors = {}
        if listing_type not in MANAGEABLE_TYPES:
            errors["listing_type"] = "Choose a listing type."
            return errors
        self._add(errors, "name", first_error(
            require(form.get("name"), "Name"),
            check_length(form.get("name"), "Name", maximum=100)))
        self._add(errors, "location", first_error(
            require(form.get("location"), "Location"),
            check_length(form.get("location"), "Location", maximum=100)))
        self._add(errors, "description", check_length(
            form.get("description"), "Description", maximum=1000))
        self._add(errors, "price", first_error(
            require(form.get("price"), "Price"),
            check_number(form.get("price"), "Price", minimum=0)))
        self._add(errors, "contact_phone", first_error(
            require(form.get("contact_phone"), "Phone number"),
            _check_phone(form.get("contact_phone"))))
        if listing_type in TYPES_WITH_HOURS:
            self._check_hours(errors, form)
        if listing_type == "accommodation":
            self._add(errors, "room_count", first_error(
                require(form.get("room_count"), "Number of rooms"),
                _check_whole_number(form.get("room_count"),
                                    "Number of rooms", 1)))
        return errors

    def find_possible_duplicate(self, listing_type, name, location,
                                exclude_id=None):
        """Return a stored listing that looks like the same one, or None.

        A listing is a likely duplicate when another listing of the same
        type has the same name and location, ignoring case and spaces.
        ``exclude_id`` leaves out the listing being edited.
        """
        return self._store.find_one(
            "SELECT * FROM listings WHERE listing_type = ? "
            "AND lower(trim(name)) = lower(trim(?)) "
            "AND lower(trim(location)) = lower(trim(?)) "
            "AND id != ?",
            (listing_type, name or "", location or "", exclude_id or 0))

    @staticmethod
    def _add(errors, field, message):
        """Record ``message`` for ``field`` when there is one."""
        if message:
            errors[field] = message

    def _check_hours(self, errors, form):
        """Check opening and closing times, and that they make sense."""
        opening = parse_time(form.get("opening_time"))
        closing = parse_time(form.get("closing_time"))
        if opening is None:
            errors["opening_time"] = (
                "Enter the opening time as HH:MM, such as 09:00.")
        if closing is None:
            errors["closing_time"] = (
                "Enter the closing time as HH:MM, such as 17:00.")
        if opening and closing and closing <= opening:
            errors["closing_time"] = (
                "Closing time must be after the opening time.")
