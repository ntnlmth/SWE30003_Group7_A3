"""Tests for registering, signing in and role checks."""

from app.models.user import AdminStaff, Operator, Tourist, User
from app.services.authenticator import Authenticator


def test_home_screen_shows_the_four_areas(client):
    """The home screen lists every implemented area."""
    page = client.get("/").get_data(as_text=True)
    for name in ("Search and book accommodation", "Pay for a booking",
                 "Plan an itinerary", "Manage listings"):
        assert name in page


def test_register_rejects_blank_and_invalid_fields(client):
    """Blank names, bad emails and short passwords are refused."""
    page = client.post("/auth/register", data={
        "name": "", "email": "not-an-email", "password": "short",
        "role": "tourist"}).get_data(as_text=True)
    assert "Name cannot be blank." in page
    assert "Enter a valid email address" in page
    assert "Password must be at least 8 characters." in page


def test_register_refuses_duplicate_email(client):
    """An email that already has an account cannot register again."""
    page = client.post("/auth/register", data={
        "name": "Copy", "email": "tourist@example.com",
        "password": "Password1!", "role": "tourist"}).get_data(as_text=True)
    assert "already exists" in page


def test_register_then_signed_in(client):
    """A valid registration creates the account and signs it in."""
    response = client.post("/auth/register", data={
        "name": "New Tourist", "email": "new@example.com",
        "password": "Password1!", "role": "tourist"},
        follow_redirects=True)
    assert "Welcome, New Tourist" in response.get_data(as_text=True)


def test_sign_in_with_wrong_password_is_refused(client):
    """A wrong password shows an error and does not sign in."""
    page = client.post("/auth/sign-in", data={
        "email": "tourist@example.com",
        "password": "wrong-password"}).get_data(as_text=True)
    assert "Email or password is incorrect." in page


def test_area_pages_need_sign_in(client):
    """Signed-out users are sent to the sign-in screen."""
    response = client.get("/bookings/")
    assert response.status_code == 302
    assert "/auth/sign-in" in response.headers["Location"]


def test_tourist_cannot_open_listing_management(client, sign_in):
    """Only operators and admin staff can manage listings."""
    sign_in("tourist@example.com")
    response = client.get("/listings/")
    assert response.status_code == 302


def test_operator_can_open_listing_management(client, sign_in):
    """Operators reach the listing management area."""
    sign_in("operator@example.com")
    assert client.get("/listings/").status_code == 200


def test_user_rows_become_the_right_subclass():
    """User.from_row builds Tourist, Operator or AdminStaff by role."""
    base = {"id": 1, "name": "N", "email": "e@example.com"}
    assert isinstance(User.from_row({**base, "role": "tourist"}), Tourist)
    assert isinstance(User.from_row({**base, "role": "operator"}), Operator)
    assert isinstance(User.from_row({**base, "role": "admin"}), AdminStaff)


def test_operators_may_change_only_their_own_listings():
    """Solution 1 ownership rule from Assignment 2 Scenario 5."""
    operator = Operator(2, "Omar", "operator@example.com")
    admin = AdminStaff(4, "Aisha", "admin@example.com")
    assert Authenticator.may_change_listing(operator, 2)
    assert not Authenticator.may_change_listing(operator, 3)
    assert Authenticator.may_change_listing(admin, 3)
    assert not Authenticator.may_change_listing(None, 2)
