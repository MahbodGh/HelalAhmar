"""Domain value objects — pure Python, framework-free."""
from __future__ import annotations

import re
from dataclasses import dataclass

_IR_MOBILE_RE = re.compile(r"^09\d{9}$")


class InvalidMobileError(ValueError):
    """Raised when a mobile string is not a valid Iranian mobile number."""


@dataclass(frozen=True)
class Mobile:
    """Normalized Iranian mobile number value object."""

    value: str

    @classmethod
    def parse(cls, raw: str) -> "Mobile":
        if raw is None:
            raise InvalidMobileError("mobile is required")
        digits = (
            str(raw)
            .strip()
            .replace(" ", "")
            .replace("-", "")
        )
        # normalize +98 / 0098 -> 0
        if digits.startswith("+98"):
            digits = "0" + digits[3:]
        elif digits.startswith("0098"):
            digits = "0" + digits[4:]
        elif digits.startswith("98") and len(digits) == 12:
            digits = "0" + digits[2:]
        if not _IR_MOBILE_RE.match(digits):
            raise InvalidMobileError(f"invalid Iranian mobile: {raw}")
        return cls(digits)

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True)
class OtpPolicy:
    """OTP rules pulled from settings; passed into domain services."""

    length: int = 6
    ttl_seconds: int = 120
    max_attempts: int = 5
    resend_cooldown_seconds: int = 60
    max_per_hour: int = 5
