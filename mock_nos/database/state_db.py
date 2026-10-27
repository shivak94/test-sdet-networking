"""
State Database (STATE_DB) implementation.

STATE_DB stores the current operational state of the device, including:
- Port operational status
- BGP neighbor states
- System information
- Hardware status

This is read-only from applications' perspective - updated by daemons.
"""

from typing import Any, Dict, List, Optional
from dataclasses import dataclass
from datetime import datetime
from mock_nos.database.redis_mock import RedisMock


@dataclass
class PortState:
    """Port operational state."""
    name: str
    oper_status: str  # "up" or "down"
    speed: int
    mtu: int
    mac_address: str
    link_up_count: int = 0
    link_down_count: int = 0
    last_change: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "oper_status": self.oper_status,
            "speed": self.speed,
            "mtu": self.mtu,
            "mac_address": self.mac_address,
            "link_up_count": self.link_up_count,
            "link_down_count": self.link_down_count,
            "last_change": self.last_change,
        }


@dataclass
class BGPNeighborState:
    """BGP neighbor operational state."""
    neighbor_address: str
    state: str  # "Idle", "Connect", "Active", "OpenSent", "OpenConfirm", "Established"
    remote_as: int
    local_as: int
    uptime: str = ""
    prefixes_received: int = 0
    prefixes_sent: int = 0
    messages_received: int = 0
    messages_sent: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "state": self.state,
            "remote_as": self.remote_as,
            "local_as": self.local_as,
            "uptime": self.uptime,
            "prefixes_received": self.prefixes_received,
            "prefixes_sent": self.prefixes_sent,
            "messages_received": self.messages_received,
            "messages_sent": self.messages_sent,
        }


class StateDB:
    """
    State database for storing current operational state.

    Tables:
        - PORT_STATE: Port operational status
        - BGP_NEIGHBOR_STATE: BGP peer states
        - SYSTEM_STATE: System-wide state information
        - ROUTE_STATE: RIB route states
    """

    TABLE_PORT_STATE = "PORT_STATE"
    TABLE_BGP_NEIGHBOR_STATE = "BGP_NEIGHBOR_STATE"
    TABLE_SYSTEM_STATE = "SYSTEM_STATE"
    TABLE_ROUTE_STATE = "ROUTE_STATE"

    def __init__(self, redis: RedisMock = None):
        """
        Initialize STATE_DB.

        Args:
            redis: RedisMock instance to use, or create new one
        """
        self._redis = redis or RedisMock()

    @property
    def redis(self) -> RedisMock:
        """Get underlying Redis instance."""
        return self._redis

    def clear(self) -> None:
        """Clear all state data."""
        for table in [
            self.TABLE_PORT_STATE,
            self.TABLE_BGP_NEIGHBOR_STATE,
            self.TABLE_SYSTEM_STATE,
            self.TABLE_ROUTE_STATE,
        ]:
            self._redis.drop_table(table)

    # =========================================================================
    # Port State
    # =========================================================================

    def set_port_state(
        self,
        name: str,
        oper_status: str,
        speed: int = 100000,
        mtu: int = 9100,
        mac_address: str = "",
    ) -> PortState:
        """
        Set port operational state.

        Args:
            name: Port name
            oper_status: "up" or "down"
            speed: Operational speed in Mbps
            mtu: Operational MTU
            mac_address: Port MAC address

        Returns:
            PortState object
        """
        # Get existing state to preserve counters
        existing = self._redis.hget(self.TABLE_PORT_STATE, name) or {}

        state = PortState(
            name=name,
            oper_status=oper_status,
            speed=speed,
            mtu=mtu,
            mac_address=mac_address,
            link_up_count=existing.get("link_up_count", 0),
            link_down_count=existing.get("link_down_count", 0),
            last_change=datetime.now().isoformat(),
        )

        # Update counters based on state change
        old_status = existing.get("oper_status", "down")
        if old_status != oper_status:
            if oper_status == "up":
                state.link_up_count += 1
            else:
                state.link_down_count += 1

        self._redis.hset(self.TABLE_PORT_STATE, name, state.to_dict())
        return state

    def get_port_state(self, name: str) -> Optional[Dict[str, Any]]:
        """Get port operational state."""
        return self._redis.hget(self.TABLE_PORT_STATE, name)

    def get_all_port_states(self) -> Dict[str, Dict[str, Any]]:
        """Get all port states."""
        return self._redis.hgetall(self.TABLE_PORT_STATE)

    def get_ports_by_status(self, status: str) -> List[str]:
        """Get list of ports with given operational status."""
        all_states = self.get_all_port_states()
        return [name for name, state in all_states.items() if state["oper_status"] == status]

    # =========================================================================
    # BGP Neighbor State
    # =========================================================================

    def set_bgp_neighbor_state(
        self,
        neighbor_address: str,
        state: str,
        remote_as: int,
        local_as: int,
        prefixes_received: int = 0,
        prefixes_sent: int = 0,
    ) -> BGPNeighborState:
        """
        Set BGP neighbor operational state.

        Args:
            neighbor_address: Neighbor IP address
            state: FSM state name
            remote_as: Remote AS number
            local_as: Local AS number
            prefixes_received: Number of prefixes received
            prefixes_sent: Number of prefixes sent

        Returns:
            BGPNeighborState object
        """
        existing = self._redis.hget(self.TABLE_BGP_NEIGHBOR_STATE, neighbor_address) or {}

        # Calculate uptime if transitioning to Established
        uptime = existing.get("uptime", "")
        if state == "Established" and existing.get("state") != "Established":
            uptime = datetime.now().isoformat()
        elif state != "Established":
            uptime = ""

        neighbor_state = BGPNeighborState(
            neighbor_address=neighbor_address,
            state=state,
            remote_as=remote_as,
            local_as=local_as,
            uptime=uptime,
            prefixes_received=prefixes_received,
            prefixes_sent=prefixes_sent,
            messages_received=existing.get("messages_received", 0),
            messages_sent=existing.get("messages_sent", 0),
        )

        self._redis.hset(
            self.TABLE_BGP_NEIGHBOR_STATE,
            neighbor_address,
            neighbor_state.to_dict()
        )
        return neighbor_state

    def get_bgp_neighbor_state(self, address: str) -> Optional[Dict[str, Any]]:
        """Get BGP neighbor state."""
        return self._redis.hget(self.TABLE_BGP_NEIGHBOR_STATE, address)

    def get_all_bgp_neighbor_states(self) -> Dict[str, Dict[str, Any]]:
        """Get all BGP neighbor states."""
        return self._redis.hgetall(self.TABLE_BGP_NEIGHBOR_STATE)

    def get_established_neighbors(self) -> List[str]:
        """Get list of BGP neighbors in Established state."""
        all_states = self.get_all_bgp_neighbor_states()
        return [
            addr for addr, state in all_states.items()
            if state["state"] == "Established"
        ]

    def increment_bgp_messages(
        self,
        neighbor_address: str,
        received: int = 0,
        sent: int = 0
    ) -> None:
        """Increment BGP message counters."""
        existing = self._redis.hget(self.TABLE_BGP_NEIGHBOR_STATE, neighbor_address)
        if existing:
            existing["messages_received"] = existing.get("messages_received", 0) + received
            existing["messages_sent"] = existing.get("messages_sent", 0) + sent
            self._redis.hset(self.TABLE_BGP_NEIGHBOR_STATE, neighbor_address, existing)

    # =========================================================================
    # System State
    # =========================================================================

    def set_system_state(self, key: str, value: Any) -> None:
        """Set a system state value."""
        self._redis.hset(self.TABLE_SYSTEM_STATE, key, value)

    def get_system_state(self, key: str) -> Optional[Any]:
        """Get a system state value."""
        return self._redis.hget(self.TABLE_SYSTEM_STATE, key)

    def set_system_ready(self, ready: bool = True) -> None:
        """Set system ready state."""
        self.set_system_state("system_ready", ready)
        self.set_system_state("ready_time", datetime.now().isoformat() if ready else "")

    def is_system_ready(self) -> bool:
        """Check if system is ready."""
        return self.get_system_state("system_ready") is True

    # =========================================================================
    # Route State
    # =========================================================================

    def add_route_state(
        self,
        prefix: str,
        nexthop: str,
        protocol: str,
        metric: int = 0,
        preference: int = 0,
    ) -> None:
        """
        Add a route to state database.

        Args:
            prefix: Route prefix (e.g., "10.0.0.0/24")
            nexthop: Next-hop IP address
            protocol: Protocol that installed route (e.g., "bgp", "ospf", "static")
            metric: Route metric
            preference: Administrative preference
        """
        self._redis.hset(self.TABLE_ROUTE_STATE, prefix, {
            "prefix": prefix,
            "nexthop": nexthop,
            "protocol": protocol,
            "metric": metric,
            "preference": preference,
            "installed_time": datetime.now().isoformat(),
        })

    def get_route_state(self, prefix: str) -> Optional[Dict[str, Any]]:
        """Get route state for a prefix."""
        return self._redis.hget(self.TABLE_ROUTE_STATE, prefix)

    def get_all_routes(self) -> Dict[str, Dict[str, Any]]:
        """Get all routes."""
        return self._redis.hgetall(self.TABLE_ROUTE_STATE)

    def get_routes_by_protocol(self, protocol: str) -> Dict[str, Dict[str, Any]]:
        """Get routes installed by a specific protocol."""
        all_routes = self.get_all_routes()
        return {
            prefix: route
            for prefix, route in all_routes.items()
            if route["protocol"] == protocol
        }

    def delete_route_state(self, prefix: str) -> bool:
        """Delete a route from state."""
        return self._redis.hdel(self.TABLE_ROUTE_STATE, prefix) > 0

    # =========================================================================
    # Utility Methods
    # =========================================================================

    def dump_state(self) -> Dict[str, Any]:
        """Dump all state to a dictionary."""
        return {
            "port_states": self.get_all_port_states(),
            "bgp_neighbor_states": self.get_all_bgp_neighbor_states(),
            "routes": self.get_all_routes(),
            "system_ready": self.is_system_ready(),
        }
