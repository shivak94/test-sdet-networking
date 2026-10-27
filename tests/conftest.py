"""
Shared pytest fixtures for NOS testing.

=============================================================================
CANDIDATE INSTRUCTIONS
=============================================================================

Complete the TODO items in this file to create reusable test fixtures.

Requirements:
1. Implement all fixtures marked with TODO
2. Follow the existing patterns for fixture design
3. Use appropriate fixture scopes (function, module, session)
4. Ensure proper cleanup in fixtures that create resources

Tips:
- Review the existing fixtures for patterns
- Use yield for fixtures that need cleanup
- Consider fixture dependencies
- Reference docs/PROTOCOL_REFERENCE.md for protocol details

=============================================================================
"""
import pytest
from typing import Any, Dict, Generator, List, Optional

from mock_nos.database import RedisMock, ConfigDB, StateDB
from mock_nos.protocols.bgp import BGPSession, BGPNeighbor, BGPState, BGPOpenMessage
from mock_nos.protocols.ospf import OSPFInstance, OSPFNeighbor, OSPFNeighborState
from mock_nos.containers import BGPContainer, SwssContainer, ContainerState
from mock_nos.hal import PortManager, RouteManager
from mock_nos.topology import TopologyBuilder, Topology, DeviceRole


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


# TODO: Implement the databases fixture
# Requirements:
# - Should return a dictionary with keys: 'config', 'state', 'redis'
# - Should depend on config_db, state_db, and redis_mock fixtures
# - The dict should map to the respective fixture instances
#
# Example usage in tests:
#   def test_something(databases):
#       config = databases['config']
#       state = databases['state']
@pytest.fixture(scope="function")
def databases(config_db: ConfigDB, state_db: StateDB, redis_mock: RedisMock) -> Dict[str, Any]:
    """Bundle all databases for container initialization."""
    # YOUR CODE HERE
    pass


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


# TODO: Implement the bgp_session_with_neighbor fixture
# Requirements:
# - Create a BGP session (can reuse bgp_session fixture)
# - Add one neighbor with:
#   - neighbor_ip: "10.0.0.2"
#   - remote_as: 65002
# - Return the BGPSession with the neighbor already added
#
# Hint: Use the add_neighbor method of BGPSession
@pytest.fixture(scope="function")
def bgp_session_with_neighbor(bgp_session: BGPSession) -> BGPSession:
    """Create a BGP session with one pre-configured neighbor."""
    # YOUR CODE HERE
    pass


# TODO: Implement the established_bgp_neighbor fixture
# Requirements:
# - Create a BGP session with a neighbor
# - Transition the neighbor to ESTABLISHED state
# - You'll need to simulate the FSM transitions:
#   1. Call neighbor.start()
#   2. Call neighbor.tcp_connection_established()
#   3. Call neighbor.receive_open() with a valid BGPOpenMessage
#   4. Call neighbor.receive_keepalive()
# - Return the BGPNeighbor that is now in ESTABLISHED state
#
# This fixture tests your understanding of BGP state machine!
@pytest.fixture(scope="function")
def established_bgp_neighbor(bgp_session: BGPSession) -> BGPNeighbor:
    """Create a BGP neighbor in ESTABLISHED state."""
    # YOUR CODE HERE
    pass


# TODO: Implement the ospf_instance fixture
# Requirements:
# - Create an OSPFInstance with router_id="10.0.0.1"
# - Add area 0 (the backbone area)
# - Return the configured instance
@pytest.fixture(scope="function")
def ospf_instance() -> OSPFInstance:
    """Create an OSPF instance with area 0."""
    # YOUR CODE HERE
    pass


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


# TODO: Implement the swss_container fixture
# Requirements:
# - Create a SwssContainer using the databases fixture
# - Start the container before yielding
# - Stop the container in cleanup (after yield)
# - Use Generator type hint: Generator[SwssContainer, None, None]
#
# Pattern: Same as bgp_container fixture above
@pytest.fixture(scope="function")
def swss_container(databases: Dict[str, Any]) -> Generator[SwssContainer, None, None]:
    """Create and start a SWSS container."""
    # YOUR CODE HERE
    pass


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


# TODO: Implement the port_manager_with_ports fixture
# Requirements:
# - Create a PortManager
# - Add 4 ports: Ethernet1, Ethernet2, Ethernet3, Ethernet4
# - All ports should have speed=100000 (100G)
# - Return the PortManager with ports configured
@pytest.fixture(scope="function")
def port_manager_with_ports() -> PortManager:
    """Create a port manager with pre-configured ports."""
    # YOUR CODE HERE
    pass


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


# TODO: Implement the small_topology fixture
# Requirements:
# - Create a simple 1-spine, 2-leaf topology using TopologyBuilder
# - Use function scope (each test gets fresh topology)
# - Remember to call build() on the builder
# - Clean up with topology.teardown() after yield
@pytest.fixture(scope="function")
def small_topology() -> Generator[Topology, None, None]:
    """Create a minimal 1-spine, 2-leaf topology."""
    # YOUR CODE HERE
    pass


# =============================================================================
# UTILITY FIXTURES
# =============================================================================

# TODO: Implement wait_for_bgp_convergence fixture
# Requirements:
# - Return a callable/function that can be used to wait for BGP convergence
# - The returned function should accept:
#   - neighbors: List[BGPNeighbor] - neighbors to check
#   - timeout: float - maximum wait time in seconds (default 10.0)
# - The function should:
#   - Poll all neighbors until they are all ESTABLISHED
#   - Return True if all converged within timeout
#   - Return False if timeout exceeded
# - Use time.sleep(0.1) between polls
#
# Example usage:
#   def test_convergence(wait_for_bgp_convergence, bgp_session):
#       # ... add neighbors and start them ...
#       result = wait_for_bgp_convergence(list(bgp_session.neighbors.values()))
#       assert result is True
@pytest.fixture
def wait_for_bgp_convergence():
    """Factory fixture that returns a convergence waiter function."""
    # YOUR CODE HERE
    # Hint: Define and return an inner function
    pass


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
