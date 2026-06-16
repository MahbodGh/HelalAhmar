"""Domain services — pure business logic, no DB/HTTP."""
from __future__ import annotations

import secrets


def generate_numeric_code(length: int = 6) -> str:
    """Cryptographically-strong numeric OTP code (no leading-zero loss)."""
    upper = 10 ** length
    return str(secrets.randbelow(upper)).zfill(length)


def resolve_permissions(roles_with_permissions: list[dict]) -> set[str]:
    """
    Flatten a user's roles into a unique set of permission codes.

    `roles_with_permissions` is a list of dicts like:
        {"code": "hq_welfare_manager", "permissions": ["accommodation.complex.create", ...]}
    """
    perms: set[str] = set()
    for role in roles_with_permissions:
        perms.update(role.get("permissions", []))
    return perms
