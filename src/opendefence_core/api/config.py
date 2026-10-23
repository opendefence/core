"""Configuration from CORE_API_* environment variables."""

from functools import cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Config(BaseSettings):
    """REST API configuration; opendefence_core.config holds the settings shared with the operator."""

    model_config = SettingsConfigDict(env_prefix="CORE_API_")

    # JWT
    jwt_key_path: Path = Path("/var/run/secrets/opendefence/jwt/tls.key")  # PEM ECDSA private key
    jwt_lifetime: int = 60 * 60 * 4  # 4 hours, in seconds
    jwt_issuer: str = "opendefence-core"


@cache
def get_api_config() -> Config:
    """Configuration, read from the environment on first use."""
    return Config()
