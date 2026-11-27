"""Reference helpers, reconcile handlers, and watch mappers."""

from collections.abc import Callable
from typing import Any, cast
from unittest.mock import Mock, PropertyMock

import pytest
from cloudcoil.controller import Context, Controller, ResourceKey, TerminalError, Wait
from cloudcoil.errors import ResourceConflict
from cloudcoil.models.kubernetes.core.v1 import Service
from cloudcoil.resources import Resource

from lib_opendefence_core.models.v1alpha1 import (
    API_VERSION,
    BINDINGS_SYNCED_CONDITION,
    PORTS_READY_CONDITION,
    REFERENCES_RESOLVED_CONDITION,
    Group,
    Integration,
    Invite,
    ObjectRef,
    Role,
    User,
    UserBinding,
    is_synced,
)
from lib_opendefence_core.models.v1alpha1.integration import (
    IntegrationHttpRoute,
    IntegrationPort,
    IntegrationPortStatus,
    IntegrationStatus,
)
from opendefence_core.k8s_operator.config import get_operator_config
from opendefence_core.k8s_operator.controllers import groups, invites, users
from opendefence_core.k8s_operator.controllers._refs import referrers_of, resolve_refs
from opendefence_core.k8s_operator.controllers._routes import IngressRoute, Middleware
from opendefence_core.k8s_operator.controllers.groups import manager_changed, parent_group_changed, reconcile_group
from opendefence_core.k8s_operator.controllers.groups import role_changed as group_role_changed
from opendefence_core.k8s_operator.controllers.integrations import reconcile_integration
from opendefence_core.k8s_operator.controllers.invites import group_changed as invite_group_changed
from opendefence_core.k8s_operator.controllers.invites import reconcile_invite
from opendefence_core.k8s_operator.controllers.invites import role_changed as invite_role_changed
from opendefence_core.k8s_operator.controllers.roles import reconcile_role
from opendefence_core.k8s_operator.controllers.users import group_changed as user_group_changed
from opendefence_core.k8s_operator.controllers.users import reconcile_user, userbinding_changed
from opendefence_core.k8s_operator.controllers.users import role_changed as user_role_changed
from tests.factories import (
    make_binding,
    make_group,
    make_integration,
    make_invite,
    make_role,
    make_service,
    make_user,
    uid,
)
from tests.fakes import FakeCache, FakeClient, FakeContext


async def test_reconcile_user_resolves_refs() -> None:
    """User status receives UIDs for named roles and groups."""
    ctx = FakeContext({Role: FakeCache([make_role("superadmin")]), Group: FakeCache([make_group("ops")])})
    await reconcile_user(make_user("alice", roles=["superadmin"], groups=["ops"]), cast(Context[User], ctx))
    assert ctx.status["roles"][0].uid == uid("superadmin")
    assert ctx.status["groups"][0].uid == uid("ops")
    assert ctx.status["bindings"] == []
    assert (REFERENCES_RESOLVED_CONDITION, True, "Resolved", "") in ctx.conditions
    assert (BINDINGS_SYNCED_CONDITION, True, "NoBindings", "") in ctx.conditions


async def test_reconcile_user_publishes_effective_roles_and_groups() -> None:
    """User status carries ancestor groups and each role once, however many ways the user holds it."""
    ctx = FakeContext(
        {
            Role: FakeCache([make_role("medic"), make_role("comms")]),
            Group: FakeCache(
                [make_group("company", roles=["comms"]), make_group("medics", parent="company", roles=["medic"])]
            ),
        }
    )
    await reconcile_user(make_user("alice", roles=["medic"], groups=["medics"]), cast(Context[User], ctx))
    assert [ref.name for ref in ctx.status["groups"]] == ["medics", "company"]
    assert [ref.name for ref in ctx.status["roles"]] == ["comms", "medic"]


@pytest.mark.parametrize(("roles", "groups"), [(["missing"], []), ([], ["missing"])])
async def test_reconcile_user_waits_for_missing_ref(roles: list[str], groups: list[str]) -> None:
    """Missing direct role and group refs wait instead of failing."""
    ctx = FakeContext()
    with pytest.raises(Wait) as raised:
        await reconcile_user(make_user("alice", roles=roles, groups=groups), cast(Context[User], ctx))
    assert raised.value.reason == "MissingReference"
    assert (REFERENCES_RESOLVED_CONDITION, False, "MissingReference") in [
        (name, status, reason) for name, status, reason, _message in ctx.conditions
    ]


async def test_reconcile_group_and_invite() -> None:
    """Group reports references while Invite validates its references."""
    parent = make_group("root")
    role = make_role("group-admin")
    ctx = FakeContext(
        {Group: FakeCache([parent]), User: FakeCache([make_user("alice")]), Role: FakeCache([role])},
    )
    group = make_group("ops", parent="root", managers=["alice"], roles=["group-admin"])
    await reconcile_group(group, cast(Context[Group], ctx))
    assert ctx.status["parent"].uid == uid("root")
    manager = ctx.cached(User).get("alice")
    assert manager is not None and manager.metadata is not None
    assert ctx.status["managers"][0].uid == manager.metadata.uid
    assert ctx.status["roles"][0].uid == uid("group-admin")

    invite_ctx = FakeContext({Group: FakeCache([parent]), Role: FakeCache([role])})
    invite = make_invite("onboarding", groups=["root"], roles=["group-admin"])
    await reconcile_invite(invite, cast(Context[Invite], invite_ctx))
    assert invite_ctx.status == {}
    assert invite_ctx.conditions[-1] == (REFERENCES_RESOLVED_CONDITION, True, "Resolved", "")


async def test_reconcile_group_rejects_self_parent() -> None:
    """A group may not name itself as parent."""
    ctx = FakeContext()
    with pytest.raises(TerminalError):
        await reconcile_group(make_group("ops", parent="ops"), cast(Context[Group], ctx))
    assert ctx.conditions[0][2] == "SelfReference"


async def test_reconcile_group_rejects_parent_cycle() -> None:
    """A two-node parent loop is a permanent reconcile failure."""
    ctx = FakeContext({Group: FakeCache([make_group("eng", parent="ops")])})
    with pytest.raises(TerminalError):
        await reconcile_group(make_group("ops", parent="eng"), cast(Context[Group], ctx))
    assert ctx.conditions[0][2] == "CycleDetected"
    assert "ops -> eng -> ops" in ctx.conditions[0][3]


async def test_reconcile_group_waits_for_missing_ancestor() -> None:
    """A missing ancestor waits instead of resolving the immediate parent."""
    ctx = FakeContext({Group: FakeCache([make_group("eng", parent="missing")])})
    with pytest.raises(Wait) as raised:
        await reconcile_group(make_group("ops", parent="eng"), cast(Context[Group], ctx))
    assert raised.value.reason == "MissingReference"
    assert ctx.conditions[0][2] == "MissingReference"


async def test_reconcile_integration_syncs_extra_roles() -> None:
    """Extra roles are created, dropped owned Roles are deleted, and other Roles stay."""
    owned = make_role("old-role", owner="tak")
    other = make_role("superadmin")
    client = FakeClient([owned, other])
    ctx = FakeContext({Role: FakeCache([owned, other])}, {Role: client})
    await reconcile_integration(make_integration("tak", roles=["mission-lead"]), cast(Context[Integration], ctx))
    assert [role.name for role in ctx.ensured] == ["mission-lead"]
    assert cast(Role, ctx.ensured[0]).spec.display_name == "mission-lead"
    assert client.deleted == [(None, "old-role")]
    assert ctx.conditions[-1][:3] == (REFERENCES_RESOLVED_CONDITION, True, "Resolved")


async def test_reconcile_integration_writes_routes() -> None:
    """Each host with routes gets one IngressRoute in the Integration's namespace."""
    integration = make_integration("matrix")
    integration.spec.network.ingress.http_routes = [
        IntegrationHttpRoute(host="Public", path="/_matrix", service="matrix-synapse", port=8008),
        IntegrationHttpRoute(host="Public", path="/integrations/matrix/", service="matrix-web", port=8080),
        IntegrationHttpRoute(host="App", path="/integrations/matrix/ui", service="matrix-ui", port=8080),
    ]
    ctx = FakeContext()
    await reconcile_integration(integration, cast(Context[Integration], ctx))
    public, app = ctx.ensured
    shared = [
        {"name": "strip-identity-headers", "namespace": "traefik-system"},
        {"name": "hsts", "namespace": "traefik-system"},
    ]
    assert (public.kind, public.name, public.namespace) == ("IngressRoute", "matrix-public", "matrix")
    assert cast(Any, public)["spec"] == {
        "entryPoints": ["websecure"],
        "routes": [
            {
                "kind": "Rule",
                "match": "Host(`local-dev.opendefence.fi`) && (Path(`/_matrix`) || PathPrefix(`/_matrix/`))",
                "middlewares": shared,
                "services": [{"name": "matrix-synapse", "port": 8008}],
            },
            {
                "kind": "Rule",
                "match": "Host(`local-dev.opendefence.fi`) && PathPrefix(`/integrations/matrix/`)",
                "middlewares": shared,
                "services": [{"name": "matrix-web", "port": 8080}],
            },
        ],
        "tls": {},
    }
    assert (app.name, app.namespace) == ("matrix-app", "matrix")
    assert cast(Any, app)["spec"] == {
        "entryPoints": ["websecure"],
        "routes": [
            {
                "kind": "Rule",
                "match": "Host(`app.local-dev.opendefence.fi`) && "
                "(Path(`/integrations/matrix/ui`) || PathPrefix(`/integrations/matrix/ui/`))",
                "middlewares": [shared[0], {"name": "pass-client-cert", "namespace": "traefik-system"}, shared[1]],
                "services": [{"name": "matrix-ui", "port": 8080}],
            },
        ],
        "tls": {"options": {"name": "core-mtls", "namespace": "traefik-system"}},
    }


async def test_reconcile_integration_strips_route_prefixes() -> None:
    """Each stripPrefix gets its own Middleware, written before the route whose rule ends with it."""
    integration = make_integration("matrix")
    integration.spec.network.ingress.http_routes = [
        IntegrationHttpRoute(
            host="Public",
            path="/integrations/matrix/api",
            strip_prefix="/integrations/matrix/api",
            service="api",
            port=9000,
        ),
        IntegrationHttpRoute(
            host="Public",
            path="/integrations/matrix/workload",
            strip_prefix="/integrations/matrix/workload",
            service="workload",
            port=8080,
        ),
    ]
    ctx = FakeContext()
    await reconcile_integration(integration, cast(Context[Integration], ctx))
    strip_api, strip_workload, public = ctx.ensured
    assert (strip_api.kind, strip_api.namespace) == ("Middleware", "matrix")
    assert cast(Any, strip_api)["spec"] == {"stripPrefix": {"prefixes": ["/integrations/matrix/api"]}}
    assert cast(Any, strip_workload)["spec"] == {"stripPrefix": {"prefixes": ["/integrations/matrix/workload"]}}
    assert strip_api.name != strip_workload.name
    last = [rule["middlewares"][-1] for rule in cast(Any, public)["spec"]["routes"]]
    assert last == [{"name": strip_api.name}, {"name": strip_workload.name}]


async def test_reconcile_integration_keeps_a_regex_route_below_its_plain_path() -> None:
    """A regex path is matched together with its leading plain segments."""
    integration = make_integration("matrix")
    integration.spec.network.ingress.http_routes = [
        IntegrationHttpRoute(host="Public", path="^/_workload/(v1|v2)/(start|stop)$", service="workload", port=8080),
    ]
    ctx = FakeContext()
    await reconcile_integration(integration, cast(Context[Integration], ctx))
    assert cast(Any, ctx.ensured[0])["spec"]["routes"][0]["match"] == (
        "Host(`local-dev.opendefence.fi`) && (Path(`/_workload`) || PathPrefix(`/_workload/`))"
        " && PathRegexp(`^/_workload/(v1|v2)/(start|stop)$`)"
    )


async def test_reconcile_integration_denies_blocked_paths() -> None:
    """A blocked path gets its own rule with the deny middleware and a priority above every route."""
    integration = make_integration("matrix")
    integration.spec.network.ingress.http_routes = [
        IntegrationHttpRoute(
            host="Public",
            path="/integrations/matrix/workload",
            blocked_paths=["/integrations/matrix/workload/admin"],
            service="workload",
            port=8080,
        ),
    ]
    ctx = FakeContext()
    await reconcile_integration(integration, cast(Context[Integration], ctx))
    served, blocked = cast(Any, ctx.ensured[0])["spec"]["routes"]
    assert "priority" not in served
    assert blocked == {
        "kind": "Rule",
        "match": "Host(`local-dev.opendefence.fi`) && "
        "(Path(`/integrations/matrix/workload/admin`) || PathPrefix(`/integrations/matrix/workload/admin/`))",
        "priority": 10000,
        "middlewares": [{"name": "deny", "namespace": "traefik-system"}],
        "services": [{"name": "workload", "port": 8080}],
    }


async def test_reconcile_integration_deletes_dropped_routes() -> None:
    """Owned routes and strip Middlewares that the spec no longer needs are deleted; other objects stay."""

    def traefik(kind: type[Resource], name: str, owner: str) -> Resource:
        """Traefik object in the matrix namespace, owned by the named Integration."""
        owner_reference = {
            "apiVersion": API_VERSION,
            "kind": "Integration",
            "name": owner,
            "uid": uid(owner),
            "controller": True,
        }
        return kind.model_validate(
            {"metadata": {"name": name, "namespace": "matrix", "uid": uid(name), "ownerReferences": [owner_reference]}}
        )

    integration = make_integration("matrix")
    integration.spec.network.ingress.http_routes = [
        IntegrationHttpRoute(host="Public", path="/integrations/matrix/workload", service="workload", port=8080),
    ]
    routes = [
        traefik(IngressRoute, "matrix-public", "matrix"),
        traefik(IngressRoute, "matrix-app", "matrix"),
        traefik(IngressRoute, "other-app", "other"),
    ]
    strips = [traefik(Middleware, "matrix-strip-00000000", "matrix")]
    clients: dict[type[Resource], FakeClient[Any]] = {IngressRoute: FakeClient(routes), Middleware: FakeClient(strips)}
    ctx = FakeContext({IngressRoute: FakeCache(routes), Middleware: FakeCache(strips)}, clients)
    await reconcile_integration(integration, cast(Context[Integration], ctx))
    assert clients[IngressRoute].deleted == [("matrix", "matrix-app")]
    assert clients[Middleware].deleted == [("matrix", "matrix-strip-00000000")]


async def test_integration_does_not_delete_replaced_role() -> None:
    """A stale cache cannot delete a new Role owned by another Integration."""
    cached = make_role("old-role", owner="tak")
    replacement = make_role("old-role", owner="radio")
    assert replacement.metadata is not None
    replacement.metadata.uid = "replacement-uid"
    client = FakeClient([replacement])
    ctx = FakeContext({Role: FakeCache([cached])}, clients={Role: client})
    with pytest.raises(ResourceConflict):
        await reconcile_integration(make_integration("tak"), cast(Context[Integration], ctx))
    assert client.deleted == []


def test_stale_binding_condition_does_not_acknowledge_new_spec() -> None:
    binding = make_binding("binding", user="alice", synced=True)
    assert binding.metadata is not None and binding.status is not None
    binding.metadata.generation = 2
    binding.spec.user_ref.name = "bobby"
    assert not is_synced(binding)
    binding.status.conditions[0].observed_generation = None
    assert not is_synced(binding)
    binding.status.conditions[0].observed_generation = 2
    assert is_synced(binding)
    binding.metadata.generation = None
    assert not is_synced(binding)


async def test_reconcile_role_marks_resolved() -> None:
    """Roles have no outgoing refs and report ReferencesResolved."""
    ctx = FakeContext()
    await reconcile_role(make_role("superadmin"), cast(Context[Role], ctx))
    assert ctx.conditions[-1] == (REFERENCES_RESOLVED_CONDITION, True, "Resolved", "")


def test_referrers_of_matches_name_refs() -> None:
    """Reverse mapping finds objects that name the target."""
    alice = make_user("alice", roles=["superadmin"])
    bob = make_user("bob", roles=["group-admin"])
    keys = referrers_of([alice, bob], lambda user: user.spec.role_refs, make_role("superadmin"))
    assert keys == [ResourceKey("alice")]


@pytest.mark.parametrize(
    ("controller", "mapper", "primary", "target"),
    [
        (groups, parent_group_changed, make_group("dependent", parent="target"), make_group("target")),
        (groups, manager_changed, make_group("dependent", managers=["target"]), make_user("target")),
        (groups, group_role_changed, make_group("dependent", roles=["target"]), make_role("target")),
        (invites, invite_group_changed, make_invite("dependent", groups=["target"]), make_group("target")),
        (invites, invite_role_changed, make_invite("dependent", roles=["target"]), make_role("target")),
    ],
)
def test_watch_mappers_wait_for_initial_sync(
    monkeypatch: pytest.MonkeyPatch,
    controller: Controller[Any],
    mapper: Callable[[Any], list[ResourceKey]],
    primary: Resource,
    target: Resource,
) -> None:
    """Initial list events must not read unsynced snapshots; later events requeue dependents."""
    ready = PropertyMock(return_value=False)
    monkeypatch.setattr(Controller, "ready", ready)
    cache = Mock()
    cache.list.return_value = [primary]
    cached = Mock(return_value=cache)
    monkeypatch.setattr(controller, "cached", cached)

    assert mapper(target) == []
    cached.assert_not_called()

    ready.return_value = True
    assert mapper(target) == [ResourceKey("dependent")]
    cached.assert_called_once_with(type(primary))

    cache.list.side_effect = RuntimeError("Informer watch failed")
    with pytest.raises(RuntimeError, match="Informer watch failed"):
        mapper(target)


def test_user_mappers_requeue_effective_holders(monkeypatch: pytest.MonkeyPatch) -> None:
    """A change to an ancestor group or a group-granted role requeues the users below it, once caches are synced."""
    company = make_group("company", roles=["comms"])
    caches: dict[type[Resource], FakeCache[Any]] = {
        User: FakeCache(
            [
                make_user("member", groups=["medics"]),
                make_user("direct", roles=["comms"]),
                make_user("early", groups=["late"]),
                make_user("other", groups=["staff"]),
            ]
        ),
        Group: FakeCache([company, make_group("medics", parent="company"), make_group("staff")]),
    }
    ready = PropertyMock(return_value=False)
    monkeypatch.setattr(Controller, "ready", ready)
    cached = Mock(side_effect=caches.__getitem__)
    monkeypatch.setattr(users, "cached", cached)

    assert user_group_changed(company) == []
    assert user_role_changed(make_role("comms")) == []
    cached.assert_not_called()

    ready.return_value = True
    assert user_group_changed(company) == [ResourceKey("member")]
    assert user_role_changed(make_role("comms")) == [ResourceKey("member"), ResourceKey("direct")]
    assert user_group_changed(make_group("late")) == [ResourceKey("early")]


def test_resolve_refs_skips_objects_without_uid() -> None:
    """A cached object without a UID is treated as missing."""
    role = make_role("superadmin")
    assert role.metadata is not None
    role.metadata.uid = None
    ctx = FakeContext({Role: FakeCache([role])})
    with pytest.raises(Wait):
        resolve_refs(ctx, Role, [ObjectRef(name="superadmin")])


async def test_reconcile_user_reports_pending_and_synced_bindings() -> None:
    """User status lists UserBindings and BindingsSynced follows the Synced condition."""
    pending = make_binding("bob", user="alice", namespace="taky", synced=False)
    synced = make_binding("alice", user="alice", namespace="radio", synced=True)
    other = make_binding("bob", user="bob", namespace="radio", synced=True)
    ctx = FakeContext({UserBinding: FakeCache([pending, synced, other])})
    await reconcile_user(make_user("alice"), cast(Context[User], ctx))
    bindings = ctx.status["bindings"]
    assert [(item.namespace, item.name, item.synced) for item in bindings] == [
        ("radio", "alice", True),
        ("taky", "bob", False),
    ]
    assert (BINDINGS_SYNCED_CONDITION, False, "Pending", "UserBinding not synced: taky/bob") in ctx.conditions

    synced_only = FakeContext({UserBinding: FakeCache([synced])})
    await reconcile_user(make_user("alice"), cast(Context[User], synced_only))
    assert synced_only.status["bindings"][0].synced is True
    assert (BINDINGS_SYNCED_CONDITION, True, "Synced", "") in synced_only.conditions


def test_is_synced_reads_synced_condition() -> None:
    """UserBinding synchronization is True only when the Synced condition is True."""
    assert is_synced(make_binding("bob", user="bob")) is False
    assert is_synced(make_binding("bob", user="bob", synced=False)) is False
    assert is_synced(make_binding("bob", user="bob", synced=True)) is True


def test_userbinding_changed_requeues_named_user(monkeypatch: pytest.MonkeyPatch) -> None:
    """UserBinding events requeue the cluster-scoped User named in userRef."""
    ready = PropertyMock(return_value=False)
    monkeypatch.setattr(Controller, "ready", ready)
    binding = make_binding("bob", user="alice", namespace="taky")
    assert userbinding_changed(binding) == []

    ready.return_value = True
    assert userbinding_changed(binding) == [ResourceKey("alice")]


@pytest.mark.parametrize("service_type", ["LoadBalancer", "NodePort"])
async def test_reconcile_integration_opens_pinned_ports(monkeypatch: pytest.MonkeyPatch, service_type: str) -> None:
    """One <service>-external Service carries every pinned port of a backend. A dropped one is deleted."""
    monkeypatch.setattr(get_operator_config(), "port_service_type", service_type)
    integration = make_integration("radio")
    integration.spec.network.ingress.ports = [
        IntegrationPort(name="feed", protocol="UDP", public_port=5000, service="relay", port=4000),
        IntegrationPort(name="control", protocol="TCP", public_port=5001, service="relay", port=4001),
    ]
    backend = make_service("relay", "radio", ports=[(4000, "UDP", "feed"), (4001, "TCP", 8001)])
    dropped = make_service("old-external", "radio", owner="radio")
    client = FakeClient([backend, dropped])
    ctx = FakeContext({Service: FakeCache([backend, dropped])}, {Service: client})
    await reconcile_integration(integration, cast(Context[Integration], ctx))
    [service] = [item for item in ctx.ensured if isinstance(item, Service)]
    assert (service.name, service.namespace) == ("relay-external", "radio")
    node = service_type == "NodePort"
    assert service.model_dump(mode="json", by_alias=True, exclude_none=True)["spec"] == {
        "type": service_type,
        **({} if node else {"allocateLoadBalancerNodePorts": False}),
        "selector": {"app": "relay"},
        "ports": [
            {"name": "udp-5000", "protocol": "UDP", "port": 5000, "targetPort": "feed"}
            | ({"nodePort": 5000} if node else {}),
            {"name": "tcp-5001", "protocol": "TCP", "port": 5001, "targetPort": 8001}
            | ({"nodePort": 5001} if node else {}),
        ],
    }
    assert ctx.status["ports"] == [
        IntegrationPortStatus(name="feed", protocol="UDP", public_port=5000),
        IntegrationPortStatus(name="control", protocol="TCP", public_port=5001),
    ]
    assert client.deleted == [("radio", "old-external")]
    assert (PORTS_READY_CONDITION, True, "Opened", "") in ctx.conditions


async def test_reconcile_integration_waits_for_a_port_backend() -> None:
    """A port with no backend Service is reported. Its public port is still in status."""
    integration = make_integration("radio")
    integration.spec.network.ingress.ports = [
        IntegrationPort(name="feed", protocol="UDP", public_port=5000, service="relay", port=4000)
    ]
    ctx = FakeContext()
    with pytest.raises(Wait):
        await reconcile_integration(integration, cast(Context[Integration], ctx))
    assert ctx.status["ports"] == [IntegrationPortStatus(name="feed", protocol="UDP", public_port=5000)]
    assert ctx.conditions[-1][:3] == (PORTS_READY_CONDITION, False, "BackendNotFound")
    assert ctx.ensured == []


async def test_reconcile_integration_assigns_ports_from_the_pool() -> None:
    """An unpinned port keeps the number in status, or takes the lowest one that no other Integration holds."""
    integration = make_integration("radio")
    integration.spec.network.ingress.ports = [
        IntegrationPort(name="feed", protocol="UDP", service="relay", port=4000),
        IntegrationPort(name="control", protocol="TCP", service="relay", port=4001),
        IntegrationPort(name="admin", protocol="TCP", service="relay", port=4002),
    ]
    integration.status = IntegrationStatus(
        ports=[IntegrationPortStatus(name="admin", protocol="TCP", public_port=30002)]
    )
    other = make_integration("beacon")
    other.status = IntegrationStatus(ports=[IntegrationPortStatus(name="ping", protocol="UDP", public_port=30000)])
    backend = make_service("relay", "radio", ports=[(4000, "UDP", "feed"), (4001, "TCP", 8001), (4002, "TCP", 8002)])
    ctx = FakeContext({Service: FakeCache([backend])}, {Integration: FakeClient([integration, other])})
    await reconcile_integration(integration, cast(Context[Integration], ctx))
    assert [(port.name, port.public_port) for port in ctx.status["ports"]] == [
        ("feed", 30001),
        ("control", 30003),
        ("admin", 30002),
    ]
    [service] = [item for item in ctx.ensured if isinstance(item, Service)]
    assert service.spec is not None
    assert [port.name for port in service.spec.ports or []] == ["udp-30001", "tcp-30003", "tcp-30002"]
    assert (PORTS_READY_CONDITION, True, "Opened", "") in ctx.conditions


async def test_reconcile_integration_reports_an_exhausted_pool(monkeypatch: pytest.MonkeyPatch) -> None:
    """A number outside the pool is replaced. A port that the pool has no number for is reported."""
    monkeypatch.setattr(get_operator_config(), "port_pool_end", 30000)
    integration = make_integration("radio")
    integration.spec.network.ingress.ports = [
        IntegrationPort(name="feed", protocol="TCP", service="relay", port=4000),
        IntegrationPort(name="control", protocol="TCP", service="relay", port=4001),
    ]
    integration.status = IntegrationStatus(
        ports=[IntegrationPortStatus(name="feed", protocol="TCP", public_port=40000)]
    )
    backend = make_service("relay", "radio", ports=[(4000, "TCP", 8000), (4001, "TCP", 8001)])
    ctx = FakeContext({Service: FakeCache([backend])})
    with pytest.raises(Wait):
        await reconcile_integration(integration, cast(Context[Integration], ctx))
    assert ctx.status["ports"] == [IntegrationPortStatus(name="feed", protocol="TCP", public_port=30000)]
    assert ctx.conditions[-1][:3] == (PORTS_READY_CONDITION, False, "PoolExhausted")
    assert [item.name for item in ctx.ensured] == ["relay-external"]
