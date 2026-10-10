"""Package level tests"""

from opendefence_core import __version__


def test_version() -> None:
    """Make sure version matches expected"""
    assert __version__ == "0.2.0+261010"
