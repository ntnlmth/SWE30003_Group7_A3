"""Area: Pay for a booking (owner: Zaferah).

Placeholder route so the app runs end to end. Replace the index view
with the real screens. Classes for this area: Payment,
PaymentGatewayAdapter, SimulatedPaymentGateway, Notifier, ActivityLog.
"""

from flask import Blueprint, render_template

from app.services.authenticator import sign_in_required

blueprint = Blueprint("payments", __name__, url_prefix="/payments")


@blueprint.route("/")
@sign_in_required("tourist")
def index():
    """Show the area's start screen (placeholder)."""
    return render_template(
        "placeholder.html",
        title="Pay for a booking",
        owner="Zaferah",
        classes=(
            "Payment, PaymentGatewayAdapter, "
            "SimulatedPaymentGateway, Notifier, ActivityLog"
        ),
    )
