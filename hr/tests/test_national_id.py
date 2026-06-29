"""Unit tests for the NationalId value object (no DB)."""
import pytest

from hr.domain.value_objects import InvalidNationalIdError, NationalId


def _valid(first9):
    check = sum(int(first9[i]) * (10 - i) for i in range(9)) % 11
    ctrl = check if check < 2 else 11 - check
    return first9 + str(ctrl)


def test_valid_national_id():
    nid = _valid("123456780")
    assert NationalId.parse(nid).value == nid


def test_all_same_digits_invalid():
    with pytest.raises(InvalidNationalIdError):
        NationalId.parse("1111111111")


def test_non_digit_invalid():
    with pytest.raises(InvalidNationalIdError):
        NationalId.parse("12345abcde")


def test_wrong_control_digit_invalid():
    nid = _valid("123456780")
    wrong = nid[:9] + str((int(nid[9]) + 1) % 10)
    with pytest.raises(InvalidNationalIdError):
        NationalId.parse(wrong)
