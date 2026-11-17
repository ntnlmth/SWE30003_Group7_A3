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


def _seed_users_and_listings(connection):
    """Insert missing sample users and listings, preserving existing data."""
    for role, name, email in SAMPLE_USERS:
        if connection.execute(
                "SELECT id FROM users WHERE email = ?", (email,)).fetchone():
            continue
        connection.execute(
            "INSERT INTO users (role, name, email, password_hash) "
            "VALUES (?, ?, ?, ?)",
            (role, name, email, generate_password_hash(SAMPLE_PASSWORD)),
        )
    for (listing_type, operator_email, name, location, price, phone,
         opening, closing_time, rooms) in SAMPLE_LISTINGS:
        if connection.execute(
                "SELECT id FROM listings WHERE name = ? AND listing_type = ?",
                (name, listing_type)).fetchone():
            continue
        operator = None
        if operator_email is not None:
            operator = connection.execute(
                "SELECT id FROM users WHERE email = ?",
                (operator_email,)).fetchone()
        connection.execute(
            "INSERT INTO listings (listing_type, operator_id, name, "
            "location, price, contact_phone, opening_time, closing_time, "
            "room_count) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (listing_type, operator["id"] if operator else None, name,
             location, price, phone, opening, closing_time, rooms),
        )


def seed_sample_data(store):
    """Add linked demo scenarios once, retaining existing records."""
    with store.transaction() as connection:
        _seed_users_and_listings(connection)
        tourist = connection.execute(
            "SELECT id FROM users WHERE email = ? AND role = 'tourist'",
            ("tourist@example.com",)).fetchone()
        hotel = connection.execute(
            "SELECT id, price FROM listings WHERE name = ? "
            "AND listing_type = 'accommodation'",
            ("Riverside Kuching Hotel",)).fetchone()
        attraction = connection.execute(
            "SELECT id FROM listings WHERE name = ?",
            ("Sarawak Cultural Village",)).fetchone()
        dining = connection.execute(
            "SELECT id FROM listings WHERE name = ?",
            ("Top Spot Food Court",)).fetchone()
        if not all((tourist, hotel, attraction, dining)):
            raise ValueError(
                "Demo data needs the sample tourist and listings.")

        # The audit marker prevents reseeding edited demo records.
        marker = "demo_dataset_v1"
        if connection.execute("SELECT id FROM activity_log WHERE action = ?",
                              (marker,)).fetchone():
            return
        for day, status, payment_status in (
                (1, "pending", None),
                (5, "confirmed", "success"),
                (9, "pending", "failed"),
                (13, "cancelled", None)):
            start = f"2026-12-{day:02d}"
            end = f"2026-12-{day + 2:02d}"
            amount = hotel["price"] * 2
            booking_id = connection.execute(
                "INSERT INTO bookings (tourist_id, listing_id, check_in, "
                "check_out, guests, total_price, status) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (tourist["id"], hotel["id"], start, end, 2, amount,
                 status)).lastrowid
            actions = ["booking_created"]
            if payment_status:
                connection.execute(
                    "INSERT INTO payments (booking_id, amount, status, "
                    "reference) VALUES (?, ?, ?, ?)",
                    (booking_id, amount, payment_status,
                     f"DEMO-PAY-{booking_id:04d}"))
                actions.append(f"payment_{payment_status}")
            if status == "cancelled":
                actions.append("booking_cancelled")
            for action in actions:
                connection.execute(
                    "INSERT INTO activity_log (user_id, action, item) "
                    "VALUES (?, ?, ?)",
                    (tourist["id"], action, f"booking:{booking_id}"))
            message = {
                "success": (
                    "Simulated payment successful; booking confirmed."),
                "failed": "Simulated payment failed; please retry.",
            }.get(
                payment_status,
                "Booking cancelled before payment."
                if status == "cancelled" else "Booking awaiting payment.",
            )
            connection.execute(
                "INSERT INTO notifications (user_id, message) "
                "VALUES (?, ?)",
                (tourist["id"], f"[Demo booking {booking_id}] {message}"))

        itinerary_id = connection.execute(
            "INSERT INTO itineraries (tourist_id, title, start_date, "
            "end_date) VALUES (?, ?, ?, ?)",
            (tourist["id"], "Demo: Kuching three-day trip",
             "2026-12-05", "2026-12-07")).lastrowid
        for listing_id, day, start, end in (
                (hotel["id"], "2026-12-05", "15:00", "16:00"),
                (attraction["id"], "2026-12-06", "09:00", "11:00"),
                (dining["id"], "2026-12-06", "18:00", "19:00"),
                (hotel["id"], "2026-12-07", "10:00", "11:00")):
            connection.execute(
                "INSERT INTO itinerary_items (itinerary_id, listing_id, "
                "day, start_time, end_time) VALUES (?, ?, ?, ?, ?)",
                (itinerary_id, listing_id, day, start, end))
        connection.execute(
            "INSERT INTO activity_log (user_id, action, item) "
            "VALUES (?, ?, ?)",
            (tourist["id"], "itinerary_created",
             f"itinerary:{itinerary_id}"))
        connection.execute(
            "INSERT INTO notifications (user_id, message) "
            "VALUES (?, ?)",
            (tourist["id"],
             "[Demo] Kuching three-day itinerary saved."))
        connection.execute(
            "INSERT INTO activity_log (user_id, action, item) "
            "VALUES (?, ?, ?)",
            (tourist["id"], marker,
             "Linked demonstration dataset installed"))
