"""
Topology builder for constructing network topologies.

Supports:
- Programmatic topology construction
- YAML-based topology definitions
- Common topology patterns (spine-leaf, Clos)
"""

from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass, field
import yaml

from mock_nos.topology.device import Device, DeviceRole, Link
from mock_nos.errors import TopologyError


@dataclass
class Topology:
    """Represents a complete network topology."""
    name: str
    devices: Dict[str, Device] = field(default_factory=dict)
    links: List[Link] = field(default_factory=list)

    def get_device(self, name: str) -> Optional[Device]:
        """Get a device by name."""
        return self.devices.get(name)

    def get_devices_by_role(self, role: DeviceRole) -> List[Device]:
        """Get all devices with a specific role."""
        return [d for d in self.devices.values() if d.role == role]

    def get_spines(self) -> List[Device]:
        """Get all spine devices."""
        return self.get_devices_by_role(DeviceRole.SPINE)

    def get_leaves(self) -> List[Device]:
        """Get all leaf devices."""
        return self.get_devices_by_role(DeviceRole.LEAF)

    def get_link_between(self, device1: str, device2: str) -> Optional[Link]:
        """Get the link between two devices."""
        for link in self.links:
            if (link.device1 == device1 and link.device2 == device2) or \
               (link.device1 == device2 and link.device2 == device1):
                return link
        return None

    def validate(self) -> List[str]:
        """
        Validate the topology.

        Returns:
            List of validation errors (empty if valid)
        """
        errors = []

        # Check all links reference valid devices
        for link in self.links:
            if link.device1 not in self.devices:
                errors.append(f"Link references unknown device: {link.device1}")
            if link.device2 not in self.devices:
                errors.append(f"Link references unknown device: {link.device2}")

        # Check for duplicate links
        seen_links = set()
        for link in self.links:
            key = tuple(sorted([f"{link.device1}:{link.port1}",
                                f"{link.device2}:{link.port2}"]))
            if key in seen_links:
                errors.append(f"Duplicate link: {link.device1}:{link.port1} <-> "
                              f"{link.device2}:{link.port2}")
            seen_links.add(key)

        return errors

    def to_dict(self) -> Dict[str, Any]:
        """Convert topology to dictionary."""
        return {
            "name": self.name,
            "devices": {name: d.to_dict() for name, d in self.devices.items()},
            "links": [l.to_dict() for l in self.links],
        }

    def teardown(self) -> None:
        """Clean up topology resources."""
        self.devices.clear()
        self.links.clear()


class TopologyBuilder:
    """
    Builder for constructing network topologies.

    Usage:
        builder = TopologyBuilder("my-topology")
        builder.add_device("spine1", DeviceRole.SPINE, asn=65100)
        builder.add_device("leaf1", DeviceRole.LEAF, asn=65001)
        builder.add_link("spine1", "Ethernet1", "leaf1", "Ethernet1")
        topology = builder.build()
    """

    def __init__(self, name: str = "topology"):
        """
        Initialize topology builder.

        Args:
            name: Topology name
        """
        self.name = name
        self._devices: Dict[str, Device] = {}
        self._links: List[Link] = []

        # For IP allocation
        self._loopback_base = "10.0.0.0"
        self._loopback_counter = 1
        self._p2p_base = "10.1.0.0"
        self._p2p_counter = 0

    def add_device(
        self,
        name: str,
        role: DeviceRole,
        loopback_ip: str = None,
        asn: int = 0,
        num_ports: int = 4,
    ) -> Device:
        """
        Add a device to the topology.

        Args:
            name: Device name
            role: Device role
            loopback_ip: Loopback IP (auto-assigned if None)
            asn: BGP AS number
            num_ports: Number of Ethernet ports to create

        Returns:
            Device object
        """
        if name in self._devices:
            raise TopologyError(f"Device {name} already exists")

        # Auto-assign loopback if not provided
        if loopback_ip is None:
            loopback_ip = self._allocate_loopback()

        device = Device(
            name=name,
            role=role,
            loopback_ip=loopback_ip,
            asn=asn,
        )

        # Add default ports
        for i in range(1, num_ports + 1):
            device.add_port(f"Ethernet{i}")

        self._devices[name] = device
        return device

    def add_link(
        self,
        device1: str,
        port1: str,
        device2: str,
        port2: str,
        network: str = None,
        speed: int = 100000,
    ) -> Link:
        """
        Add a link between two devices.

        Args:
            device1: First device name
            port1: Port on first device
            device2: Second device name
            port2: Port on second device
            network: Point-to-point network (auto-assigned if None)
            speed: Link speed in Mbps

        Returns:
            Link object
        """
        if device1 not in self._devices:
            raise TopologyError(f"Device {device1} not found")
        if device2 not in self._devices:
            raise TopologyError(f"Device {device2} not found")

        # Auto-assign network if not provided
        if network is None:
            network = self._allocate_p2p_network()

        link = Link(
            device1=device1,
            port1=port1,
            device2=device2,
            port2=port2,
            network=network,
            speed=speed,
        )

        # Register link with devices
        self._devices[device1].add_link(link)
        self._devices[device2].add_link(link)

        # Configure port IPs
        if network and "/" in network:
            base_ip = network.split("/")[0]
            ip_parts = base_ip.split(".")
            ip1 = base_ip
            ip_parts[-1] = str(int(ip_parts[-1]) + 1)
            ip2 = ".".join(ip_parts)

            if port1 in self._devices[device1].ports:
                self._devices[device1].ports[port1].ip_address = f"{ip1}/31"
            if port2 in self._devices[device2].ports:
                self._devices[device2].ports[port2].ip_address = f"{ip2}/31"

        self._links.append(link)
        return link

    def _allocate_loopback(self) -> str:
        """Allocate next loopback IP."""
        ip_parts = self._loopback_base.split(".")
        ip_parts[-1] = str(self._loopback_counter)
        self._loopback_counter += 1
        return ".".join(ip_parts) + "/32"

    def _allocate_p2p_network(self) -> str:
        """Allocate next point-to-point network (/31)."""
        ip_parts = self._p2p_base.split(".")
        # Each /31 uses 2 addresses
        offset = self._p2p_counter * 2
        ip_parts[-1] = str(offset % 256)
        ip_parts[-2] = str(int(ip_parts[-2]) + offset // 256)
        self._p2p_counter += 1
        return ".".join(ip_parts) + "/31"

    def build(self) -> Topology:
        """
        Build and return the topology.

        Returns:
            Topology object
        """
        topology = Topology(
            name=self.name,
            devices=dict(self._devices),
            links=list(self._links),
        )

        # Validate
        errors = topology.validate()
        if errors:
            raise TopologyError(f"Topology validation failed: {errors}")

        return topology

    # =========================================================================
    # Factory Methods
    # =========================================================================

    @classmethod
    def create_spine_leaf(
        cls,
        num_spines: int = 2,
        num_leaves: int = 4,
        spine_asn: int = 65100,
        leaf_asn_base: int = 65001,
    ) -> 'TopologyBuilder':
        """
        Create a spine-leaf topology.

        Args:
            num_spines: Number of spine switches
            num_leaves: Number of leaf switches
            spine_asn: AS number for spines
            leaf_asn_base: Starting AS number for leaves

        Returns:
            TopologyBuilder with pre-configured spine-leaf topology
        """
        builder = cls(f"{num_spines}spine-{num_leaves}leaf")

        # Add spines
        for i in range(1, num_spines + 1):
            builder.add_device(
                f"spine{i}",
                DeviceRole.SPINE,
                asn=spine_asn,
                num_ports=num_leaves,
            )

        # Add leaves
        for i in range(1, num_leaves + 1):
            builder.add_device(
                f"leaf{i}",
                DeviceRole.LEAF,
                asn=leaf_asn_base + i - 1,
                num_ports=num_spines + 2,  # Extra ports for hosts
            )

        # Connect spines to leaves (full mesh)
        for si in range(1, num_spines + 1):
            for li in range(1, num_leaves + 1):
                builder.add_link(
                    f"spine{si}", f"Ethernet{li}",
                    f"leaf{li}", f"Ethernet{si}",
                )

        # Configure BGP neighbors
        for spine in builder._devices.values():
            if spine.role == DeviceRole.SPINE:
                for leaf in builder._devices.values():
                    if leaf.role == DeviceRole.LEAF:
                        # Get the link between them
                        for link in spine.get_links():
                            other = link.get_other_end(spine.name)
                            if other and other[0] == leaf.name:
                                # Configure BGP using link IPs
                                leaf_port = leaf.ports.get(other[1])
                                spine_port = spine.ports.get(link.get_local_port(spine.name))

                                if leaf_port and spine_port:
                                    spine.configure_bgp_neighbor(
                                        leaf_port.ip_address.split("/")[0],
                                        leaf.asn,
                                        leaf.name
                                    )
                                    leaf.configure_bgp_neighbor(
                                        spine_port.ip_address.split("/")[0],
                                        spine.asn,
                                        spine.name
                                    )

        return builder

    @classmethod
    def create_clos(
        cls,
        tiers: int = 3,
        width: int = 2,
    ) -> 'TopologyBuilder':
        """
        Create a Clos fabric topology.

        Args:
            tiers: Number of tiers (2 or 3)
            width: Number of devices per tier

        Returns:
            TopologyBuilder with pre-configured Clos topology
        """
        builder = cls(f"{tiers}tier-clos")

        if tiers == 2:
            return cls.create_spine_leaf(width, width * 2)

        # 3-tier: super-spine, spine, leaf
        asn_base = 65000

        # Super spines
        for i in range(1, width + 1):
            builder.add_device(
                f"super-spine{i}",
                DeviceRole.SUPER_SPINE,
                asn=asn_base,
                num_ports=width * 2,
            )

        # Spines
        for i in range(1, width * 2 + 1):
            builder.add_device(
                f"spine{i}",
                DeviceRole.SPINE,
                asn=asn_base + 100,
                num_ports=width * 2,
            )

        # Leaves
        for i in range(1, width * 4 + 1):
            builder.add_device(
                f"leaf{i}",
                DeviceRole.LEAF,
                asn=asn_base + 200 + i,
                num_ports=width * 2,
            )

        # Connect super-spines to spines
        for ssi in range(1, width + 1):
            for si in range(1, width * 2 + 1):
                builder.add_link(
                    f"super-spine{ssi}", f"Ethernet{si}",
                    f"spine{si}", f"Ethernet{ssi}",
                )

        # Connect spines to leaves (grouped)
        for si in range(1, width * 2 + 1):
            leaf_start = ((si - 1) // 2) * 4 + 1
            for li in range(leaf_start, min(leaf_start + 4, width * 4 + 1)):
                port_idx = (li - leaf_start) + width + 1
                builder.add_link(
                    f"spine{si}", f"Ethernet{port_idx}",
                    f"leaf{li}", f"Ethernet{((si - 1) % 2) + 1}",
                )

        return builder

    # =========================================================================
    # YAML Loading
    # =========================================================================

    @classmethod
    def from_yaml(cls, filepath: str) -> 'TopologyBuilder':
        """
        Load topology from YAML file.

        Args:
            filepath: Path to YAML file

        Returns:
            TopologyBuilder with topology from file
        """
        with open(filepath, 'r') as f:
            data = yaml.safe_load(f)

        topology_data = data.get('topology', data)
        builder = cls(topology_data.get('name', 'yaml-topology'))

        # Add devices
        for device_data in topology_data.get('devices', []):
            role = DeviceRole(device_data.get('role', 'leaf'))
            builder.add_device(
                device_data['name'],
                role,
                loopback_ip=device_data.get('loopback'),
                asn=device_data.get('asn', 0),
                num_ports=len(device_data.get('ports', [])) or 4,
            )

        # Add links
        for link_data in topology_data.get('links', []):
            endpoints = link_data.get('endpoints', [])
            if len(endpoints) == 2:
                dev1, port1 = endpoints[0].split(':')
                dev2, port2 = endpoints[1].split(':')
                builder.add_link(
                    dev1, port1,
                    dev2, port2,
                    network=link_data.get('network'),
                )

        return builder

    def to_yaml(self) -> str:
        """
        Export topology to YAML string.

        Returns:
            YAML representation of the topology
        """
        data = {
            'topology': {
                'name': self.name,
                'devices': [],
                'links': [],
            }
        }

        for device in self._devices.values():
            device_data = {
                'name': device.name,
                'role': device.role.value,
                'loopback': device.loopback_ip,
                'asn': device.asn,
                'ports': [{'name': p.name, 'speed': p.speed}
                          for p in device.ports.values()],
            }
            data['topology']['devices'].append(device_data)

        for link in self._links:
            link_data = {
                'endpoints': [
                    f"{link.device1}:{link.port1}",
                    f"{link.device2}:{link.port2}",
                ],
                'network': link.network,
            }
            data['topology']['links'].append(link_data)

        return yaml.dump(data, default_flow_style=False)
