"""Services for the TCP and UDP ports that an Integration lists."""

from cloudcoil.apimachinery import IntOrString, ObjectMeta
from cloudcoil.models.kubernetes.core.v1 import Service, ServicePort, ServiceSpec

from lib_opendefence_core.models.v1alpha1 import Integration
from lib_opendefence_core.models.v1alpha1.integration import IntegrationPort, IntegrationPortStatus
from opendefence_core.k8s_operator.controllers._refs import CachedStore


def public_ports(integration: Integration, taken: set[int], pool: range) -> list[IntegrationPortStatus]:
    """The public port of each listed port. A port that the pool has no number for is left out.

    A port with no publicPort keeps the number that status holds for it, while that number is in the pool and free.
    Otherwise it takes the lowest free number of the pool. A number is taken on both protocols at once.
    taken holds the numbers of other Integrations.
    """
    ports = integration.spec.network.ingress.ports
    held = {
        (port.name, port.protocol): port.public_port
        for port in (integration.status.ports if integration.status else [])
    }
    numbers = {port.name: port.public_port for port in ports if port.public_port is not None}
    taken = taken | set(numbers.values())
    unpinned = [port for port in ports if port.public_port is None]
    # Kept numbers go first, so that a new port cannot take the number of a later port
    for port in unpinned:
        number = held.get((port.name, port.protocol))
        if number is not None and number in pool and number not in taken:
            numbers[port.name] = number
            taken.add(number)
    for port in unpinned:
        number = next((number for number in pool if number not in taken), None)
        if port.name not in numbers and number is not None:
            numbers[port.name] = number
            taken.add(number)
    return [
        IntegrationPortStatus(name=port.name, protocol=port.protocol, public_port=numbers[port.name])
        for port in ports
        if port.name in numbers
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
