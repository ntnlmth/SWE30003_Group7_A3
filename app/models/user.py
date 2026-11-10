"""User and its three subclasses: Tourist, Operator and AdminStaff.

User is new in the detailed design (report Section 2.2). It gathers the
account details and sign-in that Assignment 2 repeated on three cards.
"""

from abc import ABC, abstractmethod


class User(ABC):
    """A person with an account on the system."""

    def __init__(self, user_id, name, email):
        """Create a user from stored account details."""
        self.user_id = user_id
        self.name = name
        self.email = email

    @property
    @abstractmethod
    def role(self):
        """Return the role name stored in the users table."""

    @property
    def display_role(self):
        """Return the role as shown in the user interface."""
        return self.role.capitalize()

    @staticmethod
    def from_row(row):
        """Build the right User subclass from a users table row."""
        subclasses = {cls.ROLE: cls for cls in (Tourist, Operator, AdminStaff)}
        user_class = subclasses[row["role"]]
        return user_class(row["id"], row["name"], row["email"])


class Tourist(User):
    """A visitor who searches, books, pays and plans trips."""

    ROLE = "tourist"

    @property
    def role(self):
        """Return the stored role name."""
        return self.ROLE


class Operator(User):
    """A business that maintains its own listings (Assumption A-1)."""

    ROLE = "operator"

    @property
    def role(self):
        """Return the stored role name."""
        return self.ROLE


class AdminStaff(User):
    """Tourism Association staff who can manage any listing."""

    ROLE = "admin"

    @property
    def role(self):
        """Return the stored role name."""
        return self.ROLE

    @property
    def display_role(self):
        """Return the role as shown in the user interface."""
        return "Admin staff"
