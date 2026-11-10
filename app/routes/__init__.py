"""UI boundary: one route module (Flask blueprint) per area.

Route handlers only read input, call a controller or service, and
render the result. Business rules belong in controllers and models.
"""
