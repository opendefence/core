"""Services for the TCP and UDP ports that an Integration lists."""

from cloudcoil.apimachinery import IntOrString, ObjectMeta
from cloudcoil.models.kubernetes.core.v1 import Service, ServicePort, ServiceSpec

from lib_opendefence_core.models.v1alpha1 import Integration
from lib_opendefence_core.models.v1alpha1.integration import IntegrationPort, IntegrationPortStatus
from opendefence_core.k8s_operator.controllers._refs import CachedStore


def public_ports(integration: Integration) -> list[IntegrationPortStatus]:
    """The public port of each listed port that has one."""
    return [
        IntegrationPortStatus(name=port.name, protocol=port.protocol, public_port=port.public_port)
        for port in integration.spec.network.ingress.ports
        if port.public_port is not None
    ]


def _target(backend: Service | None, port: IntegrationPort) -> tuple[dict[str, str], IntOrString] | None:
    """Selector and target port of the backend Service port that the entry names."""
    spec = backend.spec if backend else None
    if spec is None or not spec.selector:
        return None
    for item in spec.ports or []:
        if item.port == port.port and (item.protocol or "TCP") == port.protocol:
            return spec.selector, item.target_port or IntOrString(item.port)
    return None


def port_services(
    integration: Integration,
    public: list[IntegrationPortStatus],
    backends: CachedStore[Service],
    service_type: str,
) -> tuple[list[Service], list[str]]:
    """The <service>-external Services in the Integration's namespace, and the names of the ports with no backend.

    Each backend Service gets one Service, which carries every public port that names it.
    A NodePort Service opens the public port on the node. A LoadBalancer Service leaves that to the load balancer.
    """
    node_port = service_type == "NodePort"
    numbers = {port.name: port.public_port for port in public}
    grouped: dict[str, tuple[dict[str, str], list[ServicePort]]] = {}
    missing: list[str] = []
    for port in integration.spec.network.ingress.ports:
        number = numbers.get(port.name)
        if number is None:
            continue
        target = _target(backends.get(port.service, integration.name), port)
        if target is None:
            missing.append(port.name)
            continue
        selector, target_port = target
        _, service_ports = grouped.setdefault(port.service, (selector, []))
        service_ports.append(
            ServicePort(
                name=f"{port.protocol.lower()}-{number}",
                protocol=port.protocol,
                port=number,
                target_port=target_port,
                node_port=number if node_port else None,
            )
        )
    return [
        Service(
            metadata=ObjectMeta(name=f"{name}-external", namespace=integration.name),
            spec=ServiceSpec(
                type=service_type,
                allocate_load_balancer_node_ports=None if node_port else False,
                selector=selector,
                ports=ports,
            ),
        )
        for name, (selector, ports) in grouped.items()
    ], missing
