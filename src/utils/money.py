"""Money formatting helpers for Paperite.

Money is stored in the database as INTEGER paise (1 rupee = 100 paise) and
must NEVER be held as a float, to avoid binary rounding. These helpers convert
between integer paise and human-readable Indian-rupee strings for display
only.

Formatting rules
----------------
- Always two decimal places: ``₹12.00``, ``₹12.50``, ``₹1,234.56``.
- Negative amounts are formatted with a leading minus: ``-₹3.50`` (they can
  arise for refunds/displays even though most columns are ``>= 0``).
- The Indian numbering grouping (lakhs/crores) is NOT applied to the integer
  rupee part for now: shop-level figures are small and a plain grouped
  thousands style keeps it locale-independent and predictable. This can be
  revisited in a localisation phase.
- Parsing accepts an optional leading ``₹`` and surrounding whitespace, an
  optional sign, digits, optional decimal point and one or two decimal digits.

These helpers are pure stdlib (no Qt) so they are trivially testable.
"""

from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation

RUPEE_SYMBOL = "₹"


def format_paise(paise: int) -> str:
    """Format an integer paise amount as ``"₹X.XX"`` (two decimals).

    Examples
    --------
    >>> format_paise(0)
    '₹0.00'
    >>> format_paise(1250)
    '₹12.50'
    >>> format_paise(123456)
    '₹1,234.56'
    >>> format_paise(-350)
    '-₹3.50'
    """
    if not isinstance(paise, int):
        raise TypeError(f"paise must be int, got {type(paise).__name__}")
    sign = "-" if paise < 0 else ""
    n = abs(paise)
    rupees, cents = divmod(n, 100)
    return f"{sign}{RUPEE_SYMBOL}{rupees:,}.{cents:02d}"


_PARSE_RE = re.compile(
    r"^\s*"
    r"(?P<sign>[+-])?"            # optional sign
    f"(?:{re.escape(RUPEE_SYMBOL)})?"  # optional rupee symbol
    r"\s*"
    r"(?P<rupees>\d{1,3}(?:,\d{3})*|\d+)"   # integer rupees, optional grouped
    r"(?:\.(?P<decimals>\d{1,2}))?"         # optional .dd
    r"\s*$"
)


def parse_paise(text: str) -> int:
    """Parse a rupee string into integer paise.

    Accepts ``"₹12.50"``, ``"12.50"``, ``"₹1,234"`` (no decimals), ``"12"``
    (treated as rupees -> 1200 paise), and a leading ``+``/``-``.

    Raises :class:`ValueError` with a clear message if the input is not a
    valid money string.
    """
    if not isinstance(text, str):
        raise TypeError(f"text must be str, got {type(text).__name__}")
    m = _PARSE_RE.match(text)
    if not m:
        raise ValueError(f"invalid money amount: {text!r}")

    rupees_str = m.group("rupees").replace(",", "")
    decimals = m.group("decimals") or ""
    # Pad/truncate to exactly two decimal digits -> paise.
    decimals = (decimals + "00")[:2]
    try:
        rupees = int(rupees_str)
    except ValueError as exc:  # pragma: no cover - regex guards this
        raise ValueError(f"invalid money amount: {text!r}") from exc
    paise = rupees * 100 + int(decimals)
    if m.group("sign") == "-":
        paise = -paise
    return paise


def parse_paise_or_none(text: str | None) -> int | None:
    """Parse a money string, returning ``None`` for empty/blank input.

    Useful for optional fields: blank stays blank, invalid still raises.
    """
    if text is None:
        return None
    if text.strip() == "":
        return None
    return parse_paise(text)


def money_to_decimal(paise: int) -> Decimal:
    """Return a :class:`~decimal.Decimal` rupee value for an integer paise.

    Provided for display/preview code that needs an exact decimal; never use
    floats for money.
    """
    return Decimal(paise) / Decimal(100)


__all__ = [
    "RUPEE_SYMBOL",
    "format_paise",
    "parse_paise",
    "parse_paise_or_none",
    "money_to_decimal",
]
