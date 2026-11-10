# Sarawak Tourism Information System (SWE30003 Assignment 3, Group 7)

A Flask web application implementing four areas of the Assignment 2
design: search and book accommodation, pay for a booking (simulated),
plan an itinerary, and manage listings.

## Requirements

- Python 3.12 or later

## Setting up

```bash
python -m venv venv
# Windows
venv\Scripts\activate
# macOS / Linux
source venv/bin/activate

pip install -r requirements-dev.txt
```

## Running

```bash
python run.py
```

Open http://127.0.0.1:5000 in a browser. The database
(`instance/stis.db`) and sample data are created on first start.
To start again with fresh data, stop the server and delete
`instance/stis.db`. Stop the server with Ctrl+C.

### Sample accounts

All sample accounts use the password `Password1!`.

| Role     | Email                  |
|----------|------------------------|
| Tourist  | tourist@example.com    |
| Operator | operator@example.com   |
| Operator | operator2@example.com  |
| Admin    | admin@example.com      |

## Checks

```bash
python -m compileall app     # compilation evidence
flake8                       # PEP 8 coding standard
pytest                       # automated tests
```

## Project structure

| Folder          | Contents                                        |
|-----------------|-------------------------------------------------|
| `app/models`    | Entity classes (User, Listing, Booking, ...)     |
| `app/controllers` | Workflow controllers (BookingManager, ...)    |
| `app/services`  | Shared services (Authenticator, Notifier, ...)   |
| `app/data`      | DataStore, schema and sample data                |
| `app/routes`    | One route module per area (UI boundary)          |
| `app/templates` | HTML screens                                     |
| `tests`         | Automated tests                                  |

## Who owns what

| Area / part                         | Owner   | Route module            |
|-------------------------------------|---------|-------------------------|
| Sign-in, app setup, DataStore       | Nathan  | `auth.py`, `main.py`    |
| Search and book accommodation       | Badrul  | `bookings.py`           |
| Pay for a booking                   | Zaferah | `payments.py`           |
| Plan an itinerary                   | Rukman  | `itineraries.py`        |
| Manage listings                     | Anisa   | `listings.py`           |
| Database, run instructions, checks  | Ivan    | `app/data`, `tests`     |

## Coding standard

PEP 8 (https://peps.python.org/pep-0008/) with PEP 257 docstrings
(https://peps.python.org/pep-0257/), checked with flake8. Every public
class and function has a docstring naming the responsibility it
implements. Route handlers contain no business rules.

## Working together

1. Create a branch for your area: `git checkout -b area/bookings`.
2. Commit small, working steps.
3. Run `flake8` and `pytest` before pushing.
4. Open a pull request and ask one other member to review it.
