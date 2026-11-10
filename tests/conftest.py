"""Shared test fixtures: an app on a temporary database."""

import pytest

from app import create_app
from app.data.seed import SAMPLE_PASSWORD


@pytest.fixture
def app(tmp_path):
    """Return an app that uses a fresh database for each test."""
    return create_app({
        "TESTING": True,
        "DATABASE": str(tmp_path / "test.db"),
        "SECRET_KEY": "test",
    })


@pytest.fixture
def client(app):
    """Return a test browser for the app."""
    return app.test_client()


@pytest.fixture
def sign_in(client):
    """Return a helper that signs in as one of the sample accounts."""
    def _sign_in(email):
        return client.post("/auth/sign-in", data={
            "email": email, "password": SAMPLE_PASSWORD})
    return _sign_in
