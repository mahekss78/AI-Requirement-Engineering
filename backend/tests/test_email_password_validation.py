"""
backend/tests/test_email_password_validation.py
=================================================
Automated unit tests for Email Validation, Password Policy, and OTP Email Ownership Verification.
"""

import pytest
from app.utils.email_validator import validate_email_address
from app.utils.password_validator import validate_password_strength


def test_email_validation_rules():
    # 1. Invalid syntax
    valid, msg = validate_email_address("invalid-email-format")
    assert not valid
    assert "syntax" in msg.lower()

    # 2. Disposable domain
    valid, msg = validate_email_address("user@mailinator.com")
    assert not valid
    assert "disposable" in msg.lower()

    # 3. Non-existent domain
    valid, msg = validate_email_address("driver@fake-nonexistent-domain.example")
    assert not valid
    assert "disposable" in msg.lower() or "exist" in msg.lower()

    # 4. Valid email address
    valid, msg = validate_email_address("valid.analyst@gmail.com")
    assert valid
    assert msg == ""


def test_password_policy_rules():
    # 1. Password too short (< 12 chars)
    valid, errs = validate_password_strength("Short1!", "user@example.com")
    assert not valid
    assert any("at least 12 characters" in e for e in errs)

    # 2. Missing uppercase
    valid, errs = validate_password_strength("lowercase123!", "user@example.com")
    assert not valid
    assert any("uppercase" in e for e in errs)

    # 3. Missing lowercase
    valid, errs = validate_password_strength("UPPERCASE123!", "user@example.com")
    assert not valid
    assert any("lowercase" in e for e in errs)

    # 4. Missing number
    valid, errs = validate_password_strength("NoNumberHere!", "user@example.com")
    assert not valid
    assert any("number" in e for e in errs)

    # 5. Missing special character
    valid, errs = validate_password_strength("NoSpecialChar123", "user@example.com")
    assert not valid
    assert any("special character" in e for e in errs)

    # 6. Common password
    valid, errs = validate_password_strength("Password123!", "user@example.com")
    assert not valid
    assert any("common" in e for e in errs)

    # 7. Email local-part inclusion
    valid, errs = validate_password_strength("MyAnalystPass123!", "analyst@example.com")
    assert not valid
    assert any("email username" in e for e in errs)

    # 8. Valid strong password
    valid, errs = validate_password_strength("SecureP@ssw0rd2026!", "user@example.com")
    assert valid
    assert len(errs) == 0


from fastapi.testclient import TestClient
from main import app


def test_api_onboarding_and_otp_flow(test_db):
    client = TestClient(app)
    email = "new.analyst.2026@gmail.com"
    password = "SecureP@ssw0rd2026!"

    # 1. Check Email (Available)
    res = client.post("/api/auth/check-email", json={"email": email})
    assert res.status_code == 200
    data = res.json()
    assert data["exists"] is False
    assert data["deliverable"] is True

    # 2. Onboard (Generates OTP)
    res = client.post("/api/auth/onboard", json={"email": email, "password": password})
    assert res.status_code == 201
    data = res.json()
    assert data["status"] == "verification_required"
    assert data["dev_otp"] is not None
    otp = data["dev_otp"]

    # 3. Verify OTP with wrong code (Rejected)
    res = client.post("/api/auth/verify-email", json={"email": email, "code": "000000"})
    assert res.status_code == 400
    assert "Invalid verification code" in res.json()["detail"]

    # 4. Verify OTP with correct code (Success)
    res = client.post("/api/auth/verify-email", json={"email": email, "code": otp})
    assert res.status_code == 200
    data = res.json()
    assert data["authenticated"] is True
    assert data["assigned_role"] is None

    # 5. One-Time Role Selection
    res = client.post("/api/auth/role", json={"role": "BUSINESS_ANALYST"})
    assert res.status_code == 200
    assert res.json()["assigned_role"] == "BUSINESS_ANALYST"
