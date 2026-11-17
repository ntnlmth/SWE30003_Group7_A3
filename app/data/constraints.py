"""Install booking and payment constraints without rebuilding tables."""

import sqlite3

RULES = {
    "bookings": (
        "status IN ('pending', 'confirmed', 'cancelled') "
        "AND check_out > check_in"
    ),
    "payments": (
        "status IN ('success', 'failed', 'pending') "
        "AND typeof(amount) IN ('integer', 'real') AND amount >= 0"
    ),
}


def install_constraints(connection):
    """Validate existing data and atomically install insert/update guards."""
    with connection:
        connection.execute("BEGIN IMMEDIATE")
        for table, rule in RULES.items():
            invalid = connection.execute(
                f"SELECT id FROM {table} WHERE NOT ({rule})"
            ).fetchall()
            if invalid:
                ids = [row[0] for row in invalid]
                raise sqlite3.IntegrityError(
                    f"Cannot install constraints: invalid {table} IDs {ids}")
            for operation in ("INSERT", "UPDATE"):
                connection.execute(f"""
                    CREATE TRIGGER IF NOT EXISTS {table}_validate_{operation}
                    AFTER {operation} ON {table}
                    WHEN EXISTS (
                        SELECT 1 FROM {table}
                        WHERE id = NEW.id AND NOT ({rule})
                    )
                    BEGIN
                        SELECT RAISE(ABORT, 'Invalid {table} values');
                    END
                """)
