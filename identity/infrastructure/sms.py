"""
Infrastructure adapter for sending SMS.
'console' backend just logs the code (no server yet). Swap to a real provider later
without touching the application layer.
"""
from __future__ import annotations

import logging

from django.conf import settings

logger = logging.getLogger("identity.sms")


class BaseSmsBackend:
    def send(self, mobile: str, message: str) -> None:  # pragma: no cover - interface
        raise NotImplementedError


class ConsoleSmsBackend(BaseSmsBackend):
    def send(self, mobile: str, message: str) -> None:
        logger.warning("[SMS→%s] %s", mobile, message)
        print(f"\n[SMS→{mobile}] {message}\n")


def get_sms_backend() -> BaseSmsBackend:
    backend = getattr(settings, "SMS_BACKEND", "console")
    # extend with real providers (e.g. Kavenegar/Faraz) here:
    return ConsoleSmsBackend()


def send_otp_sms(mobile: str, code: str) -> None:
    get_sms_backend().send(mobile, f"کد ورود شما به سامانه رفاهیات: {code}")
