"""Event recording for cluster-scoped platform objects."""

from typing import Any, override

from cloudcoil._context import context
from cloudcoil.controller import EventRecorder
from cloudcoil.resources import Resource


class OperatorEventRecorder(EventRecorder):
    """Record Events in the operator namespace for cluster-scoped objects.

    Kubernetes rejects ``events.k8s.io/v1`` Events whose ``regarding.namespace``
    is empty unless they live in ``default`` or ``kube-system``. Cloudcoil omits
    that field for cluster-scoped objects, then posts the Event into
    ``Config.namespace`` (the operator namespace), which the API rejects. Copy
    the operator namespace onto a throwaway object so ``regarding.namespace``
    matches the Event namespace.
    """

    @override
    async def emit(self, resource: Resource, reason: str, message: str, **kwargs: Any) -> bool:
        if resource.namespace is None and resource.metadata is not None:
            config = kwargs.get("config") or context.active_config
            kwargs["config"] = config
            namespace = self.namespace or config.namespace
            if namespace:
                resource = resource.model_copy(
                    update={"metadata": resource.metadata.model_copy(update={"namespace": namespace})}
                )
        return await super().emit(resource, reason, message, **kwargs)


def recorder(name: str) -> OperatorEventRecorder:
    """Return the EventRecorder cloudcoil would create for a named controller."""
    return OperatorEventRecorder(f"opendefence/{name}")
