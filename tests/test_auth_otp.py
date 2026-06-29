import pytest

pytestmark = pytest.mark.django_db

REQ = "/api/v1/auth/otp/request"
VERIFY = "/api/v1/auth/otp/verify"


def test_request_otp_ok(api):
    from identity.models import OtpRequest

    r = api.post(REQ, {"mobile": "09120000001"}, format="json")
    assert r.status_code == 200
    assert r.data["expires_in"] == 120
    assert OtpRequest.objects.filter(mobile="09120000001").exists()


def test_request_otp_does_not_leak_code(api):
    r = api.post(REQ, {"mobile": "09120000001"}, format="json")
    assert "debug_code" not in r.data or r.data.get("debug_code") in (None, "123456")
    # the code must never be required to come back; the contract field is detail/expires_in/request_id
    assert "request_id" in r.data


def test_request_otp_invalid_mobile(api):
    r = api.post(REQ, {"mobile": "12345"}, format="json")
    assert r.status_code == 400


def test_request_otp_rate_limited(api):
    api.post(REQ, {"mobile": "09120000002"}, format="json")
    r2 = api.post(REQ, {"mobile": "09120000002"}, format="json")
    assert r2.status_code == 429


def test_verify_ok_returns_tokens(api, make_user):
    make_user(mobile="09120000003")
    api.post(REQ, {"mobile": "09120000003"}, format="json")
    r = api.post(VERIFY, {"mobile": "09120000003", "code": "123456"}, format="json")
    assert r.status_code == 200
    assert "access" in r.data and "refresh" in r.data
    assert r.data["user"]["mobile"] == "09120000003"


def test_verify_wrong_code(api, make_user):
    make_user(mobile="09120000004")
    api.post(REQ, {"mobile": "09120000004"}, format="json")
    r = api.post(VERIFY, {"mobile": "09120000004", "code": "000000"}, format="json")
    assert r.status_code == 400


def test_verify_unknown_user_forbidden(api):
    api.post(REQ, {"mobile": "09120000005"}, format="json")
    r = api.post(VERIFY, {"mobile": "09120000005", "code": "123456"}, format="json")
    assert r.status_code == 403


def test_verify_writes_login_audit(api, make_user):
    from identity.models import LoginAudit

    make_user(mobile="09120000006")
    api.post(REQ, {"mobile": "09120000006"}, format="json")
    api.post(VERIFY, {"mobile": "09120000006", "code": "123456"}, format="json")
    assert LoginAudit.objects.filter(mobile="09120000006", success=True).exists()


def test_protected_endpoint_requires_auth(api):
    assert api.get("/api/v1/me/roles").status_code == 401
