"""Tests for the OTP login flow."""
from unittest.mock import patch

import pytest

pytestmark = pytest.mark.django_db

REQ = "/api/v1/auth/otp/request"
VERIFY = "/api/v1/auth/otp/verify"
GEN = "identity.application.services.generate_numeric_code"


def test_request_invalid_mobile(api_client):
    r = api_client.post(REQ, {"mobile": "123"}, format="json")
    assert r.status_code == 400


def test_request_and_verify_existing_user(api_client, make_user):
    make_user(mobile="09121112233")
    with patch(GEN, return_value="654321"):
        r1 = api_client.post(REQ, {"mobile": "09121112233"}, format="json")
    assert r1.status_code == 200
    r2 = api_client.post(VERIFY, {"mobile": "09121112233", "code": "654321"}, format="json")
    assert r2.status_code == 200
    assert "access" in r2.data and "refresh" in r2.data
    assert r2.data["user"]["mobile"] == "09121112233"


def test_verify_unknown_user_forbidden(api_client):
    with patch(GEN, return_value="111111"):
        api_client.post(REQ, {"mobile": "09127778899"}, format="json")
    r = api_client.post(VERIFY, {"mobile": "09127778899", "code": "111111"}, format="json")
    assert r.status_code == 403


def test_verify_wrong_code(api_client, make_user):
    make_user(mobile="09121110000")
    with patch(GEN, return_value="222222"):
        api_client.post(REQ, {"mobile": "09121110000"}, format="json")
    r = api_client.post(VERIFY, {"mobile": "09121110000", "code": "000000"}, format="json")
    assert r.status_code == 400


def test_rate_limit_cooldown(api_client, make_user):
    make_user(mobile="09121114444")
    with patch(GEN, return_value="333333"):
        r1 = api_client.post(REQ, {"mobile": "09121114444"}, format="json")
        r2 = api_client.post(REQ, {"mobile": "09121114444"}, format="json")
    assert r1.status_code == 200
    assert r2.status_code == 429
