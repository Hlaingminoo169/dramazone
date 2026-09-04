"""
tests/test_numbers.py
======================
Unit tests for Myanmar/English number normalization.
"""

import pytest
from app.utils.numbers import myanmar_to_english, normalize_number, format_mmk


class TestMyanmarToEnglish:
    def test_single_digit(self):
        assert myanmar_to_english("၃") == "3"

    def test_multi_digit(self):
        assert myanmar_to_english("၁၀") == "10"

    def test_zero(self):
        assert myanmar_to_english("၀") == "0"

    def test_all_digits(self):
        assert myanmar_to_english("၀၁၂၃၄၅၆၇၈၉") == "0123456789"

    def test_english_passthrough(self):
        assert myanmar_to_english("123") == "123"

    def test_empty(self):
        assert myanmar_to_english("") == ""


class TestNormalizeNumber:
    # Valid Myanmar inputs
    def test_myanmar_1(self):    assert normalize_number("၁") == 1
    def test_myanmar_2(self):    assert normalize_number("၂") == 2
    def test_myanmar_3(self):    assert normalize_number("၃") == 3
    def test_myanmar_4(self):    assert normalize_number("၄") == 4
    def test_myanmar_5(self):    assert normalize_number("၅") == 5
    def test_myanmar_10(self):   assert normalize_number("၁၀") == 10
    def test_myanmar_25(self):   assert normalize_number("၂၅") == 25

    # Valid English inputs
    def test_english_1(self):    assert normalize_number("1") == 1
    def test_english_5(self):    assert normalize_number("5") == 5
    def test_english_10(self):   assert normalize_number("10") == 10
    def test_english_25(self):   assert normalize_number("25") == 25
    def test_english_100(self):  assert normalize_number("100") == 100

    # Whitespace handling
    def test_whitespace(self):   assert normalize_number("  3  ") == 3
    def test_myanmar_ws(self):   assert normalize_number(" ၃ ") == 3

    # Invalid inputs — must return None
    def test_zero(self):         assert normalize_number("0") is None
    def test_negative(self):     assert normalize_number("-1") is None
    def test_alpha(self):        assert normalize_number("abc") is None
    def test_empty(self):        assert normalize_number("") is None
    def test_none_str(self):     assert normalize_number(None) is None  # type: ignore
    def test_float_str(self):    assert normalize_number("1.5") is None
    def test_mixed(self):        assert normalize_number("1a") is None
    def test_special(self):      assert normalize_number("!@#") is None


class TestFormatMMK:
    def test_basic(self):
        assert format_mmk(1500) == "1,500 MMK"

    def test_large(self):
        assert format_mmk(1000000) == "1,000,000 MMK"

    def test_zero(self):
        assert format_mmk(0) == "0 MMK"
