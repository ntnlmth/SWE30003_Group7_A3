"""The payment gateway, reached only through an «Adapter».

Implements the Adapter pattern from Assignment 2 (Section 6.3):

* ``SimulatedPaymentGateway`` stands in for a third-party gateway. Like
  a real one, it has its own interface: amounts in whole cents, a
  dict-shaped request and a dict-shaped reply with its own field names.
* ``PaymentGatewayAdapter`` is the one interface the rest of the system
  uses: ``charge(amount, card)`` with ringgit amounts, returning a
  ``GatewayResult``. It translates between the two.

Replacing the simulation with a real gateway later means writing a new
adapter for that gateway's interface; PaymentManager does not change.

No real money moves and nothing leaves the application. The simulated
gateway decides the outcome from the card number, using test numbers in
the style real gateways publish for testing:

* ``4000 0000 0000 0002`` is always declined ("card declined");
* ``4000 0000 0000 9995`` is always declined ("insufficient funds");
* any other card that passed validation is approved.
"""

from dataclasses import dataclass
from itertools import count

DECLINED_CARD = "4000000000000002"
NO_FUNDS_CARD = "4000000000009995"


@dataclass(frozen=True)
class CardDetails:
    """Card details for one charge. Never saved to the database."""

    holder_name: str
    number: str
    expiry_month: int
    expiry_year: int
    cvv: str

    @property
    def last_four(self):
        """Return the last four digits, the only part safe to show."""
        return self.number[-4:]


@dataclass(frozen=True)
class GatewayResult:
    """The system's view of a gateway reply."""

    approved: bool
    reference: str
    message: str


class SimulatedPaymentGateway:
    """A stand-in for an external payment gateway (the «Adaptee»)."""

    def __init__(self):
        """Create a gateway that numbers its transactions from 1."""
        self._next_number = count(1)

    def submit_transaction(self, request):
        """Process one transaction request and return the reply.

        Args:
            request: Dict with ``amount_cents``, ``currency``, ``pan``
                (card number), ``exp`` (``MM/YY``) and ``cvc``.

        Returns:
            Dict with ``status`` (``"APPROVED"`` or ``"DECLINED"``),
            ``txn_id`` and, when declined, ``decline_reason``.
        """
        txn_id = f"SIM-{next(self._next_number):06d}"
        if request["pan"] == DECLINED_CARD:
            return {"status": "DECLINED", "txn_id": txn_id,
                    "decline_reason": "card_declined"}
        if request["pan"] == NO_FUNDS_CARD:
            return {"status": "DECLINED", "txn_id": txn_id,
                    "decline_reason": "insufficient_funds"}
        return {"status": "APPROVED", "txn_id": txn_id}


class PaymentGatewayAdapter:
    """Charge a card through the gateway using the system's interface."""

    DECLINE_MESSAGES = {
        "card_declined": "The card was declined by the bank.",
        "insufficient_funds": "The card has insufficient funds.",
    }

    def __init__(self, gateway=None):
        """Wrap ``gateway``; a SimulatedPaymentGateway if not given."""
        self._gateway = gateway or SimulatedPaymentGateway()

    def charge(self, amount, card):
        """Charge ``amount`` ringgit to ``card``.

        Args:
            amount: Amount in RM, such as 440.0.
            card: A CardDetails.

        Returns:
            A GatewayResult saying whether the charge was approved.
        """
        reply = self._gateway.submit_transaction({
            "amount_cents": round(amount * 100),
            "currency": "MYR",
            "pan": card.number,
            "exp": f"{card.expiry_month:02d}/{card.expiry_year % 100:02d}",
            "cvc": card.cvv,
        })
        if reply["status"] == "APPROVED":
            return GatewayResult(True, reply["txn_id"], "Payment approved.")
        reason = reply.get("decline_reason", "")
        return GatewayResult(
            False, reply["txn_id"],
            self.DECLINE_MESSAGES.get(reason, "The payment was declined."))
