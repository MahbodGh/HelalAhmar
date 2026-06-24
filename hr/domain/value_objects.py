"""HR domain value objects — pure Python."""
from __future__ import annotations

from dataclasses import dataclass


class InvalidNationalIdError(ValueError):
    pass


@dataclass(frozen=True)
class NationalId:
    """Iranian national code (کد ملی) with checksum validation."""

    value: str

    @classmethod
    def parse(cls, raw: str) -> "NationalId":
        if raw is None:
            raise InvalidNationalIdError("کد ملی لازم است")
        s = str(raw).strip()
        # accept 8-10 digits by left-padding to 10 (common in legacy data)
        if not s.isdigit():
            raise InvalidNationalIdError("کد ملی باید فقط رقم باشد")
        s = s.zfill(10)
        if len(s) != 10:
            raise InvalidNationalIdError("کد ملی باید ۱۰ رقم باشد")
        if s == s[0] * 10:
            raise InvalidNationalIdError("کد ملی نامعتبر است")
        check = sum(int(s[i]) * (10 - i) for i in range(9)) % 11
        ctrl = int(s[9])
        valid = (check < 2 and ctrl == check) or (check >= 2 and ctrl == 11 - check)
        if not valid:
            raise InvalidNationalIdError("کد ملی نامعتبر است (رقم کنترلی)")
        return cls(s)

    def __str__(self) -> str:
        return self.value
