"""SystemController: starts the system and routes requests.

In the detailed design, SystemController is the Flask application
factory. It runs the bootstrap sequence (Section 2.5 of the report):
open DataStore, create the schema and sample data, create the shared
services, then register one route module per area.
"""

import os
from datetime import timedelta

from flask import Flask

from app.data.data_store import DataStore
from app.data.seed import seed_sample_data, seed_users_and_listings
from app.routes import auth, bookings, itineraries, listings, main, payments
from app.services.authenticator import Authenticator


def create_app(config=None):
    """Create and configure the application.

    Args:
        config: Optional mapping of settings that override the defaults,
            used by the tests to point at a temporary database.

    Returns:
        The configured Flask application.
    """
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_mapping(
        SECRET_KEY=os.environ.get("STIS_SECRET_KEY", "dev-only-change-me"),
        DATABASE=os.path.join(app.instance_path, "stis.db"),
        SEED_SAMPLE_DATA=True,
        SEED_DEMO_DATA=True,
        SESSION_TIMEOUT_MINUTES=30,
    )
    if config:
        app.config.update(config)
    # The browser drops the cookie when the idle limit passes as well;
    # Authenticator enforces the same limit on the server (S4).
    app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(
        minutes=app.config["SESSION_TIMEOUT_MINUTES"])
    os.makedirs(app.instance_path, exist_ok=True)

    # Bootstrap step 1: the single DataStore and its schema.
    store = DataStore.get_instance(app.config["DATABASE"])
    store.create_schema()
    if app.config["SEED_SAMPLE_DATA"]:
        if app.config["SEED_DEMO_DATA"]:
            seed_sample_data(store)
        else:
            seed_users_and_listings(store)

    # Bootstrap step 2: shared services.
    app.extensions["authenticator"] = Authenticator(store)

    # Bootstrap step 3: one route module per area.
    for module in (main, auth, bookings, payments, itineraries, listings):
        app.register_blueprint(module.blueprint)

    return app
