"""Configuration from CORE_OPERATOR_* environment variables."""

from functools import cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Config(BaseSettings):
    """Operator configuration; opendefence_core.config holds the settings shared with the API."""

    model_config = SettingsConfigDict(env_prefix="CORE_OPERATOR_")

    # cert-manager duration of user certificates, in whole hours
    user_certificate_duration: str = Field(default="2880h", pattern=r"^[1-9][0-9]*h$")
    # Service type that opens integration ports, from the package's ports.serviceType value
    port_service_type: Literal["LoadBalancer", "NodePort"] = "LoadBalancer"
    # First and last port that an integration port with no publicPort can get, from the ports.pool value
    port_pool_start: int = Field(default=30000, ge=1024, le=65535)
    port_pool_end: int = Field(default=32767, ge=1024, le=65535)

    @property
    def port_pool(self) -> range:
        """The pool, with both ends."""
        return range(self.port_pool_start, self.port_pool_end + 1)


@cache
def get_operator_config() -> Config:
    """Configuration, read from the environment on first use."""
    return Config()
