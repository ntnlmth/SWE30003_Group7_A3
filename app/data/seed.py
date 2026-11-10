"""Sample data so every area can be tested without typing it in."""

from werkzeug.security import generate_password_hash

SAMPLE_PASSWORD = "Password1!"

SAMPLE_USERS = [
    ("tourist", "Tasha Tourist", "tourist@example.com"),
    ("operator", "Omar Operator", "operator@example.com"),
    ("operator", "Olivia Operator", "operator2@example.com"),
    ("admin", "Aisha Admin", "admin@example.com"),
]

SAMPLE_LISTINGS = [
    # type, operator email, name, location, price, phone, open, close, rooms
    ("accommodation", "operator@example.com", "Riverside Kuching Hotel",
     "Kuching", 220.0, "082-123456", None, None, 20),
    ("accommodation", "operator@example.com", "Damai Beach Resort",
     "Santubong", 380.0, "082-234567", None, None, 12),
    ("accommodation", "operator2@example.com", "Miri City Inn",
     "Miri", 150.0, "085-345678", None, None, 30),
    ("dining", "operator2@example.com", "Top Spot Food Court",
     "Kuching", 25.0, "082-456789", "17:00", "23:00", None),
    ("attraction", None, "Sarawak Cultural Village",
     "Santubong", 95.0, "082-567890", "09:00", "17:00", None),
]


def seed_sample_data(store):
    """Insert the sample users and listings if the database is empty."""
    if store.find_one("SELECT id FROM users LIMIT 1") is not None:
        return
    for role, name, email in SAMPLE_USERS:
        store.execute(
            "INSERT INTO users (role, name, email, password_hash) "
            "VALUES (?, ?, ?, ?)",
            (role, name, email, generate_password_hash(SAMPLE_PASSWORD)),
        )
    for (listing_type, operator_email, name, location, price, phone,
         opening, closing, rooms) in SAMPLE_LISTINGS:
        operator = None
        if operator_email is not None:
            operator = store.find_one(
                "SELECT id FROM users WHERE email = ?", (operator_email,))
        store.execute(
            "INSERT INTO listings (listing_type, operator_id, name, "
            "location, price, contact_phone, opening_time, closing_time, "
            "room_count) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (listing_type, operator["id"] if operator else None, name,
             location, price, phone, opening, closing, rooms),
        )
