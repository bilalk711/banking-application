"""Validation and exact arithmetic for amounts in one two-decimal currency."""

from decimal import Decimal, InvalidOperation, localcontext

Money = int | float | Decimal
CENT = Decimal("0.01")


def as_money(
    value: Money, *, allow_zero: bool = False, allow_negative: bool = False
) -> Decimal:
    if isinstance(value, bool) or not isinstance(value, (int, float, Decimal)):
        raise TypeError("Amount must be an int, float, or Decimal")

    amount = Decimal(str(value))
    if not amount.is_finite():
        raise ValueError("Amount must be finite")
    if not allow_negative and amount < 0:
        raise ValueError("Amount cannot be negative")
    if not allow_zero and amount == 0:
        raise ValueError("Amount must be greater than zero")

    try:
        with localcontext() as context:
            context.prec = max(28, len(amount.as_tuple().digits), amount.adjusted() + 3)
            normalized = amount.quantize(CENT)
    except InvalidOperation as error:
        raise ValueError("Amount cannot be represented as currency") from error
    if normalized != amount:
        raise ValueError("Amount must have at most two decimal places")
    return normalized


def add_money(left: Decimal, right: Decimal) -> Decimal:
    # Both operands have exponent -2. Reserve a digit for a possible carry.
    with localcontext() as context:
        context.prec = max(len(left.as_tuple().digits), len(right.as_tuple().digits)) + 1
        return left + right
