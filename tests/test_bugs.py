"""Reproductions for the bugs in BUGS_FOUND.md that aren't covered in test_starter.py."""
from pathlib import Path

from mock_nos.protocols.bgp import (
    BGPAttributes,
    BGPOpenMessage,
    BGPSession,
    BGPState,
)
from mock_nos.protocols.ospf import OSPFInstance
from mock_nos.topology import TopologyBuilder
from tests.bugs import known_bug
from tests.plugins.topology_plugin import check_ports_exist

DATA = Path(__file__).resolve().parent.parent / "data"


def established(session, ip="10.0.0.2", remote_as=65002):
    n = session.add_neighbor({"neighbor_ip": ip, "remote_as": remote_as})
    n.start()
    n.tcp_connection_established()
    n.receive_open(BGPOpenMessage(my_as=remote_as, bgp_identifier=ip))
    n.receive_keepalive()
    assert n.is_established
    return n


# BGP

def test_hold_timer_expires(fake_clock):
    n = established(BGPSession("10.0.0.1", 65001))
    fake_clock.advance(179)
    assert not n.check_hold_timer()
    fake_clock.advance(2)
    assert n.check_hold_timer()
    assert n.state == BGPState.IDLE


@known_bug("BUG-002")
def test_keepalive_resets_hold_timer(fake_clock):
    n = established(BGPSession("10.0.0.1", 65001))
    fake_clock.advance(120)
    n.receive_keepalive()
    fake_clock.advance(120)
    # only 120s since the last keepalive, hold time is 180
    assert not n.check_hold_timer()
    assert n.is_established


@known_bug("BUG-008")
def test_open_with_wrong_as_rejected():
    n = BGPSession("10.0.0.1", 65001).add_neighbor({"neighbor_ip": "10.0.0.2", "remote_as": 65002})
    n.start()
    n.tcp_connection_established()
    assert not n.receive_open(BGPOpenMessage(my_as=65999, bgp_identifier="10.0.0.2"))
    assert n.state != BGPState.OPENCONFIRM


@known_bug("BUG-009")
def test_remove_neighbor_cleans_loc_rib():
    session = BGPSession("10.0.0.1", 65001)
    session.add_neighbor({"neighbor_ip": "10.0.0.3", "remote_as": 65003})
    session.receive_route("9.9.9.0/24", BGPAttributes(as_path=[65003]), "10.0.0.3")
    assert "9.9.9.0/24" in session.loc_rib

    session.remove_neighbor("10.0.0.3")
    assert "9.9.9.0/24" not in session.loc_rib


# OSPF

def ospf_segment(router_id="10.0.0.1", priority=1):
    ospf = OSPFInstance(router_id)
    ospf.add_interface("Ethernet1", f"{router_id}/24", 0, priority=priority)
    return ospf


@known_bug("BUG-006")
def test_priority_zero_router_not_elected():
    ospf = ospf_segment("10.0.0.200", priority=0)
    ospf.add_neighbor("10.0.0.2", "10.0.0.2", "Ethernet1")
    assert "10.0.0.200" not in ospf.elect_dr_bdr("Ethernet1")


@known_bug("BUG-006")
def test_priority_zero_neighbor_not_elected():
    ospf = ospf_segment()
    ospf.add_neighbor("10.0.0.250", "10.0.0.250", "Ethernet1").priority = 0
    assert "10.0.0.250" not in ospf.elect_dr_bdr("Ethernet1")


@known_bug("BUG-007")
def test_dr_tiebreak_numeric_router_id():
    ospf = ospf_segment("10.0.0.9")
    ospf.add_neighbor("10.0.0.10", "10.0.0.10", "Ethernet1")
    assert ospf.elect_dr_bdr("Ethernet1") == ("10.0.0.10", "10.0.0.9")


# Topology

@known_bug("BUG-010")
def test_load_spine_leaf_yaml():
    topo = TopologyBuilder.from_yaml(str(DATA / "topologies" / "spine_leaf.yaml")).build()
    assert len(topo.get_spines()) == 2
    assert len(topo.get_leaves()) == 4


def test_yaml_round_trip(tmp_path):
    # loader works with its own format, so BUG-010 is about the data file layout
    path = tmp_path / "topo.yaml"
    path.write_text(TopologyBuilder.create_spine_leaf(2, 2).to_yaml())
    topo = TopologyBuilder.from_yaml(str(path)).build()
    assert len(topo.devices) == 4
    assert len(topo.links) == 4


@known_bug("BUG-011")
def test_clos_links_use_real_ports():
    topo = TopologyBuilder.create_clos(tiers=3, width=2).build()
    assert check_ports_exist(topo) == []
