"""
Topology plugin.

Usage:

    @pytest.mark.requires_topology("spine_leaf", spines=2, leaves=4)
    def test_something(topology):
        ...

The topology is built once and shared (scope="session" by default), or
per module / per test with scope="module" / scope="function". Everything
gets torn down automatically. Built topologies are validated first, and a
test that changes a shared topology gets an error.

Options:
    --topology-validation=strict|warn|off   (default strict)
    --topology NAME                          only run tests that use NAME
"""
import hashlib
import ipaddress
import json
import warnings
from collections import Counter

import pytest

from mock_nos.errors import TopologyError
from mock_nos.topology import DeviceRole, TopologyBuilder

SCOPES = ("function", "module", "session")
MANAGER = pytest.StashKey()


class TopologyValidationError(Exception):
    pass


class Request:
    def __init__(self, marker):
        if len(marker.args) != 1:
            raise pytest.UsageError(f"requires_topology takes one name, got {marker.args}")
        self.name = marker.args[0]
        params = dict(marker.kwargs)
        self.scope = params.pop("scope", "session")
        if self.scope not in SCOPES:
            raise pytest.UsageError(f"requires_topology scope must be one of {SCOPES}")
        self.params = params
        self.key = (self.name, tuple(sorted(params.items())))

    def __str__(self):
        args = ",".join(f"{k}={v}" for k, v in sorted(self.params.items()))
        return f"{self.name}({args})" if args else self.name


# --- topologies available out of the box ---

def spine_leaf(spines=2, leaves=4, **kwargs):
    return TopologyBuilder.create_spine_leaf(num_spines=spines, num_leaves=leaves, **kwargs).build()


def clos(tiers=3, width=2):
    return TopologyBuilder.create_clos(tiers=tiers, width=width).build()


def p2p():
    b = TopologyBuilder("p2p")
    b.add_device("router1", DeviceRole.ROUTER, asn=65001)
    b.add_device("router2", DeviceRole.ROUTER, asn=65002)
    b.add_link("router1", "Ethernet1", "router2", "Ethernet1")
    return b.build()


def from_yaml(path):
    return TopologyBuilder.from_yaml(path).build()


# --- checks (Topology.validate() doesn't catch most of these) ---

def check_builtin(topo):
    return topo.validate()


def check_not_empty(topo):
    return [] if topo.devices else ["no devices"]


def check_ports_exist(topo):
    errors = []
    for link in topo.links:
        for dev, port in ((link.device1, link.port1), (link.device2, link.port2)):
            if dev in topo.devices and port not in topo.devices[dev].ports:
                errors.append(f"link uses non-existent port {dev}:{port}")
    return errors


def check_port_reuse(topo):
    used = Counter()
    for link in topo.links:
        used[link.device1, link.port1] += 1
        used[link.device2, link.port2] += 1
    return [f"port {d}:{p} used by {n} links" for (d, p), n in used.items() if n > 1]


def check_addresses(topo):
    errors = []
    seen = {}
    for dev in topo.devices.values():
        if not dev.loopback_ip:
            continue
        try:
            ip = ipaddress.ip_interface(dev.loopback_ip).ip
        except ValueError:
            errors.append(f"{dev.name}: bad loopback {dev.loopback_ip}")
            continue
        if ip in seen:
            errors.append(f"loopback {ip} on both {seen[ip]} and {dev.name}")
        seen[ip] = dev.name
    return errors


def check_spine_leaf(topo):
    spines, leaves = topo.get_spines(), topo.get_leaves()
    if not spines or not leaves or topo.get_devices_by_role(DeviceRole.SUPER_SPINE):
        return []
    errors = []
    leaf_names = {leaf.name for leaf in leaves}
    for spine in spines:
        missing = leaf_names - set(spine.get_neighbors())
        if missing:
            errors.append(f"{spine.name} not connected to {sorted(missing)}")
    for leaf in leaves:
        if leaf_names & set(leaf.get_neighbors()):
            errors.append(f"{leaf.name} is connected to another leaf")
    return errors


def fingerprint(topo):
    data = json.dumps(topo.to_dict(), sort_keys=True, default=str)
    return hashlib.sha256(data.encode()).hexdigest()


class TopologyManager:
    def __init__(self, validation="strict", hook=None):
        self.validation = validation
        self.hook = hook
        self.factories = {"spine_leaf": spine_leaf, "clos": clos, "p2p": p2p, "yaml": from_yaml}
        self.checks = [check_builtin, check_not_empty, check_ports_exist,
                       check_port_reuse, check_addresses, check_spine_leaf]
        self.cache = {}  # key -> (request, topology, fingerprint)
        self.stats = Counter()

    def register(self, name, factory):
        if name in self.factories:
            raise ValueError(f"topology {name} already registered")
        self.factories[name] = factory

    def validate(self, topo, name=""):
        errors = []
        for check in self.checks:
            errors += check(topo)
        if self.hook:
            for result in self.hook.pytest_topology_validate(topology=topo, name=name):
                errors += result or []
        return errors

    def get(self, req):
        if req.scope != "function" and req.key in self.cache:
            self.stats["cache_hits"] += 1
            return self.cache[req.key][1]

        if req.name not in self.factories:
            raise TopologyValidationError(
                f"unknown topology {req.name!r}, registered: {sorted(self.factories)}")
        try:
            topo = self.factories[req.name](**req.params)
        except TopologyError as e:
            self.stats["validation_failures"] += 1
            raise TopologyValidationError(f"{req} could not be built: {e}")
        self.stats["built"] += 1

        if self.validation != "off":
            errors = self.validate(topo, req.name)
            if errors:
                self.stats["validation_failures"] += 1
                msg = f"{req} failed validation:\n" + "\n".join(f"  - {e}" for e in errors)
                if self.validation == "strict":
                    self._teardown(topo)
                    raise TopologyValidationError(msg)
                warnings.warn(msg)

        if req.scope != "function":
            self.cache[req.key] = (req, topo, fingerprint(topo))
        return topo

    def release(self, req, topo):
        """Returns an error message if a shared topology was modified by the test."""
        if req.scope == "function":
            self._teardown(topo)
            return None
        cached = self.cache.get(req.key)
        if not cached or cached[1] is not topo:
            return None
        if fingerprint(topo) != cached[2]:
            self.stats["mutations"] += 1
            del self.cache[req.key]
            self._teardown(topo)
            return (f"test modified shared {req.scope}-scoped topology {req}, "
                    f"use scope='function' if you need to change it")
        return None

    def release_scope(self, scope):
        for key in [k for k, v in self.cache.items() if v[0].scope == scope]:
            self._teardown(self.cache.pop(key)[1])

    def teardown_all(self):
        for _, topo, _ in self.cache.values():
            self._teardown(topo)
        self.cache.clear()

    def _teardown(self, topo):
        topo.teardown()
        self.stats["torn_down"] += 1


# --- pytest hooks ---

def pytest_addhooks(pluginmanager):
    from tests.plugins import hookspecs
    pluginmanager.add_hookspecs(hookspecs)


def pytest_addoption(parser):
    group = parser.getgroup("topology")
    group.addoption("--topology-validation", choices=["strict", "warn", "off"], default="strict",
                    help="what to do when a topology fails validation")
    group.addoption("--topology", action="append", default=[], metavar="NAME",
                    help="only run tests that need topology NAME")


def pytest_configure(config):
    config.addinivalue_line(
        "markers", "requires_topology(name, scope='session', **params): test needs a topology")
    manager = TopologyManager(config.getoption("topology_validation"), config.hook)
    config.hook.pytest_topology_register(manager=manager)
    config.stash[MANAGER] = manager


def pytest_report_header(config):
    m = config.stash[MANAGER]
    return f"topologies: {', '.join(sorted(m.factories))} (validation={m.validation})"


def pytest_collection_modifyitems(config, items):
    wanted = config.getoption("topology")
    if not wanted:
        return
    keep, drop = [], []
    for item in items:
        marker = item.get_closest_marker("requires_topology")
        if marker and marker.args and marker.args[0] in wanted:
            keep.append(item)
        else:
            drop.append(item)
    if drop:
        config.hook.pytest_deselected(items=drop)
        items[:] = keep


@pytest.hookimpl(tryfirst=True)
def pytest_runtest_setup(item):
    marker = item.get_closest_marker("requires_topology")
    if marker is None:
        return
    req = Request(marker)
    manager = item.config.stash[MANAGER]
    if req.name not in manager.factories:
        pytest.fail(f"unknown topology {req.name!r}, registered: {sorted(manager.factories)}",
                    pytrace=False)
    item.user_properties.append(("topology", str(req)))


@pytest.hookimpl(trylast=True)
def pytest_runtest_teardown(item, nextitem):
    # drop module scoped topologies when we move to the next module
    if nextitem is None or nextitem.module is not item.module:
        item.config.stash[MANAGER].release_scope("module")


def pytest_sessionfinish(session):
    session.config.stash[MANAGER].teardown_all()


def pytest_terminal_summary(terminalreporter, config):
    s = config.stash[MANAGER].stats
    if s["built"]:
        terminalreporter.write_sep("-", "topologies")
        terminalreporter.write_line(
            f"built={s['built']} cache_hits={s['cache_hits']} torn_down={s['torn_down']} "
            f"mutations={s['mutations']} validation_failures={s['validation_failures']}")


# --- fixtures ---

@pytest.fixture(scope="session")
def topology_manager(pytestconfig):
    return pytestconfig.stash[MANAGER]


@pytest.fixture
def topology(request, topology_manager):
    marker = request.node.get_closest_marker("requires_topology")
    if marker is None:
        pytest.fail("topology fixture needs @pytest.mark.requires_topology(...)", pytrace=False)
    req = Request(marker)
    try:
        topo = topology_manager.get(req)
    except TopologyValidationError as e:
        error = str(e)
    else:
        error = None
    if error:
        pytest.fail(error, pytrace=False)

    yield topo

    error = topology_manager.release(req, topo)
    if error:
        pytest.fail(error, pytrace=False)
