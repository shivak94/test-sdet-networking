"""
NOS test suite.

Tests that hit a known bug in mock_nos are marked with @known_bug (see
tests/bugs.py and BUGS_FOUND.md), so they show up as xfail.
"""
import random
import threading
import time
from typing import Dict

import pytest

from mock_nos.containers import BGPContainer, ContainerState, SwssContainer
from mock_nos.database import ConfigDB
from mock_nos.errors import ConfigError, TopologyError, ValidationError
from mock_nos.hal import PortManager, PortState, RouteManager, RouteType
from mock_nos.protocols.bgp import (
    BGPAttributes,
    BGPNeighbor,
    BGPOpenMessage,
    BGPSession,
    BGPState,
)
from mock_nos.protocols.ospf import OSPFDBD, OSPFHello, OSPFInstance, OSPFNeighborState
from mock_nos.topology import DeviceRole, TopologyBuilder
from tests.bugs import bug, known_bug


def bring_up(neighbor: BGPNeighbor, peer_hold_time: int = 180) -> None:
    neighbor.start()
    neighbor.tcp_connection_established()
    neighbor.receive_open(BGPOpenMessage(
        my_as=neighbor.remote_as,
        hold_time=peer_hold_time,
        bgp_identifier=neighbor.neighbor_ip,
    ))
    neighbor.receive_keepalive()


# =============================================================================
# BGP BASIC TESTS
# =============================================================================

class TestBGPBasic:
    """Basic BGP functionality tests."""

    def test_bgp_session_creation(self, bgp_session: BGPSession):
        """Verify BGP session initializes correctly."""
        assert bgp_session.router_id == "10.0.0.1"
        assert bgp_session.local_as == 65001
        assert len(bgp_session.neighbors) == 0

    def test_bgp_add_neighbor(self, bgp_session: BGPSession):
        """Verify BGP neighbor can be added."""
        neighbor = bgp_session.add_neighbor({
            "neighbor_ip": "10.0.0.2",
            "remote_as": 65002,
        })

        assert neighbor is not None
        assert neighbor.neighbor_ip == "10.0.0.2"
        assert neighbor.remote_as == 65002
        assert len(bgp_session.neighbors) == 1

    def test_bgp_neighbor_initial_state(self, bgp_session: BGPSession):
        """Verify new BGP neighbor starts in IDLE state."""
        neighbor = bgp_session.add_neighbor({
            "neighbor_ip": "10.0.0.2",
            "remote_as": 65002,
        })
        assert neighbor.state == BGPState.IDLE

    def test_bgp_state_machine_transitions(self, bgp_session_with_neighbor: BGPSession):
        """Test BGP FSM state transitions from IDLE to ESTABLISHED."""
        neighbor = bgp_session_with_neighbor.get_neighbor("10.0.0.2")
        seen = []
        neighbor.on_state_change(lambda n, old, new: seen.append(new))

        neighbor.start()
        assert neighbor.state == BGPState.CONNECT

        neighbor.tcp_connection_established()
        assert neighbor.state == BGPState.OPENSENT

        open_msg = BGPOpenMessage(my_as=65002, hold_time=90, bgp_identifier="10.0.0.2")
        assert neighbor.receive_open(open_msg)
        assert neighbor.state == BGPState.OPENCONFIRM
        assert neighbor.hold_time == 90  # min(180, 90)

        assert neighbor.receive_keepalive()
        assert neighbor.state == BGPState.ESTABLISHED
        assert neighbor.uptime is not None

        assert seen == [BGPState.CONNECT, BGPState.OPENSENT,
                        BGPState.OPENCONFIRM, BGPState.ESTABLISHED]
        assert neighbor.state_changes == 4

    def test_bgp_fsm_ignores_out_of_order_events(self, bgp_session_with_neighbor: BGPSession):
        neighbor = bgp_session_with_neighbor.get_neighbor("10.0.0.2")
        assert not neighbor.receive_open(BGPOpenMessage(my_as=65002))
        assert not neighbor.receive_keepalive()
        neighbor.tcp_connection_established()
        assert neighbor.state == BGPState.IDLE

        neighbor.start()
        neighbor.tcp_connection_failed()
        assert neighbor.state == BGPState.ACTIVE
        neighbor.tcp_connection_established()
        assert neighbor.state == BGPState.OPENSENT

        # only BGP-4 is supported
        assert not neighbor.receive_open(BGPOpenMessage(version=3, my_as=65002))
        assert neighbor.state == BGPState.OPENSENT

    def test_notification_resets_session(self, established_bgp_neighbor: BGPNeighbor):
        established_bgp_neighbor.receive_notification(error_code=6, error_subcode=2)
        assert established_bgp_neighbor.state == BGPState.IDLE
        assert established_bgp_neighbor.uptime is None

    def test_ibgp_vs_ebgp_detection(self, bgp_session: BGPSession):
        """Verify correct iBGP/eBGP classification."""
        ibgp = bgp_session.add_neighbor({"neighbor_ip": "10.0.0.3", "remote_as": 65001})
        ebgp = bgp_session.add_neighbor({"neighbor_ip": "10.0.0.2", "remote_as": 65002})

        assert ibgp.is_ibgp and not ibgp.is_ebgp
        assert ebgp.is_ebgp and not ebgp.is_ibgp

    def test_bgp_route_advertisement(self, bgp_session: BGPSession):
        """Test BGP route advertisement to RIB."""
        bgp_session.advertise_route("192.168.1.0/24")

        assert "192.168.1.0/24" in bgp_session.loc_rib
        route = bgp_session.get_best_path("192.168.1.0/24")
        assert route.best
        assert route.neighbor == "local"
        assert route.attributes.origin == "IGP"
        assert route.attributes.as_path == [65001]
        assert route.attributes.next_hop == "10.0.0.1"
        assert route.attributes.local_pref == 100

        assert bgp_session.withdraw_route("192.168.1.0/24")
        assert "192.168.1.0/24" not in bgp_session.loc_rib
        assert not bgp_session.withdraw_route("192.168.1.0/24")

    @pytest.mark.parametrize("better,worse", [
        ({"local_pref": 200, "as_path": [1, 2, 3]}, {"local_pref": 100, "as_path": [1]}),
        ({"as_path": [1]}, {"as_path": [1, 2]}),
        ({"origin": "IGP"}, {"origin": "INCOMPLETE"}),
        ({"med": 10}, {"med": 50}),
    ])
    def test_best_path_selection(self, bgp_session: BGPSession, better, worse):
        bgp_session.add_neighbor({"neighbor_ip": "10.0.0.2", "remote_as": 65002})
        bgp_session.add_neighbor({"neighbor_ip": "10.0.0.3", "remote_as": 65003})

        bgp_session.receive_route("172.16.0.0/16", BGPAttributes(**worse), "10.0.0.3")
        bgp_session.receive_route("172.16.0.0/16", BGPAttributes(**better), "10.0.0.2")

        assert bgp_session.get_best_path("172.16.0.0/16").neighbor == "10.0.0.2"


# =============================================================================
# BGP PARAMETERIZED TESTS
# =============================================================================

class TestBGPParameterized:
    """Parameterized BGP tests demonstrating pytest capabilities."""

    @pytest.mark.parametrize("asn", [1, 65535, 4294967295])
    def test_bgp_asn_range(self, asn: int, config_db: ConfigDB):
        """Test BGP session creation with various AS numbers."""
        session = BGPSession(router_id="10.0.0.1", local_as=asn)
        assert session.local_as == asn

        config_db.set_bgp_global(local_as=asn, router_id="10.0.0.1")
        assert config_db.get_bgp_global()["local_as"] == asn

    @pytest.mark.parametrize("asn", [0, -1, 4294967296])
    def test_bgp_invalid_asn(self, asn: int, config_db: ConfigDB):
        with pytest.raises(ValidationError):
            config_db.set_bgp_global(local_as=asn, router_id="10.0.0.1")

    @pytest.mark.parametrize("hold_time,expected_keepalive", [(0, 0), (90, 30), (180, 60)])
    def test_bgp_timers(self, bgp_session: BGPSession, hold_time: int, expected_keepalive: int):
        """Test BGP timer configuration."""
        neighbor = bgp_session.add_neighbor({
            "neighbor_ip": "10.0.0.2",
            "remote_as": 65002,
            "hold_time": hold_time,
        })
        bring_up(neighbor, peer_hold_time=180)

        assert neighbor.hold_time == hold_time
        assert neighbor.keepalive_interval == expected_keepalive


# =============================================================================
# OSPF TESTS
# =============================================================================

class TestOSPFBasic:
    """Basic OSPF functionality tests."""

    def test_ospf_instance_creation(self, ospf_instance: OSPFInstance):
        """Verify OSPF instance initializes correctly."""
        assert ospf_instance.router_id == "10.0.0.1"
        assert 0 in ospf_instance.areas
        assert ospf_instance.get_area(0).area_id == 0

    def test_ospf_neighbor_initial_state(self, ospf_instance: OSPFInstance):
        """Verify OSPF neighbor starts in DOWN state."""
        ospf_instance.add_interface("Ethernet1", "10.0.0.1/24", 0)
        neighbor = ospf_instance.add_neighbor("10.0.0.2", "10.0.0.2", "Ethernet1")

        assert neighbor.state == OSPFNeighborState.DOWN
        assert neighbor.area_id == 0

    def test_ospf_neighbor_on_unknown_interface(self, ospf_instance: OSPFInstance):
        with pytest.raises(ValueError):
            ospf_instance.add_neighbor("10.0.0.2", "10.0.0.2", "Ethernet9")

    def test_ospf_hello_processing(self, ospf_instance: OSPFInstance):
        """Test OSPF Hello packet processing."""
        ospf_instance.add_interface("Ethernet1", "10.0.0.1/24", 0)
        neighbor = ospf_instance.add_neighbor("10.0.0.2", "10.0.0.2", "Ethernet1")

        hello = OSPFHello(router_id="10.0.0.2", area_id=0, network_mask="255.255.255.0")
        assert neighbor.receive_hello(hello)
        assert neighbor.state == OSPFNeighborState.INIT

    def test_ospf_adjacency_to_full_and_dead_timer(self, ospf_instance: OSPFInstance, fake_clock):
        ospf_instance.add_interface("Ethernet1", "10.0.0.1/24", 0)
        nbr = ospf_instance.add_neighbor("10.0.0.2", "10.0.0.2", "Ethernet1")
        hello = OSPFHello(router_id="10.0.0.2", area_id=0, network_mask="255.255.255.0",
                          neighbors=["10.0.0.1"])

        nbr.receive_hello(hello)
        nbr.receive_hello(hello)
        assert nbr.state == OSPFNeighborState.TWO_WAY

        nbr.adjacency_decision(True)
        assert nbr.state == OSPFNeighborState.EXSTART
        nbr.receive_dbd(OSPFDBD(router_id="10.0.0.2", sequence_number=1, init=True, more=True))
        assert nbr.state == OSPFNeighborState.EXCHANGE
        nbr.receive_dbd(OSPFDBD(router_id="10.0.0.2", sequence_number=2, more=False))
        assert nbr.state == OSPFNeighborState.FULL

        # default dead interval is 40s
        fake_clock.advance(39)
        assert not nbr.check_dead_timer()
        fake_clock.advance(2)
        assert nbr.check_dead_timer()
        assert nbr.state == OSPFNeighborState.DOWN


# =============================================================================
# DATABASE TESTS
# =============================================================================

class TestDatabaseOperations:
    """Database layer tests."""

    def test_config_db_port_config(self, config_db: ConfigDB):
        """Test port configuration in CONFIG_DB."""
        config_db.add_port("Ethernet0", {
            "speed": 100000,
            "mtu": 9100,
            "admin_status": "up"
        })

        port = config_db.get_port_config("Ethernet0")
        assert port is not None
        assert port["speed"] == 100000
        assert port["mtu"] == 9100

    @pytest.mark.parametrize("vlan_id", [1, 100, bug("BUG-001", 4094)])
    def test_config_db_vlan_config(self, config_db: ConfigDB, vlan_id: int):
        """Test VLAN configuration in CONFIG_DB."""
        config_db.add_vlan(vlan_id)

        vlan = config_db.get_vlan_config(vlan_id)
        assert vlan is not None
        assert vlan["vlan_id"] == vlan_id
        assert vlan["name"] == f"Vlan{vlan_id}"

    @pytest.mark.parametrize("vlan_id", [0, 4095, -1, 5000])
    def test_config_db_invalid_vlan(self, config_db: ConfigDB, vlan_id: int):
        with pytest.raises(ValidationError):
            config_db.add_vlan(vlan_id)
        assert config_db.get_vlan_config(vlan_id) is None

    def test_config_db_bgp_neighbor(self, config_db: ConfigDB):
        """Test BGP neighbor configuration in CONFIG_DB."""
        config_db.add_bgp_neighbor({
            "neighbor_address": "10.0.0.2",
            "remote_as": 65002,
            "hold_time": 90,
        })

        neighbor = config_db.get_bgp_neighbor("10.0.0.2")
        assert neighbor["neighbor_address"] == "10.0.0.2"
        assert neighbor["remote_as"] == 65002
        assert neighbor["hold_time"] == 90
        assert neighbor["keepalive"] == 60
        assert config_db.get_bgp_neighbor("10.0.0.99") is None

    @pytest.mark.parametrize("missing", ["neighbor_address", "remote_as"])
    def test_config_db_bgp_neighbor_missing_field(self, config_db: ConfigDB, missing: str):
        cfg = {"neighbor_address": "10.0.0.2", "remote_as": 65002}
        del cfg[missing]
        with pytest.raises(ConfigError):
            config_db.add_bgp_neighbor(cfg)


# =============================================================================
# CONTAINER TESTS
# =============================================================================

class TestContainerLifecycle:
    """Container management tests."""

    def test_bgp_container_starts(self, bgp_container: BGPContainer):
        """Verify BGP container starts successfully."""
        assert bgp_container.state == ContainerState.RUNNING
        assert bgp_container.health_check() is True

    def test_bgp_container_has_session(self, bgp_container: BGPContainer):
        """Verify BGP container initializes BGP session."""
        assert bgp_container.bgp_session is not None

    def test_swss_container_starts(self, swss_container: SwssContainer):
        """Verify SWSS container starts successfully."""
        assert swss_container.state == ContainerState.RUNNING
        assert swss_container.orchagent_ready is True
        assert swss_container.health_check() is True

    def test_swss_container_stop(self, databases: Dict):
        swss = SwssContainer(databases)
        swss.start()
        assert swss.stop()
        assert swss.state == ContainerState.STOPPED
        assert not swss.orchagent_ready
        assert not swss.health_check()

    def test_container_restart(self, bgp_container: BGPContainer):
        """Test container restart behavior."""
        assert bgp_container.restart()
        assert bgp_container.state == ContainerState.RUNNING
        assert bgp_container.bgp_session is not None
        assert bgp_container.get_stats()["restart_count"] == 1

    def test_bgp_container_reads_config_db(self, databases: Dict):
        databases["config"].set_bgp_global(local_as=65010, router_id="10.10.10.10")
        databases["config"].add_bgp_neighbor({"neighbor_address": "10.0.0.2", "remote_as": 65002})

        container = BGPContainer(databases)
        container.start()
        try:
            assert container.bgp_session.local_as == 65010
            assert container.get_neighbor("10.0.0.2") is not None
        finally:
            container.stop()


# =============================================================================
# HAL TESTS
# =============================================================================

class TestPortManager:
    """Port manager tests."""

    def test_port_creation(self, port_manager: PortManager):
        """Test port creation."""
        port = port_manager.add_port("Ethernet1", speed=100000)
        assert port is not None
        assert port.name == "Ethernet1"
        assert port.speed == 100000

    def test_port_manager_with_ports(self, port_manager_with_ports: PortManager):
        ports = port_manager_with_ports.get_all_ports()
        assert sorted(ports) == ["Ethernet1", "Ethernet2", "Ethernet3", "Ethernet4"]
        assert all(p.speed == 100000 for p in ports.values())

    def test_port_counters(self, port_manager: PortManager):
        """Test port counter operations."""
        port_manager.add_port("Ethernet1")
        port_manager.increment_counter("Ethernet1", "rx_packets")
        port_manager.increment_counter("Ethernet1", "rx_packets", 41)

        counters = port_manager.get_counters("Ethernet1")
        assert counters["rx_packets"] == 42
        assert counters["tx_packets"] == 0

        assert not port_manager.increment_counter("Ethernet1", "foo")
        assert not port_manager.increment_counter("Ethernet9", "rx_packets")

        port_manager.clear_counters("Ethernet1")
        assert port_manager.get_counters("Ethernet1")["rx_packets"] == 0

    @known_bug("BUG-004")
    def test_port_counter_overflow(self, port_manager: PortManager):
        port_manager.add_port("Ethernet1")
        port_manager.increment_counter("Ethernet1", "rx_bytes", PortManager.MAX_COUNTER_VALUE)
        port_manager.increment_counter("Ethernet1", "rx_bytes", 5)
        # 64-bit counter should wrap
        assert port_manager.get_counters("Ethernet1")["rx_bytes"] == 4

    def test_port_state_transitions(self, port_manager: PortManager):
        """Test port state management."""
        port_manager.add_port("Ethernet1")
        port = port_manager.get_port("Ethernet1")

        port_manager.set_admin_state("Ethernet1", PortState.UP)
        port_manager.set_oper_state("Ethernet1", PortState.UP)
        assert port.admin_state == PortState.UP
        assert port.oper_state == PortState.UP

        port_manager.set_admin_state("Ethernet1", PortState.ADMIN_DOWN)
        assert port.oper_state == PortState.DOWN

        # link can't come up while admin down
        assert not port_manager.set_oper_state("Ethernet1", PortState.UP)
        assert port.oper_state == PortState.DOWN


class TestRouteManager:
    """Route manager tests."""

    def test_route_add_and_lookup(self, route_manager: RouteManager):
        """Test basic route operations."""
        route_manager.add_route(
            prefix="10.0.0.0/24",
            nexthop="192.168.1.1",
            route_type=RouteType.STATIC
        )

        route = route_manager.get_route("10.0.0.0/24")
        assert route is not None
        assert route["nexthop"] == "192.168.1.1"

    @pytest.mark.parametrize("ip,expected", [
        ("10.1.1.50", "10.1.1.0/24"),
        ("10.1.2.1", "10.1.0.0/16"),
        ("10.2.0.1", "10.0.0.0/8"),
        ("11.0.0.1", None),
    ])
    def test_longest_prefix_match(self, route_manager: RouteManager, ip, expected):
        """Test longest prefix match lookup."""
        route_manager.add_route("10.0.0.0/8", "1.1.1.1")
        route_manager.add_route("10.1.0.0/16", "2.2.2.2")
        route_manager.add_route("10.1.1.0/24", "3.3.3.3")

        match = route_manager.lookup(ip)
        assert (match["prefix"] if match else None) == expected

    def test_default_route(self, route_manager: RouteManager):
        route_manager.add_route("0.0.0.0/0", "9.9.9.9")
        route_manager.add_route("10.0.0.0/8", "1.1.1.1")
        assert route_manager.lookup("10.5.5.5")["nexthop"] == "1.1.1.1"
        assert route_manager.lookup("8.8.8.8")["nexthop"] == "9.9.9.9"

    def test_admin_distance(self, route_manager: RouteManager):
        route_manager.add_route("10.0.0.0/24", "1.1.1.1", route_type=RouteType.OSPF)
        route_manager.add_route("10.0.0.0/24", "2.2.2.2", route_type=RouteType.BGP)
        assert route_manager.get_route("10.0.0.0/24")["nexthop"] == "2.2.2.2"

        route_manager.delete_route("10.0.0.0/24", route_type=RouteType.BGP)
        assert route_manager.get_route("10.0.0.0/24")["nexthop"] == "1.1.1.1"

    @pytest.mark.parametrize("prefix", [
        bug("BUG-005", "10.0.0.0/33"),
        bug("BUG-005", "10.0.0.0/-1"),
        bug("BUG-005", "2001:db8::/129"),
        "10.0.0.0",
        "10.0.0.0/abc",
        "300.0.0.0/8",
        "",
    ])
    def test_route_prefix_validation(self, route_manager: RouteManager, prefix: str):
        """Test route prefix validation."""
        assert route_manager.add_route(prefix, "192.168.1.1") is False
        assert route_manager.get_stats()["total_routes"] == 0

    @pytest.mark.parametrize("prefix", ["0.0.0.0/0", "10.0.0.1/32", "::/0", "2001:db8::1/128"])
    def test_route_prefix_edges_accepted(self, route_manager: RouteManager, prefix: str):
        assert route_manager.add_route(prefix, "192.168.1.1")


# =============================================================================
# TOPOLOGY TESTS
# =============================================================================

class TestTopology:
    """Network topology tests."""

    def test_topology_device_count(self, spine_leaf_topology):
        """Verify topology has correct device count."""
        assert len(spine_leaf_topology.devices) == 6  # 2 spines + 4 leaves

    def test_spine_leaf_connectivity(self, spine_leaf_topology):
        """Verify spine-leaf topology connectivity."""
        spines = spine_leaf_topology.get_spines()
        leaves = spine_leaf_topology.get_leaves()
        spine_names = {s.name for s in spines}
        leaf_names = {leaf.name for leaf in leaves}

        for spine in spines:
            assert set(spine.get_neighbors()) == leaf_names
        for leaf in leaves:
            assert set(leaf.get_neighbors()) == spine_names

        assert len(spine_leaf_topology.links) == len(spines) * len(leaves)
        for spine in spines:
            assert len(spine.bgp_neighbors) == len(leaves)

    def test_small_topology(self, small_topology):
        assert len(small_topology.get_spines()) == 1
        assert len(small_topology.get_leaves()) == 2
        assert small_topology.validate() == []

    def test_custom_topology_creation(self):
        """Test creating a custom topology."""
        builder = TopologyBuilder("custom")
        builder.add_device("router1", DeviceRole.ROUTER, asn=65001)
        builder.add_device("router2", DeviceRole.ROUTER, asn=65002)
        link = builder.add_link("router1", "Ethernet1", "router2", "Ethernet1")
        topology = builder.build()

        assert topology.validate() == []
        assert set(topology.devices) == {"router1", "router2"}
        assert topology.get_link_between("router2", "router1") is link

        r1 = topology.get_device("router1")
        r2 = topology.get_device("router2")
        assert r1.get_neighbor_on_port("Ethernet1") == "router2"
        assert r1.ports["Ethernet1"].ip_address != r2.ports["Ethernet1"].ip_address

    def test_custom_topology_errors(self):
        builder = TopologyBuilder("bad")
        builder.add_device("router1", DeviceRole.ROUTER)
        with pytest.raises(TopologyError):
            builder.add_link("router1", "Ethernet1", "router2", "Ethernet1")
        with pytest.raises(TopologyError):
            builder.add_device("router1", DeviceRole.ROUTER)


# =============================================================================
# INTEGRATION TESTS
# =============================================================================

class TestIntegration:
    """Integration tests combining multiple components."""

    def test_bgp_end_to_end(self, bgp_container: BGPContainer, databases: Dict):
        """Test complete BGP workflow."""
        bgp_container.add_neighbor({"neighbor_ip": "10.0.0.2", "remote_as": 65002})
        assert bgp_container.simulate_neighbor_up("10.0.0.2")
        assert bgp_container.get_neighbor("10.0.0.2").state == BGPState.ESTABLISHED
        assert bgp_container.get_established_count() == 1

        # container should have pushed the state to STATE_DB
        assert databases["state"].get_bgp_neighbor_state("10.0.0.2")["state"] == "Established"

        bgp_container.advertise_route("192.168.10.0/24", local_pref=150)
        rib = bgp_container.get_rib()
        assert "192.168.10.0/24" in rib
        assert rib["192.168.10.0/24"]["attributes"]["local_pref"] == 150

        bgp_container.simulate_neighbor_down("10.0.0.2")
        assert databases["state"].get_bgp_neighbor_state("10.0.0.2")["state"] == "Idle"

        assert bgp_container.withdraw_route("192.168.10.0/24")
        assert bgp_container.get_rib() == {}

    def test_wait_for_bgp_convergence(self, bgp_session: BGPSession, wait_for_bgp_convergence):
        neighbors = [
            bgp_session.add_neighbor({"neighbor_ip": f"10.0.0.{i}", "remote_as": 65000 + i})
            for i in range(2, 5)
        ]
        timers = [threading.Timer(0.05 * i, bring_up, args=(n,)) for i, n in enumerate(neighbors)]
        for t in timers:
            t.start()

        assert wait_for_bgp_convergence(neighbors, timeout=5)
        for t in timers:
            t.join()

    def test_wait_for_bgp_convergence_timeout(self, bgp_session_with_neighbor,
                                              wait_for_bgp_convergence):
        neighbors = list(bgp_session_with_neighbor.neighbors.values())
        start = time.monotonic()
        assert not wait_for_bgp_convergence(neighbors, timeout=0.3)
        assert time.monotonic() - start >= 0.3


# =============================================================================
# BONUS CHALLENGES (Senior SDET / Team Lead)
# =============================================================================

class TestAdvanced:
    """Advanced tests for senior candidates."""

    @pytest.mark.bonus
    def test_concurrent_route_updates(self, route_manager: RouteManager):
        """Add 100 routes from 10 threads and check nothing gets lost."""
        start = threading.Barrier(10)
        errors = []

        def worker(t):
            try:
                start.wait()
                for i in range(10):
                    assert route_manager.add_route(f"10.{t}.{i}.0/24", f"192.168.{t}.1")
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker, args=(t,)) for t in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors
        stats = route_manager.get_stats()
        assert stats["total_routes"] == 100
        assert stats["active_routes"] == 100
        for t in range(10):
            for i in range(10):
                assert route_manager.get_route(f"10.{t}.{i}.0/24")["nexthop"] == f"192.168.{t}.1"

        # now everyone writes the same prefix
        start = threading.Barrier(20)

        def same_prefix(t):
            start.wait()
            route_manager.add_route("172.16.0.0/16", f"10.255.0.{t}", metric=t)

        threads = [threading.Thread(target=same_prefix, args=(t,)) for t in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        entries = route_manager.get_all_routes_for_prefix("172.16.0.0/16")
        assert len(entries) == 20
        assert sum(e["active"] for e in entries) == 1
        assert route_manager.get_route("172.16.0.0/16")["metric"] == 0

    @pytest.mark.bonus
    @known_bug("BUG-003", strict=False)
    def test_concurrent_swss_routes(self, swss_container: SwssContainer):
        """Same idea against SWSS, with a reader running at the same time."""
        done = threading.Event()
        read_errors = []

        def reader():
            while not done.is_set():
                try:
                    swss_container.get_all_routes()
                except RuntimeError as e:
                    read_errors.append(e)

        def writer(t):
            for i in range(100):
                swss_container.add_route(f"10.{t}.{i}.0/24", "192.168.0.1")

        r = threading.Thread(target=reader)
        r.start()
        writers = [threading.Thread(target=writer, args=(t,)) for t in range(10)]
        for w in writers:
            w.start()
        for w in writers:
            w.join()
        done.set()
        r.join()

        assert len(swss_container.get_all_routes()) == 1000
        assert not read_errors, f"{len(read_errors)} errors, first: {read_errors[0]!r}"

    @pytest.mark.bonus
    @pytest.mark.performance
    @pytest.mark.slow
    @known_bug("BUG-012", strict=False)
    def test_route_lookup_performance(self, route_manager: RouteManager, record_property):
        """10k routes, 1000 lookups, average must be under 1ms."""
        for i in range(10_000):
            route_manager.add_route(f"10.{i // 256}.{i % 256}.0/24", "192.168.0.1")

        rnd = random.Random(42)
        queries = []
        for _ in range(1000):
            i = rnd.randrange(10_000)
            net = f"10.{i // 256}.{i % 256}"
            queries.append((f"{net}.{rnd.randrange(1, 255)}", f"{net}.0/24"))

        # stop once we've used up the whole 1s budget, no point waiting longer
        total = 0.0
        count = 0
        for ip, expected in queries:
            t0 = time.perf_counter()
            match = route_manager.lookup(ip)
            total += time.perf_counter() - t0
            count += 1
            assert match["prefix"] == expected
            if total > 1.0:
                break

        avg_ms = total / count * 1000
        record_property("avg_lookup_ms", round(avg_ms, 3))
        assert count == 1000 and avg_ms < 1.0, f"avg {avg_ms:.2f}ms after {count} lookups"

    @pytest.mark.bonus
    def test_bgp_flap_detection(self, bgp_session: BGPSession):
        """Flap the session 10 times and check the counters."""
        neighbor = bgp_session.add_neighbor({"neighbor_ip": "10.0.0.2", "remote_as": 65002})
        flaps = []
        neighbor.on_state_change(
            lambda n, old, new: flaps.append(new) if old == BGPState.ESTABLISHED else None
        )

        for i in range(10):
            bring_up(neighbor)
            assert neighbor.is_established
            if i % 2:
                neighbor.stop()
            else:
                neighbor.receive_notification(6, 4)
            assert neighbor.state == BGPState.IDLE
            assert neighbor.uptime is None

        assert len(flaps) == 10
        # 4 transitions up + 1 down per flap
        assert neighbor.state_changes == 50

        # stopping an already idle session isn't a state change
        neighbor.stop()
        assert neighbor.state_changes == 50
