"""Shared pytest setup."""

import os

# Shared configuration is required; tests use what the core-config ConfigMap holds for local-dev
os.environ.setdefault("CORE_DOMAIN", "local-dev.opendefence.fi")
os.environ.setdefault("CORE_DEPLOYMENT", "local-dev")
