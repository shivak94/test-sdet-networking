"""
Shared pytest fixtures for NOS testing.
"""
import time

import pytest
from typing import Any, Dict, Generator, List, Optional

from mock_nos.database import RedisMock, ConfigDB, StateDB
from mock_nos.protocols.bgp import BGPSession, BGPNeighbor, BGPState, BGPOpenMessage
from mock_nos.protocols.ospf import OSPFInstance, OSPFNeighbor, OSPFNeighborState
from mock_nos.containers import BGPContainer, SwssContainer, ContainerState
from mock_nos.hal import PortManager, RouteManager
from mock_nos.topology import TopologyBuilder, Topology, DeviceRole


pytest_plugins = ["tests.plugins.topology_plugin"]


# =============================================================================
# CLOCK
# =============================================================================

class FakeClock:
    """Stand-in for the time module so timer tests don't have to sleep."""

    def __init__(self, start: float = 1_000_000.0):
        self.now = start

    def time(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.now += seconds

    def advance(self, seconds: float) -> None:
        self.now += seconds


@pytest.fixture
def fake_clock(monkeypatch) -> FakeClock:
    import mock_nos.protocols.bgp as bgp_mod
    import mock_nos.protocols.ospf as ospf_mod

    clock = FakeClock()
    monkeypatch.setattr(bgp_mod, "time", clock)
    monkeypatch.setattr(ospf_mod, "time", clock)
    return clock


# =============================================================================
# DATABASE FIXTURES
# =============================================================================

@pytest.fixture(scope="function")
def redis_mock() -> Generator[RedisMock, None, None]:
    """
    Create a fresh Redis mock for each test.

    This fixture provides an isolated in-memory database instance
    that is automatically cleared after each test.
    """
    db = RedisMock()
    yield db
    db.clear()


@pytest.fixture(scope="function")
def config_db(redis_mock: RedisMock) -> ConfigDB:
    """
    Create CONFIG_DB connected to Redis mock.

    This fixture provides a configuration database for storing
    port configs, VLANs, BGP neighbors, etc.
    """
    return ConfigDB(redis_mock)


@pytest.fixture(scope="function")
def state_db(redis_mock: RedisMock) -> StateDB:
    """
    Create STATE_DB connected to Redis mock.

    This fixture provides a state database for storing
    operational state like port status, BGP neighbor states, etc.
    """
    return StateDB(redis_mock)


@pytest.fixture(scope="function")
def databases(config_db: ConfigDB, state_db: StateDB, redis_mock: RedisMock) -> Dict[str, Any]:
    """Bundle all databases for container initialization."""
    return {"config": config_db, "state": state_db, "redis": redis_mock}


# =============================================================================
# PROTOCOL FIXTURES
# =============================================================================

@pytest.fixture(scope="function")
def bgp_session() -> BGPSession:
    """
    Create a basic BGP session with default configuration.

    Returns:
        BGPSession with router_id="10.0.0.1" and local_as=65001
    """
    return BGPSession(router_id="10.0.0.1", local_as=65001)


@pytest.fixture(scope="function")
def bgp_session_with_neighbor(bgp_session: BGPSession) -> BGPSession:
    """Create a BGP session with one pre-configured neighbor."""
    bgp_session.add_neighbor({"neighbor_ip": "10.0.0.2", "remote_as": 65002})
    return bgp_session


@pytest.fixture(scope="function")
def established_bgp_neighbor(bgp_session: BGPSession) -> BGPNeighbor:
    """Create a BGP neighbor in ESTABLISHED state."""
    neighbor = bgp_session.add_neighbor({"neighbor_ip": "10.0.0.2", "remote_as": 65002})

    neighbor.start()
    neighbor.tcp_connection_established()
    neighbor.receive_open(BGPOpenMessage(my_as=65002, hold_time=180, bgp_identifier="10.0.0.2"))
    neighbor.receive_keepalive()
    assert neighbor.state == BGPState.ESTABLISHED
    return neighbor


@pytest.fixture(scope="function")
def ospf_instance() -> OSPFInstance:
    """Create an OSPF instance with area 0."""
    instance = OSPFInstance(router_id="10.0.0.1")
    instance.add_area(0)
    return instance


# =============================================================================
# CONTAINER FIXTURES
# =============================================================================

@pytest.fixture(scope="function")
def bgp_container(databases: Dict[str, Any]) -> Generator[BGPContainer, None, None]:
    """
    Create and start a BGP container.

    This fixture:
    1. Creates a BGPContainer with the databases
    2. Starts the container
    3. Yields the running container
    4. Stops the container in cleanup
    """
    container = BGPContainer(databases)
    container.start()
    yield container
    container.stop()


@pytest.fixture(scope="function")
def swss_container(databases: Dict[str, Any]) -> Generator[SwssContainer, None, None]:
    """Create and start a SWSS container."""
    container = SwssContainer(databases)
    container.start()
    yield container
    container.stop()


# =============================================================================
# HAL FIXTURES
# =============================================================================

@pytest.fixture(scope="function")
def port_manager() -> PortManager:
    """Create a port manager instance."""
    return PortManager()


@pytest.fixture(scope="function")
def route_manager() -> RouteManager:
    """Create a route manager instance."""
    return RouteManager()


@pytest.fixture(scope="function")
def port_manager_with_ports() -> PortManager:
    """Create a port manager with pre-configured ports."""
    manager = PortManager()
    for i in range(1, 5):
        manager.add_port(f"Ethernet{i}", speed=100000)
    return manager


# =============================================================================
# TOPOLOGY FIXTURES
# =============================================================================

@pytest.fixture(scope="module")
def spine_leaf_topology() -> Generator[Topology, None, None]:
    """
    Create a 2-spine, 4-leaf topology.

    This fixture has module scope for efficiency - the topology
    is created once and shared across all tests in the module.
    """
    builder = TopologyBuilder.create_spine_leaf(num_spines=2, num_leaves=4)
    topology = builder.build()
    yield topology
    topology.teardown()


@pytest.fixture(scope="function")
def small_topology() -> Generator[Topology, None, None]:
    """Create a minimal 1-spine, 2-leaf topology."""
    topology = TopologyBuilder.create_spine_leaf(num_spines=1, num_leaves=2).build()
    yield topology
    topology.teardown()


# =============================================================================
# UTILITY FIXTURES
# =============================================================================

@pytest.fixture
def wait_for_bgp_convergence():
    """Factory fixture that returns a convergence waiter function."""

    def wait(neighbors: List[BGPNeighbor], timeout: float = 10.0) -> bool:
        deadline = time.monotonic() + timeout
        while True:
            if all(n.is_established for n in neighbors):
                return True
            if time.monotonic() >= deadline:
                return False
            time.sleep(0.1)

    return wait


# =============================================================================
# PARAMETERIZED FIXTURE HELPERS
# =============================================================================

# These are examples of how to create parameterized fixtures.
# You may find these patterns useful for your tests.

@pytest.fixture(params=[65001, 65100, 4200000000])
def sample_asn(request) -> int:
    """Parameterized fixture providing various AS numbers."""
    return request.param


@pytest.fixture(params=["Idle", "Connect", "Active", "OpenSent", "OpenConfirm", "Established"])
def bgp_state_name(request) -> str:
    """Parameterized fixture providing BGP state names."""
    return request.param
