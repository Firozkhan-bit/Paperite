"""Tests for the paise <-> rupee string money helpers (pure stdlib)."""

import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from src.utils.money import (
    format_paise,
    money_to_decimal,
    parse_paise,
    parse_paise_or_none,
)


@pytest.mark.parametrize(
    "paise, expected",
    [
        (0, "₹0.00"),
        (1, "₹0.01"),
        (99, "₹0.99"),
        (100, "₹1.00"),
        (1250, "₹12.50"),
        (123456, "₹1,234.56"),
        (100000, "₹1,000.00"),
        (-350, "-₹3.50"),
        (-1, "-₹0.01"),
    ],
)
def test_format_paise(paise, expected):
    assert format_paise(paise) == expected


def test_format_paise_rejects_float():
    with pytest.raises(TypeError):
        format_paise(12.5)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "text, expected",
    [
        ("₹0.00", 0),
        ("₹12.50", 1250),
        ("12.50", 1250),
        ("12", 1200),            # no decimals -> whole rupees
        ("₹1,234.56", 123456),
        ("1234.56", 123456),
        ("₹1,234", 123400),
        ("  ₹10.00  ", 1000),     # whitespace tolerated
        ("-₹3.50", -350),
        ("+₹3.50", 350),
        ("₹0.5", 50),             # single decimal digit
        ("₹0.09", 9),
    ],
)
def test_parse_paise(text, expected):
    assert parse_paise(text) == expected


@pytest.mark.parametrize("text", ["", "   ", "₹", "abc", "₹12.5.6", "12,34.56", "₹.."])
def test_parse_paise_invalid(text):
    with pytest.raises(ValueError):
        parse_paise(text)


def test_parse_paise_or_none():
    assert parse_paise_or_none("") is None
    assert parse_paise_or_none(None) is None
    assert parse_paise_or_none("₹12.50") == 1250
    with pytest.raises(ValueError):
        parse_paise_or_none("nope")


def test_money_to_decimal_exact():
    assert money_to_decimal(1250) == 1250 / 100
    # exact Decimal (no float rounding); Decimal normalises trailing zeros.
    from decimal import Decimal

    assert money_to_decimal(1250) == Decimal("12.50")
    assert money_to_decimal(3) == Decimal("0.03")


def test_roundtrip_format_parse():
    for paise in [0, 1, 99, 100, 1250, 123456, 9999999]:
        assert parse_paise(format_paise(paise)) == paise
