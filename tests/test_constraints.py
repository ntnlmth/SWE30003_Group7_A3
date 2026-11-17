"""Exercise constraint guards without column-level NOT NULL protection."""

import sqlite3

import pytest

from app.data.constraints import RULES, install_constraints


@pytest.fixture
def connection():
    connection = sqlite3.connect(':memory:')
    connection.executescript('''
                             CREATE TABLE bookings
                             (
                                 id        INTEGER PRIMARY KEY,
                                 status    TEXT,
                                 check_in  TEXT,
                                 check_out TEXT
                             );
                             CREATE TABLE payments
                             (
                                 id     INTEGER PRIMARY KEY,
                                 status TEXT,
                                 amount REAL
                             );
                             INSERT INTO bookings
                             VALUES (1, 'pending', '2027-01-01', '2027-01-02');
                             INSERT INTO payments
                             VALUES (1, 'pending', 0);
                             ''')
    yield connection
    connection.close()


NULL_FIELDS = [
    ('bookings', 'status'), ('bookings', 'check_in'),
    ('bookings', 'check_out'), ('payments', 'status'), ('payments', 'amount'),
]


@pytest.mark.parametrize('table, field', NULL_FIELDS)
def test_install_rejects_existing_null(connection, table, field):
    connection.execute(f'UPDATE {table} SET {field} = NULL')
    connection.commit()
    with pytest.raises(sqlite3.IntegrityError, match=f'invalid {table} IDs'):
        install_constraints(connection)
    assert connection.execute(
        f'SELECT {field} FROM {table}').fetchone()[0] is None
    assert connection.execute(
        "SELECT name FROM sqlite_master "
        "WHERE type = 'trigger'").fetchall() == []


@pytest.mark.parametrize('table, field', NULL_FIELDS)
@pytest.mark.parametrize('operation', ['INSERT', 'UPDATE'])
def test_upgraded_guards_reject_null(connection, table, field, operation):
    for name, rule in RULES.items():
        for action in ('INSERT', 'UPDATE'):
            connection.execute(f'''
                CREATE TRIGGER {name}_validate_{action}
                AFTER {action} ON {name}
                WHEN EXISTS (SELECT 1 FROM {name}
                             WHERE id = NEW.id AND NOT ({rule}))
                BEGIN
                    SELECT RAISE(ABORT, 'Old guard');
                END
            ''')
    install_constraints(connection)
    install_constraints(connection)
    before = connection.execute(f'SELECT * FROM {table}').fetchall()
    with pytest.raises(sqlite3.IntegrityError,
                       match=f'Invalid {table} values'):
        if operation == 'UPDATE':
            connection.execute(f'UPDATE {table} SET {field} = NULL')
        else:
            fields = (['status', 'check_in', 'check_out']
                      if table == 'bookings' else ['status', 'amount'])
            values = ['NULL' if column == field else column
                      for column in fields]
            connection.execute(
                f"INSERT INTO {table} ({', '.join(fields)}) "
                f"SELECT {', '.join(values)} FROM {table}")
    assert connection.execute(f'SELECT * FROM {table}').fetchall() == before
