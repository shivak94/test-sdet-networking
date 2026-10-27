"""
Network device abstraction for topology building.

Provides Device and Link classes for constructing network topologies.
"""

from enum import Enum
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field


class DeviceRole(Enum):
    """Device roles in a network topology."""
    SPINE = "spine"
    LEAF = "leaf"
    BORDER_LEAF = "border_leaf"
    SUPER_SPINE = "super_spine"
    CORE = "core"
    AGGREGATION = "aggregation"
    ACCESS = "access"
    ROUTER = "router"
    HOST = "host"


@dataclass
class Link:
    """Network link between two devices."""
    device1: str
    port1: str
    device2: str
    port2: str
    network: str = ""  # Point-to-point network (e.g., "10.0.0.0/31")
    speed: int = 100000  # Mbps
    state: str = "up"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "device1": self.device1,
            "port1": self.port1,
            "device2": self.device2,
            "port2": self.port2,
            "network": self.network,
            "speed": self.speed,
            "state": self.state,
        }

    def get_other_end(self, device: str) -> Optional[tuple]:
        """Get the other end of the link from a device's perspective."""
        if device == self.device1:
            return (self.device2, self.port2)
        elif device == self.device2:
            return (self.device1, self.port1)
        return None

    def get_local_port(self, device: str) -> Optional[str]:
        """Get the local port for a device on this link."""
        if device == self.device1:
            return self.port1
        elif device == self.device2:
            return self.port2
        return None


@dataclass
class DevicePort:
    """Port on a device."""
    name: str
    speed: int = 100000
    connected_to: Optional[str] = None  # "device:port"
    ip_address: str = ""
    state: str = "up"


class Device:
    """
    Network device abstraction.

    Represents a switch, router, or host in the topology.
    """

    def __init__(
        self,
        name: str,
        role: DeviceRole,
        loopback_ip: str = "",
        asn: int = 0,
        router_id: str = "",
    ):
        """
        Initialize a network device.

        Args:
            name: Device name (e.g., "spine1", "leaf1")
            role: Device role in the topology
            loopback_ip: Loopback IP address (e.g., "10.0.0.1/32")
            asn: BGP AS number
            router_id: Router ID (defaults to loopback IP)
        """
        self.name = name
        self.role = role
        self.loopback_ip = loopback_ip
        self.asn = asn
        self.router_id = router_id or loopback_ip.split("/")[0] if loopback_ip else ""

        # Ports
        self.ports: Dict[str, DevicePort] = {}

        # Connected links
        self._links: List[Link] = []

        # Protocol state (populated when topology is built)
        self.bgp_neighbors: List[Dict[str, Any]] = []
        self.ospf_interfaces: List[Dict[str, Any]] = []

    def add_port(self, name: str, speed: int = 100000) -> DevicePort:
        """Add a port to the device."""
        port = DevicePort(name=name, speed=speed)
        self.ports[name] = port
        return port

    def get_port(self, name: str) -> Optional[DevicePort]:
        """Get a port by name."""
        return self.ports.get(name)

    def add_link(self, link: Link) -> None:
        """Register a link connected to this device."""
        self._links.append(link)

        # Update port connection info
        local_port = link.get_local_port(self.name)
        other_end = link.get_other_end(self.name)

        if local_port and other_end:
            if local_port in self.ports:
                self.ports[local_port].connected_to = f"{other_end[0]}:{other_end[1]}"

    def get_links(self) -> List[Link]:
        """Get all links connected to this device."""
        return self._links

    def get_neighbors(self) -> List[str]:
        """Get names of all connected neighbor devices."""
        neighbors = []
        for link in self._links:
            other = link.get_other_end(self.name)
            if other:
                neighbors.append(other[0])
        return neighbors

    def get_neighbor_on_port(self, port_name: str) -> Optional[str]:
        """Get the neighbor device connected to a specific port."""
        for link in self._links:
            if link.get_local_port(self.name) == port_name:
                other = link.get_other_end(self.name)
                if other:
                    return other[0]
        return None

    def configure_bgp_neighbor(
        self,
        neighbor_ip: str,
        remote_as: int,
        description: str = ""
    ) -> None:
        """Add BGP neighbor configuration."""
        self.bgp_neighbors.append({
            "neighbor_ip": neighbor_ip,
            "remote_as": remote_as,
            "description": description,
        })

    def configure_ospf_interface(
        self,
        interface: str,
        area: int,
        network_type: str = "point-to-point"
    ) -> None:
        """Add OSPF interface configuration."""
        self.ospf_interfaces.append({
            "interface": interface,
            "area": area,
            "network_type": network_type,
        })

    def to_dict(self) -> Dict[str, Any]:
        """Convert device to dictionary."""
        return {
            "name": self.name,
            "role": self.role.value,
            "loopback_ip": self.loopback_ip,
            "asn": self.asn,
            "router_id": self.router_id,
            "ports": {name: {"speed": p.speed, "connected_to": p.connected_to}
                      for name, p in self.ports.items()},
            "neighbors": self.get_neighbors(),
            "bgp_neighbors": self.bgp_neighbors,
            "ospf_interfaces": self.ospf_interfaces,
        }

    def __repr__(self) -> str:
        return f"Device(name={self.name}, role={self.role.value})"
