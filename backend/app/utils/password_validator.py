"""
app/utils/password_validator.py
================================
Enterprise password security policy validator for AREA platform:
- Minimum length: 12 characters
- At least one uppercase letter (A-Z)
- At least one lowercase letter (a-z)
- At least one number (0-9)
- At least one special character (!@#$%^&*()_+-=[]{}|;:,.<>?)
- Excludes common/obvious passwords (e.g. Password123!, Admin123456!)
- Excludes user email local-part
"""

import re
from typing import List, Tuple

COMMON_PASSWORDS = {
    "password123!",
    "password@123",
    "admin123456!",
    "administrator!",
    "123456789012",
    "qwerty123456!",
    "welcome12345!",
}

SPECIAL_CHAR_REGEX = re.compile(r"[!@#$%^&*()_+\-=\[\]{}|;:,.<>?]")


def validate_password_strength(password: str, email: str = "") -> Tuple[bool, List[str]]:
    """
    Validates password strength against policy rules.

    Returns:
        (is_valid: bool, list_of_error_messages: List[str])
    """
    errors: List[str] = []

    if not password or len(password) < 12:
        errors.append("Password must be at least 12 characters long.")

    if not re.search(r"[A-Z]", password):
        errors.append("Password must contain at least one uppercase letter (A-Z).")

    if not re.search(r"[a-z]", password):
        errors.append("Password must contain at least one lowercase letter (a-z).")

    if not re.search(r"[0-9]", password):
        errors.append("Password must contain at least one number (0-9).")

    if not SPECIAL_CHAR_REGEX.search(password):
        errors.append("Password must contain at least one special character (e.g. !@#$%^&*).")

    if password.lower() in COMMON_PASSWORDS:
        errors.append("Password is too common or easily guessable. Please choose a unique password.")

    if email and "@" in email:
        local_part = email.split("@")[0].lower()
        if len(local_part) >= 3 and local_part in password.lower():
            errors.append("Password must not contain your email username.")

    return len(errors) == 0, errors
