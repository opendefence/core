"""Configuration from CORE_OPERATOR_* environment variables."""

from functools import cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Config(BaseSettings):
    """Operator configuration; opendefence_core.config holds the settings shared with the API."""

    model_config = SettingsConfigDict(env_prefix="CORE_OPERATOR_")

    # cert-manager duration of user certificates, in whole hours
    user_certificate_duration: str = Field(default="2880h", pattern=r"^[1-9][0-9]*h$")


@cache
def get_operator_config() -> Config:
    """Configuration, read from the environment on first use."""
    return Config()
