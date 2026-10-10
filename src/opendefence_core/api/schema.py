"""Shared bases for REST API request and response bodies."""

from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel


class ApiModel(BaseModel):
    """JSON body with camelCase field names."""

    model_config = ConfigDict(alias_generator=to_camel, validate_by_name=True)


class ErrorResponse(ApiModel):
    """Error body, same shape as FastAPI's HTTPException."""

    detail: str
