"""Random codes."""

import secrets
import string

ALPHABET = string.ascii_uppercase + string.digits


def generate_code(length: int) -> str:
    """Random code of the given length."""
    return "".join(secrets.choice(ALPHABET) for _ in range(length))
