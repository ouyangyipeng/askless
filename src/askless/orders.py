"""A pure, USD order-summary adapter with explicit policy contracts."""

import json
from decimal import ROUND_HALF_UP, Context, Decimal, localcontext
from pathlib import Path
from typing import Literal, cast

from pydantic import Field, JsonValue, ValidationError

from askless.models import Model
from askless.sdk import MAX_INPUT_BYTES, Decision

ORDER_ADAPTER = "order-summary/v1"
ORDER_DECISIONS = (
    Decision("duplicates", "Which occurrence of a repeated order ID should be kept?", ("first", "last")),
    Decision("cancelled", "Should cancelled orders contribute to the summary?", ("exclude", "include")),
    Decision("rounding", "Round each order to cents, or round only the total?", ("per_order", "at_total")),
)


class Order(Model):
    order_id: str = Field(pattern=r"^[A-Za-z0-9_-]{1,64}$")
    amount: str = Field(pattern=r"^(0|[1-9][0-9]{0,8})(\.[0-9]{1,4})?$")
    status: Literal["paid", "cancelled"]


def validate_orders(data: JsonValue) -> list[Order]:
    if not isinstance(data, list) or not 1 <= len(data) <= 200:
        raise ValueError("Order input must be an array of 1–200 records.")
    try:
        return [Order.model_validate(row, strict=True) for row in data]
    except ValidationError:
        raise ValueError("Invalid order: require order_id, nonnegative decimal amount (up to four places), and paid/cancelled status.") from None


def _unique_object(pairs: list[tuple[str, JsonValue]]) -> dict[str, JsonValue]:
    result: dict[str, JsonValue] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON object keys are not accepted.")
        result[key] = value
    return result


def load_orders(path: Path) -> JsonValue:
    with path.open("rb") as source:
        raw = source.read(MAX_INPUT_BYTES + 1)
    if len(raw) > MAX_INPUT_BYTES:
        raise ValueError("Order input exceeds 512 KiB.")
    try:
        data = cast(JsonValue, json.loads(raw.decode("utf-8-sig"), object_pairs_hook=_unique_object))
    except (UnicodeError, json.JSONDecodeError):
        raise ValueError("Order input must be a UTF-8 JSON array.") from None
    validate_orders(data)
    return data


def order_profile(data: JsonValue) -> dict[str, int]:
    orders = validate_orders(data)
    with localcontext(Context(prec=28, rounding=ROUND_HALF_UP)):
        return {
            "rows": len(orders),
            "duplicate_ids": len(orders) - len({order.order_id for order in orders}),
            "cancelled_rows": sum(order.status == "cancelled" for order in orders),
            "fractional_cent_rows": sum(Decimal(order.amount) != Decimal(order.amount).quantize(Decimal("0.01")) for order in orders),
        }


def _row(index: int, order: Order) -> JsonValue:
    return {"source_row": index + 1, "order_id": order.order_id, "amount": order.amount, "status": order.status}


def preview_orders(data: JsonValue, policy: dict[str, str]) -> JsonValue:
    if set(policy) != {decision.key for decision in ORDER_DECISIONS} or any(policy[decision.key] not in decision.options for decision in ORDER_DECISIONS):
        raise ValueError("Order policy must provide exactly the declared options.")
    orders = validate_orders(data)
    # An embedding application's Decimal settings must not change order totals.
    with localcontext(Context(prec=28, rounding=ROUND_HALF_UP)):
        return _summarize(orders, policy)


def _summarize(orders: list[Order], policy: dict[str, str]) -> JsonValue:
    selected: dict[str, int] = {}
    for index, order in enumerate(orders):
        if policy["duplicates"] == "last" or order.order_id not in selected:
            selected[order.order_id] = index
    kept = set(selected.values())
    accepted: list[JsonValue] = []
    excluded: list[JsonValue] = []
    discarded: list[JsonValue] = []
    total = Decimal(0)
    for index, order in enumerate(orders):
        if index not in kept:
            discarded.append(_row(index, order))
            continue
        if policy["cancelled"] == "exclude" and order.status == "cancelled":
            excluded.append(_row(index, order))
            continue
        amount = Decimal(order.amount)
        total += amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP) if policy["rounding"] == "per_order" else amount
        accepted.append(_row(index, order))
    return {
        "currency": "USD",
        "total": str(total.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)),
        "order_count": len(accepted),
        "orders": accepted,
        "excluded_cancelled": excluded,
        "discarded_duplicates": discarded,
    }
