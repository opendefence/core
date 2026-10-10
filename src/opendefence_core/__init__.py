"""Runs core operators and REST API for OpenDefence operational platform"""

from importlib.metadata import version

# Bump with `uv run --locked bump-my-version bump patch`
__version__ = version("opendefence_core")
