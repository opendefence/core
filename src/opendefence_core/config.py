"""Configuration shared by the operator and the REST API, from CORE_* environment variables."""

from functools import cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Config(BaseSettings):
    """Deployment-wide configuration; both Deployments read it from the core-config ConfigMap."""

    model_config = SettingsConfigDict(env_prefix="CORE_")

    # Public hostname, from the package's domain value
    domain: str = Field(min_length=1)
    # First DNS label of the domain, e.g. local-dev; the ConfigMap template derives it
    deployment: str = Field(min_length=1)


@cache
def get_config() -> Config:
    """Configuration, read from the environment on first use."""
    return Config()
