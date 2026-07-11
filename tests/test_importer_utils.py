from importers.utils import parse_float


def test_parse_float_accepts_authorized_buyers_currency_symbols():
    assert parse_float("$1,234.56") == 1234.56
    assert parse_float("€1,234.56") == 1234.56
    assert parse_float("1,234.56 €") == 1234.56
    assert parse_float("£1,234.56") == 1234.56


def test_parse_float_preserves_empty_and_invalid_defaults():
    assert parse_float("", default=None) is None
    assert parse_float("not-a-number", default=None) is None
