"""Shared pytest setup."""

import os

# The API requires its public hostname; tests use the local development one
os.environ.setdefault("CORE_API_DOMAIN", "local-dev.opendefence.fi")
