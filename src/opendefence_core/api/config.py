"""Configuration from CORE_API_* environment variables."""

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Config(BaseSettings):
    """REST API configuration"""

    model_config = SettingsConfigDict(env_prefix="CORE_API_")
    domain: str = "local-dev.opendefence.fi"

    # JWT
    jwt_key_path: Path = Path("/var/run/secrets/opendefence/jwt/tls.key")  # PEM ECDSA private key
    jwt_lifetime: int = 60 * 60 * 4  # 4 hours, in seconds
    jwt_issuer: str = "opendefence-core"

    @property
    def deployment(self) -> str:
        """First DNS label, e.g. local-dev."""
        return self.domain.split(".", maxsplit=1)[0]


config = Config()
