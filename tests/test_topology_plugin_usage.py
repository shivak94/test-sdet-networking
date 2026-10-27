"""Examples of tests using the topology plugin."""
import pytest

from mock_nos.topology import DeviceRole, TopologyBuilder


@pytest.mark.requires_topology("spine_leaf", spines=2, leaves=4)
class TestSpineLeaf:

    def test_full_mesh(self, topology):
        leaves = {leaf.name for leaf in topology.get_leaves()}
        for spine in topology.get_spines():
            assert set(spine.get_neighbors()) == leaves

    def test_all_sessions_are_ebgp(self, topology):
        for device in topology.devices.values():
            for nbr in device.bgp_neighbors:
                assert nbr["remote_as"] != device.asn

    def test_topology_is_cached(self, topology, topology_manager):
        cached = [entry[1] for entry in topology_manager.cache.values()]
        assert any(t is topology for t in cached)


@pytest.mark.requires_topology("spine_leaf", spines=1, leaves=2, scope="function")
def test_private_copy_can_be_modified(topology):
    topology.devices.pop("leaf2")
    assert len(topology.get_leaves()) == 1


@pytest.mark.requires_topology("p2p")
def test_p2p(topology):
    r1 = topology.get_device("router1")
    assert r1.role == DeviceRole.ROUTER
    assert r1.get_neighbor_on_port("Ethernet1") == "router2"


@pytest.mark.parametrize("leaves", [2, 4, 8])
def test_generated_fabrics_pass_validation(topology_manager, leaves):
    topo = TopologyBuilder.create_spine_leaf(num_spines=2, num_leaves=leaves).build()
    assert topology_manager.validate(topo) == []
