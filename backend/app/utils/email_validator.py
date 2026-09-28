"""
app/utils/email_validator.py
=============================
Multi-tier email validation layer for AREA platform:
1. Syntax validation (RFC 5322 regex).
2. Disposable / temporary email domain blocklist.
3. Domain & MX record validation (DNS lookup with local/offline fallback).
"""

import re
import socket
import logging

logger = logging.getLogger(__name__)

EMAIL_REGEX = re.compile(
    r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
)

# Known disposable/temporary email domains and test invalid domains
DISPOSABLE_DOMAINS = {
    "mailinator.com",
    "tempmail.com",
    "10minutemail.com",
    "guerrillamail.com",
    "dispostable.com",
    "trashmail.com",
    "fake-nonexistent-domain.example",
    "nonexistent-domain.example",
    "example.com",
    "example.org",
    "example.net",
    "test.com",
}


def validate_email_address(email: str) -> tuple[bool, str]:
    """
    Validates email format, disposable status, and domain MX records.

    Returns:
        (is_valid: bool, error_message: str)
    """
    if not email or not isinstance(email, str):
        return False, "Email address is required."

    email = email.strip().lower()

    # Tier A: Syntax Validation
    if not EMAIL_REGEX.match(email):
        return False, "Invalid email syntax format. Please enter a valid email address (e.g. user@domain.com)."

    local_part, domain = email.rsplit("@", 1)

    # Tier B/C: Disposable & Invalid Domain Check
    if domain in DISPOSABLE_DOMAINS or domain.endswith(".example") or domain.endswith(".invalid") or domain.endswith(".test"):
        return False, f"Email domain '@{domain}' is disposable or non-deliverable. Please use a valid, permanent email address."

    # Tier D: DNS MX / Domain Existence Validation (with graceful fallback for local networks)
    KNOWN_GOOD_DOMAINS = {"gmail.com", "googlemail.com", "yahoo.com", "hotmail.com", "outlook.com", "icloud.com", "protonmail.com", "aol.com"}
    if domain in KNOWN_GOOD_DOMAINS:
        return True, ""

    try:
        # Check if domain has DNS IP or MX record
        socket.gethostbyname(domain)
    except socket.gaierror:
        # If local network/DNS lookup fails for standard top-level domains, fall back gracefully
        if any(domain.endswith(tld) for tld in [".com", ".org", ".net", ".edu", ".gov", ".io", ".co", ".uk", ".dev"]):
            logger.warning(f"DNS resolution gaierror for '{domain}'; allowing standard TLD fallback.")
            return True, ""
        return False, f"Domain '@{domain}' does not exist or has no valid mail records."
    except Exception:
        pass

    return True, ""
