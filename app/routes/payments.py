"""Area: Pay for a booking (owner: Zaferah).

Screens for a tourist to see what they owe, pay for a pending booking
with a (simulated) card payment and view the receipt. As in the other
areas, the route handlers only read the request, call PaymentManager
and show the outcome; every rule lives in PaymentManager.
"""

from flask import (Blueprint, current_app, flash, g, redirect,
                   render_template, request, url_for)

from app.controllers.payment_manager import (BookingNotFound, CannotPay,
                                             InvalidCard, NotAllowed,
                                             PaymentDeclined, PaymentManager,
                                             PaymentNotFound)
from app.data.data_store import DataStore
from app.services.authenticator import sign_in_required

blueprint = Blueprint("payments", __name__, url_prefix="/payments")


@blueprint.record_once
def create_payment_services(state):
    """Bootstrap step: create this area's controller with the app."""
    state.app.extensions["payment_manager"] = PaymentManager(
        DataStore.get_instance())


def get_payment_manager():
    """Return the application's PaymentManager."""
    return current_app.extensions["payment_manager"]


@blueprint.route("/")
@sign_in_required("tourist")
def index():
    """Show bookings awaiting payment, past payments and notifications."""
    manager = get_payment_manager()
    return render_template(
        "payments/index.html",
        unpaid=manager.list_unpaid(g.user),
        payments=manager.list_payments(g.user),
        notifications=manager.recent_notifications(g.user))


@blueprint.route("/booking/<int:booking_id>", methods=["GET", "POST"])
@sign_in_required("tourist")
def pay(booking_id):
    """Show the payment form for one booking and take the payment."""
    manager = get_payment_manager()
    try:
        payable = manager.get_payable_booking(g.user, booking_id)
    except (NotAllowed, BookingNotFound, CannotPay) as error:
        flash(str(error), "error")
        return redirect(url_for("payments.index"))

    # Only the name is sent back to the form after an error; the card
    # number and security code are never echoed into the page.
    form = {"holder_name": g.user.name}
    errors, declined = {}, None
    if request.method == "POST":
        form = {"holder_name": request.form.get("holder_name", ""),
                "expiry": request.form.get("expiry", "")}
        try:
            payment = manager.pay(g.user, booking_id, request.form)
        except (NotAllowed, BookingNotFound, CannotPay) as error:
            flash(str(error), "error")
            return redirect(url_for("payments.index"))
        except InvalidCard as error:
            errors = error.errors
        except PaymentDeclined as error:
            declined = str(error)
        else:
            flash("Payment successful. Your booking is confirmed.",
                  "success")
            return redirect(url_for(
                "payments.receipt", payment_id=payment.payment_id))
    return render_template(
        "payments/pay.html", payable=payable, form=form, errors=errors,
        declined=declined)


@blueprint.route("/<int:payment_id>/receipt")
@sign_in_required("tourist")
def receipt(payment_id):
    """Show the receipt for one of this tourist's successful payments."""
    try:
        view = get_payment_manager().get_receipt(g.user, payment_id)
    except PaymentNotFound as error:
        flash(str(error), "error")
        return redirect(url_for("payments.index"))
    return render_template("payments/receipt.html", view=view)
