"""Shared identity types for platform.opendefence.fi/v1alpha1."""

from typing import Annotated

from pydantic import Field

from cloudcoil.apimachinery import Condition, Time
from cloudcoil.crd import ListType
from cloudcoil.pydantic import BaseModel

API_VERSION = "platform.opendefence.fi/v1alpha1"


class PlatformCondition(Condition):
    """Kubernetes condition with descriptions for generated CRD schemas."""

    last_transition_time: Time = Field(
        alias="lastTransitionTime",
        description="RFC 3339 timestamp when the condition last changed status.",
    )
    message: str = Field(
        description="Human-readable details about the condition's current state.",
    )
    observed_generation: int | None = Field(
        default=None,
        alias="observedGeneration",
        description="Resource generation used to determine the condition.",
    )
    reason: str = Field(
        description="Machine-readable reason for the condition's current state.",
    )
    status: str = Field(
        description="Whether the condition is True, False, or Unknown.",
    )
    type: str = Field(
        description="Machine-readable type identifying the condition.",
    )


class ObjectRef(BaseModel):
    """Name of a cluster-scoped platform object."""

    name: str = Field(
        min_length=1,
        description="Kubernetes resource name of the referenced platform object.",
    )


class ResolvedRef(BaseModel):
    """Name plus the Kubernetes UID of a resolved platform object."""

    name: str = Field(
        min_length=1,
        description="Kubernetes resource name of the platform object.",
    )
    uid: str = Field(
        min_length=1,
        description="Kubernetes UID of the platform object.",
    )


class PlatformStatus(BaseModel):
    """Ready conditions and observedGeneration for platform resources."""

    conditions: Annotated[list[PlatformCondition], ListType("map", keys=("type",))] = Field(
        default_factory=list,
        description="Conditions describing the resource's current reconciliation state.",
    )
    observed_generation: int | None = Field(
        default=None,
        alias="observedGeneration",
        description="Most recent metadata.generation observed by the controller.",
    )
