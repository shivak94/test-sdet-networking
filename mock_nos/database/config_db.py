"""
Configuration Database (CONFIG_DB) implementation.

CONFIG_DB stores the desired configuration state, including:
- Port configurations
- VLAN configurations
- BGP neighbor configurations
- Interface configurations
- ACL configurations

This is analogous to SONiC's CONFIG_DB Redis database.
"""

from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field
from mock_nos.database.redis_mock import RedisMock
from mock_nos.errors import ConfigError, ValidationError


@dataclass
class PortConfig:
    """Port configuration data."""
    name: str
    speed: int = 100000  # Mbps
    mtu: int = 9100
    admin_status: str = "up"
    fec: str = "none"
    description: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "speed": self.speed,
            "mtu": self.mtu,
            "admin_status": self.admin_status,
            "fec": self.fec,
            "description": self.description,
        }


@dataclass
class VlanConfig:
    """VLAN configuration data."""
    vlan_id: int
    name: str = ""
    members: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "vlan_id": self.vlan_id,
            "name": self.name or f"Vlan{self.vlan_id}",
            "members": self.members,
        }


@dataclass
class BGPNeighborConfig:
    """BGP neighbor configuration data."""
    neighbor_address: str
    remote_as: int
    description: str = ""
    hold_time: int = 180
    keepalive: int = 60
    password: str = ""
    enabled: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "neighbor_address": self.neighbor_address,
            "remote_as": self.remote_as,
            "description": self.description,
            "hold_time": self.hold_time,
            "keepalive": self.keepalive,
            "enabled": self.enabled,
        }


class ConfigDB:
    """
    Configuration database for storing desired device state.

    Tables:
        - PORT: Physical port configurations
        - VLAN: VLAN configurations
        - BGP_NEIGHBOR: BGP peer configurations
        - INTERFACE: L3 interface configurations
        - LOOPBACK: Loopback interface configurations
    """

    # Table names
    TABLE_PORT = "PORT"
    TABLE_VLAN = "VLAN"
    TABLE_BGP_NEIGHBOR = "BGP_NEIGHBOR"
    TABLE_INTERFACE = "INTERFACE"
    TABLE_LOOPBACK = "LOOPBACK"
    TABLE_BGP_GLOBAL = "BGP_GLOBAL"

    def __init__(self, redis: RedisMock = None):
        """
        Initialize CONFIG_DB.

        Args:
            redis: RedisMock instance to use, or create new one
        """
        self._redis = redis or RedisMock()

    @property
    def redis(self) -> RedisMock:
        """Get underlying Redis instance."""
        return self._redis

    def clear(self) -> None:
        """Clear all configuration data."""
        for table in [
            self.TABLE_PORT,
            self.TABLE_VLAN,
            self.TABLE_BGP_NEIGHBOR,
            self.TABLE_INTERFACE,
            self.TABLE_LOOPBACK,
            self.TABLE_BGP_GLOBAL,
        ]:
            self._redis.drop_table(table)

    # =========================================================================
    # Port Configuration
    # =========================================================================

    def add_port(self, name: str, config: Dict[str, Any] = None) -> PortConfig:
        """
        Add or update a port configuration.

        Args:
            name: Port name (e.g., "Ethernet0")
            config: Port configuration dict

        Returns:
            PortConfig object

        Raises:
            ValidationError: If configuration is invalid
        """
        config = config or {}

        # Validate port name
        if not name or not isinstance(name, str):
            raise ValidationError("Port name must be a non-empty string")

        # Validate speed if provided
        if "speed" in config:
            valid_speeds = [1000, 10000, 25000, 40000, 50000, 100000, 200000, 400000]
            if config["speed"] not in valid_speeds:
                raise ValidationError(
                    f"Invalid speed {config['speed']}. Valid speeds: {valid_speeds}"
                )

        # Validate MTU if provided
        if "mtu" in config:
            if not (68 <= config["mtu"] <= 9216):
                raise ValidationError("MTU must be between 68 and 9216")

        port_config = PortConfig(
            name=name,
            speed=config.get("speed", 100000),
            mtu=config.get("mtu", 9100),
            admin_status=config.get("admin_status", "up"),
            fec=config.get("fec", "none"),
            description=config.get("description", ""),
        )

        self._redis.hset(self.TABLE_PORT, name, port_config.to_dict())
        return port_config

    def get_port_config(self, name: str) -> Optional[Dict[str, Any]]:
        """Get port configuration by name."""
        return self._redis.hget(self.TABLE_PORT, name)

    def get_all_ports(self) -> Dict[str, Dict[str, Any]]:
        """Get all port configurations."""
        return self._redis.hgetall(self.TABLE_PORT)

    def delete_port(self, name: str) -> bool:
        """Delete a port configuration."""
        return self._redis.hdel(self.TABLE_PORT, name) > 0

    # =========================================================================
    # VLAN Configuration
    # =========================================================================

    def add_vlan(self, vlan_id: int, name: str = "", members: List[str] = None) -> VlanConfig:
        """
        Add or update a VLAN configuration.

        Args:
            vlan_id: VLAN ID (1-4094)
            name: Optional VLAN name
            members: Optional list of member ports

        Returns:
            VlanConfig object

        Raises:
            ValidationError: If VLAN ID is invalid
        """
        # BUG-001: Off-by-one error in VLAN validation
        # Should be: if vlan_id < 1 or vlan_id > 4094:
        # Bug: Uses > 4094 which is correct, but < 1 should catch 0
        # Actually the bug is: this accepts VLAN 0 because the check is vlan_id < 1
        # Wait, let me make the bug more subtle - the upper bound check
        if vlan_id < 1 or vlan_id > 4094:  # This looks correct but...
            raise ValidationError(f"VLAN ID must be between 1 and 4094, got {vlan_id}")

        # BUG-001 (actual bug): Reserved VLANs not checked
        # VLAN 1 is often reserved/default, and 4094 is sometimes reserved
        # The bug is that we DON'T validate reserved VLANs when we should
        # Let's make the bug: we reject valid VLAN 4094
        if vlan_id == 4094:
            # BUG: This incorrectly rejects VLAN 4094 which should be valid
            raise ValidationError(f"VLAN ID {vlan_id} is reserved")

        vlan_config = VlanConfig(
            vlan_id=vlan_id,
            name=name or f"Vlan{vlan_id}",
            members=members or [],
        )

        self._redis.hset(self.TABLE_VLAN, f"Vlan{vlan_id}", vlan_config.to_dict())
        return vlan_config

    def get_vlan_config(self, vlan_id: int) -> Optional[Dict[str, Any]]:
        """Get VLAN configuration by ID."""
        return self._redis.hget(self.TABLE_VLAN, f"Vlan{vlan_id}")

    def get_all_vlans(self) -> Dict[str, Dict[str, Any]]:
        """Get all VLAN configurations."""
        return self._redis.hgetall(self.TABLE_VLAN)

    def delete_vlan(self, vlan_id: int) -> bool:
        """Delete a VLAN configuration."""
        return self._redis.hdel(self.TABLE_VLAN, f"Vlan{vlan_id}") > 0

    def add_vlan_member(self, vlan_id: int, port: str, tagging: str = "tagged") -> None:
        """
        Add a port to a VLAN.

        Args:
            vlan_id: VLAN ID
            port: Port name to add
            tagging: "tagged" or "untagged"
        """
        vlan = self.get_vlan_config(vlan_id)
        if not vlan:
            raise ConfigError(f"VLAN {vlan_id} does not exist")

        member_key = f"{port}:{tagging}"
        if member_key not in vlan["members"]:
            vlan["members"].append(member_key)
            self._redis.hset(self.TABLE_VLAN, f"Vlan{vlan_id}", vlan)

    # =========================================================================
    # BGP Configuration
    # =========================================================================

    def set_bgp_global(self, local_as: int, router_id: str) -> None:
        """
        Set BGP global configuration.

        Args:
            local_as: Local AS number
            router_id: Router ID (IPv4 format)
        """
        if local_as < 1 or local_as > 4294967295:
            raise ValidationError("AS number must be between 1 and 4294967295")

        self._redis.hset(self.TABLE_BGP_GLOBAL, "config", {
            "local_as": local_as,
            "router_id": router_id,
        })

    def get_bgp_global(self) -> Optional[Dict[str, Any]]:
        """Get BGP global configuration."""
        return self._redis.hget(self.TABLE_BGP_GLOBAL, "config")

    def add_bgp_neighbor(self, config: Dict[str, Any]) -> BGPNeighborConfig:
        """
        Add or update a BGP neighbor configuration.

        Args:
            config: Neighbor configuration dict with at least:
                - neighbor_address: Peer IP address
                - remote_as: Peer AS number

        Returns:
            BGPNeighborConfig object
        """
        if "neighbor_address" not in config:
            raise ConfigError("neighbor_address is required")
        if "remote_as" not in config:
            raise ConfigError("remote_as is required")

        neighbor_config = BGPNeighborConfig(
            neighbor_address=config["neighbor_address"],
            remote_as=config["remote_as"],
            description=config.get("description", ""),
            hold_time=config.get("hold_time", 180),
            keepalive=config.get("keepalive", 60),
            password=config.get("password", ""),
            enabled=config.get("enabled", True),
        )

        self._redis.hset(
            self.TABLE_BGP_NEIGHBOR,
            config["neighbor_address"],
            neighbor_config.to_dict()
        )
        return neighbor_config

    def get_bgp_neighbor(self, address: str) -> Optional[Dict[str, Any]]:
        """Get BGP neighbor configuration by address."""
        return self._redis.hget(self.TABLE_BGP_NEIGHBOR, address)

    def get_all_bgp_neighbors(self) -> Dict[str, Dict[str, Any]]:
        """Get all BGP neighbor configurations."""
        return self._redis.hgetall(self.TABLE_BGP_NEIGHBOR)

    def delete_bgp_neighbor(self, address: str) -> bool:
        """Delete a BGP neighbor configuration."""
        return self._redis.hdel(self.TABLE_BGP_NEIGHBOR, address) > 0

    # =========================================================================
    # Interface Configuration
    # =========================================================================

    def add_interface(self, name: str, ip_address: str) -> None:
        """
        Add an IP address to an interface.

        Args:
            name: Interface name (e.g., "Ethernet0", "Vlan100")
            ip_address: IP address with prefix (e.g., "10.0.0.1/24")
        """
        if "/" not in ip_address:
            raise ValidationError("IP address must include prefix length (e.g., 10.0.0.1/24)")

        self._redis.hset(self.TABLE_INTERFACE, f"{name}|{ip_address}", {
            "interface": name,
            "ip_address": ip_address,
        })

    def get_interface_ips(self, name: str) -> List[str]:
        """Get all IP addresses configured on an interface."""
        all_interfaces = self._redis.hgetall(self.TABLE_INTERFACE)
        return [
            v["ip_address"]
            for k, v in all_interfaces.items()
            if v["interface"] == name
        ]

    # =========================================================================
    # Loopback Configuration
    # =========================================================================

    def add_loopback(self, name: str, ip_address: str) -> None:
        """
        Add a loopback interface with IP.

        Args:
            name: Loopback name (e.g., "Loopback0")
            ip_address: IP address with /32 prefix
        """
        if not name.startswith("Loopback"):
            raise ValidationError("Loopback name must start with 'Loopback'")

        self._redis.hset(self.TABLE_LOOPBACK, name, {
            "ip_address": ip_address,
        })

    def get_loopback(self, name: str) -> Optional[Dict[str, Any]]:
        """Get loopback configuration."""
        return self._redis.hget(self.TABLE_LOOPBACK, name)

    # =========================================================================
    # Bulk Operations
    # =========================================================================

    def load_config(self, config: Dict[str, Any]) -> None:
        """
        Load configuration from a dictionary.

        Args:
            config: Configuration dict with optional keys:
                - ports: List of port configs
                - vlans: List of VLAN configs
                - bgp_neighbors: List of BGP neighbor configs
                - bgp_global: BGP global config
        """
        if "bgp_global" in config:
            self.set_bgp_global(
                config["bgp_global"]["local_as"],
                config["bgp_global"]["router_id"]
            )

        for port in config.get("ports", []):
            self.add_port(port["name"], port)

        for vlan in config.get("vlans", []):
            self.add_vlan(vlan["vlan_id"], vlan.get("name"), vlan.get("members"))

        for neighbor in config.get("bgp_neighbors", []):
            self.add_bgp_neighbor(neighbor)

    def dump_config(self) -> Dict[str, Any]:
        """Dump all configuration to a dictionary."""
        return {
            "ports": self.get_all_ports(),
            "vlans": self.get_all_vlans(),
            "bgp_global": self.get_bgp_global(),
            "bgp_neighbors": self.get_all_bgp_neighbors(),
        }
