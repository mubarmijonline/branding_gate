"""Canonical state transitions for client price negotiations."""


class InvalidNegotiationTransition(ValueError):
    """Raised when an actor attempts an action outside the approved flow."""


_TRANSITIONS = {
    ("pending_sales_head", "sales_head", "approve"): "pending_pricing",
    ("pending_sales_head", "sales_head", "decline"): "sales_head_declined",
    ("pending_pricing", "pricing", "reprice"): "pricing_completed",
    ("pending_pricing", "pricing", "send_to_costing"): "pending_costing",
    ("pending_pricing", "pricing", "decline"): "pricing_declined",
    ("pending_costing", "operation", "complete_costing"): "pending_pricing",
}


def transition(current_state: str, actor: str, action: str) -> str:
    """Return the next state or reject an action that is not currently valid."""
    key = (current_state, actor, action)
    try:
        return _TRANSITIONS[key]
    except KeyError as exc:
        raise InvalidNegotiationTransition(
            f"Invalid negotiation transition: state={current_state}, "
            f"actor={actor}, action={action}"
        ) from exc
