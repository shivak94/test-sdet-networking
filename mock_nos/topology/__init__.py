"""
Topology module for Mock NOS.

Provides utilities for constructing and managing network topologies:
    - Device: Network device abstraction
    - TopologyBuilder: Build topologies from YAML or programmatically
"""

from mock_nos.topology.device import Device, DeviceRole, Link
from mock_nos.topology.topology_builder import TopologyBuilder, Topology

__all__ = [
    "Device",
    "DeviceRole",
    "Link",
    "TopologyBuilder",
    "Topology",
]
