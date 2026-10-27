"""
OSPF (Open Shortest Path First) implementation.

This module provides a simulated OSPF implementation with:
- Neighbor state machine
- DR/BDR election
- Area management
- Basic LSA handling

Reference: RFC 2328 - OSPF Version 2
"""

from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set
from dataclasses import dataclass, field
from datetime import datetime
import time
import threading


class OSPFNeighborState(Enum):
    """
    OSPF neighbor state machine states.

    State transitions:
        DOWN -> INIT (Hello received)
        INIT -> 2-WAY (Hello with our ID received)
        2-WAY -> EXSTART (Adjacency decision: need to form)
        EXSTART -> EXCHANGE (DD negotiation complete)
        EXCHANGE -> LOADING (DD exchange complete, LSRs needed)
        LOADING -> FULL (All LSAs received)

    Note: On point-to-point or virtual links, skip 2-WAY -> EXSTART
    """
    DOWN = "Down"
    ATTEMPT = "Attempt"  # NBMA only
    INIT = "Init"
    TWO_WAY = "2-Way"
    EXSTART = "ExStart"
    EXCHANGE = "Exchange"
    LOADING = "Loading"
    FULL = "Full"


class OSPFNetworkType(Enum):
    """OSPF network types."""
    BROADCAST = "broadcast"
    POINT_TO_POINT = "point-to-point"
    NBMA = "nbma"
    POINT_TO_MULTIPOINT = "point-to-multipoint"


@dataclass
class OSPFHello:
    """OSPF Hello packet structure."""
    router_id: str
    area_id: int
    network_mask: str
    hello_interval: int = 10
    dead_interval: int = 40
    priority: int = 1
    dr: str = "0.0.0.0"
    bdr: str = "0.0.0.0"
    neighbors: List[str] = field(default_factory=list)


@dataclass
class OSPFDBD:
    """OSPF Database Description packet."""
    router_id: str
    sequence_number: int
    init: bool = False
    more: bool = False
    master: bool = False
    lsa_headers: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class LSA:
    """Link State Advertisement."""
    ls_type: int  # 1=Router, 2=Network, 3=Summary, 4=ASBR-Summary, 5=AS-External
    link_state_id: str
    advertising_router: str
    sequence_number: int
    age: int = 0
    data: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ls_type": self.ls_type,
            "link_state_id": self.link_state_id,
            "advertising_router": self.advertising_router,
            "sequence_number": self.sequence_number,
            "age": self.age,
            "data": self.data,
        }


class OSPFNeighbor:
    """
    OSPF neighbor with state machine implementation.

    This class simulates an OSPF neighbor relationship.
    """

    def __init__(
        self,
        neighbor_id: str,
        neighbor_ip: str,
        interface: str,
        area_id: int,
        priority: int = 1,
    ):
        """
        Initialize OSPF neighbor.

        Args:
            neighbor_id: Neighbor's router ID
            neighbor_ip: Neighbor's IP address
            interface: Local interface
            area_id: OSPF area ID
            priority: Neighbor's router priority (0-255)
        """
        self.neighbor_id = neighbor_id
        self.neighbor_ip = neighbor_ip
        self.interface = interface
        self.area_id = area_id
        self.priority = priority

        # State
        self._state = OSPFNeighborState.DOWN
        self._last_state_change: datetime = datetime.now()

        # DR/BDR info
        self.dr: str = "0.0.0.0"
        self.bdr: str = "0.0.0.0"

        # Timers
        self._dead_timer_expiry: float = 0
        self._last_hello_received: float = 0

        # DD negotiation
        self._dd_sequence_number: int = 0
        self._is_master: bool = False

        # LSA tracking
        self._pending_lsas: List[LSA] = []

        # Callbacks
        self._state_change_callbacks: List[Callable] = []

        self._lock = threading.RLock()

    @property
    def state(self) -> OSPFNeighborState:
        """Get current state."""
        return self._state

    @property
    def is_full(self) -> bool:
        """Check if adjacency is fully established."""
        return self._state == OSPFNeighborState.FULL

    def _set_state(self, new_state: OSPFNeighborState) -> None:
        """Internal state transition."""
        with self._lock:
            old_state = self._state
            if old_state == new_state:
                return

            self._state = new_state
            self._last_state_change = datetime.now()

            for callback in self._state_change_callbacks:
                try:
                    callback(self, old_state, new_state)
                except Exception:
                    pass

    def on_state_change(self, callback: Callable) -> None:
        """Register state change callback."""
        self._state_change_callbacks.append(callback)

    def receive_hello(self, hello: OSPFHello, dead_interval: int = 40) -> bool:
        """
        Process received Hello packet.

        Args:
            hello: Received Hello packet
            dead_interval: Dead interval in seconds

        Returns:
            True if Hello was processed successfully
        """
        with self._lock:
            self._last_hello_received = time.time()
            self._dead_timer_expiry = time.time() + dead_interval

            # Update DR/BDR info
            self.dr = hello.dr
            self.bdr = hello.bdr
            self.priority = hello.priority

            if self._state == OSPFNeighborState.DOWN:
                self._set_state(OSPFNeighborState.INIT)
                return True

            # Check if we're in neighbor's neighbor list (2-Way check)
            # This would be checked against our router_id
            if self._state == OSPFNeighborState.INIT:
                # Assume bidirectional for simulation
                self._set_state(OSPFNeighborState.TWO_WAY)

            return True

    def adjacency_decision(self, should_form_adjacency: bool) -> None:
        """
        Make adjacency decision after reaching 2-Way.

        Args:
            should_form_adjacency: True if adjacency should be formed
        """
        with self._lock:
            if self._state != OSPFNeighborState.TWO_WAY:
                return

            if should_form_adjacency:
                self._set_state(OSPFNeighborState.EXSTART)
                self._dd_sequence_number = int(time.time()) & 0xFFFFFFFF
            # If not forming adjacency, stay in 2-Way

    def receive_dbd(self, dbd: OSPFDBD) -> bool:
        """
        Process received Database Description packet.

        Args:
            dbd: Received DBD packet

        Returns:
            True if processed successfully
        """
        with self._lock:
            if self._state == OSPFNeighborState.EXSTART:
                # Master/slave negotiation
                self._set_state(OSPFNeighborState.EXCHANGE)
                return True

            if self._state == OSPFNeighborState.EXCHANGE:
                if not dbd.more:
                    # DD exchange complete
                    if self._pending_lsas:
                        self._set_state(OSPFNeighborState.LOADING)
                    else:
                        self._set_state(OSPFNeighborState.FULL)
                return True

            return False

    def receive_lsa(self, lsa: LSA) -> bool:
        """
        Process received LSA.

        Args:
            lsa: Received LSA

        Returns:
            True if processed
        """
        with self._lock:
            if self._state == OSPFNeighborState.LOADING:
                # Remove from pending
                self._pending_lsas = [
                    l for l in self._pending_lsas
                    if l.link_state_id != lsa.link_state_id
                ]
                if not self._pending_lsas:
                    self._set_state(OSPFNeighborState.FULL)
                return True

            if self._state == OSPFNeighborState.FULL:
                # Normal LSA update
                return True

            return False

    def check_dead_timer(self) -> bool:
        """
        Check if dead timer has expired.

        Returns:
            True if expired (neighbor should be declared down)
        """
        with self._lock:
            if self._state == OSPFNeighborState.DOWN:
                return False

            if time.time() > self._dead_timer_expiry:
                self._set_state(OSPFNeighborState.DOWN)
                return True
            return False

    def get_stats(self) -> Dict[str, Any]:
        """Get neighbor statistics."""
        return {
            "neighbor_id": self.neighbor_id,
            "neighbor_ip": self.neighbor_ip,
            "interface": self.interface,
            "area_id": self.area_id,
            "state": self._state.value,
            "priority": self.priority,
            "dr": self.dr,
            "bdr": self.bdr,
            "is_full": self.is_full,
        }

    def __repr__(self) -> str:
        return (
            f"OSPFNeighbor(id={self.neighbor_id}, ip={self.neighbor_ip}, "
            f"state={self._state.value})"
        )


@dataclass
class OSPFInterface:
    """OSPF interface configuration and state."""
    name: str
    ip_address: str
    area_id: int
    network_type: OSPFNetworkType = OSPFNetworkType.BROADCAST
    cost: int = 10
    priority: int = 1
    hello_interval: int = 10
    dead_interval: int = 40
    enabled: bool = True

    # State
    dr: str = "0.0.0.0"
    bdr: str = "0.0.0.0"


class OSPFArea:
    """OSPF area configuration and state."""

    def __init__(self, area_id: int, area_type: str = "normal"):
        """
        Initialize OSPF area.

        Args:
            area_id: Area ID (0 for backbone)
            area_type: "normal", "stub", "nssa", "totally-stubby"
        """
        self.area_id = area_id
        self.area_type = area_type
        self.interfaces: Dict[str, OSPFInterface] = {}
        self.lsdb: Dict[str, LSA] = {}  # Link State Database

    def add_interface(self, interface: OSPFInterface) -> None:
        """Add an interface to this area."""
        self.interfaces[interface.name] = interface

    def remove_interface(self, name: str) -> bool:
        """Remove an interface from this area."""
        if name in self.interfaces:
            del self.interfaces[name]
            return True
        return False

    def add_lsa(self, lsa: LSA) -> None:
        """Add or update LSA in LSDB."""
        key = f"{lsa.ls_type}:{lsa.link_state_id}:{lsa.advertising_router}"
        self.lsdb[key] = lsa

    def get_lsdb(self) -> List[Dict[str, Any]]:
        """Get all LSAs in LSDB."""
        return [lsa.to_dict() for lsa in self.lsdb.values()]


class OSPFInstance:
    """
    OSPF routing instance.

    This class provides:
    - Area management
    - Interface management
    - Neighbor management
    - DR/BDR election
    """

    def __init__(self, router_id: str):
        """
        Initialize OSPF instance.

        Args:
            router_id: Router ID (IPv4 format)
        """
        self.router_id = router_id
        self.areas: Dict[int, OSPFArea] = {}
        self.neighbors: Dict[str, OSPFNeighbor] = {}
        self.interfaces: Dict[str, OSPFInterface] = {}

        self._lock = threading.RLock()

    def add_area(self, area_id: int, area_type: str = "normal") -> OSPFArea:
        """
        Add an OSPF area.

        Args:
            area_id: Area ID (0 for backbone)
            area_type: Area type

        Returns:
            OSPFArea object
        """
        with self._lock:
            area = OSPFArea(area_id, area_type)
            self.areas[area_id] = area
            return area

    def get_area(self, area_id: int) -> Optional[OSPFArea]:
        """Get an area by ID."""
        return self.areas.get(area_id)

    def add_interface(
        self,
        name: str,
        ip_address: str,
        area_id: int,
        **kwargs
    ) -> OSPFInterface:
        """
        Add an interface to OSPF.

        Args:
            name: Interface name
            ip_address: Interface IP with mask
            area_id: Area ID
            **kwargs: Additional interface options

        Returns:
            OSPFInterface object
        """
        with self._lock:
            if area_id not in self.areas:
                self.add_area(area_id)

            interface = OSPFInterface(
                name=name,
                ip_address=ip_address,
                area_id=area_id,
                network_type=kwargs.get("network_type", OSPFNetworkType.BROADCAST),
                cost=kwargs.get("cost", 10),
                priority=kwargs.get("priority", 1),
                hello_interval=kwargs.get("hello_interval", 10),
                dead_interval=kwargs.get("dead_interval", 40),
            )

            self.interfaces[name] = interface
            self.areas[area_id].add_interface(interface)
            return interface

    def add_neighbor(
        self,
        neighbor_id: str,
        neighbor_ip: str,
        interface: str,
    ) -> OSPFNeighbor:
        """
        Add/discover an OSPF neighbor.

        Args:
            neighbor_id: Neighbor's router ID
            neighbor_ip: Neighbor's IP address
            interface: Local interface name

        Returns:
            OSPFNeighbor object
        """
        with self._lock:
            if interface not in self.interfaces:
                raise ValueError(f"Interface {interface} not configured for OSPF")

            intf = self.interfaces[interface]
            neighbor = OSPFNeighbor(
                neighbor_id=neighbor_id,
                neighbor_ip=neighbor_ip,
                interface=interface,
                area_id=intf.area_id,
            )

            self.neighbors[neighbor_ip] = neighbor
            return neighbor

    def get_neighbor(self, neighbor_ip: str) -> Optional[OSPFNeighbor]:
        """Get neighbor by IP."""
        return self.neighbors.get(neighbor_ip)

    def get_neighbors_by_state(self, state: OSPFNeighborState) -> List[OSPFNeighbor]:
        """Get all neighbors in a specific state."""
        return [n for n in self.neighbors.values() if n.state == state]

    def get_full_neighbors(self) -> List[OSPFNeighbor]:
        """Get all neighbors with full adjacency."""
        return self.get_neighbors_by_state(OSPFNeighborState.FULL)

    # =========================================================================
    # DR/BDR Election
    # =========================================================================

    def elect_dr_bdr(self, interface: str) -> tuple:
        """
        Perform DR/BDR election for an interface.

        Args:
            interface: Interface name

        Returns:
            Tuple of (DR router_id, BDR router_id)
        """
        with self._lock:
            if interface not in self.interfaces:
                return ("0.0.0.0", "0.0.0.0")

            intf = self.interfaces[interface]

            # Only broadcast and NBMA networks elect DR/BDR
            if intf.network_type not in (
                OSPFNetworkType.BROADCAST,
                OSPFNetworkType.NBMA
            ):
                return ("0.0.0.0", "0.0.0.0")

            # Gather candidates (ourselves + neighbors on this interface)
            candidates = []

            # Add ourselves
            # BUG-006: Priority 0 routers should NOT participate in DR election
            # Bug: We don't check if priority is 0 before adding ourselves
            candidates.append({
                "router_id": self.router_id,
                "priority": intf.priority,
                "ip": intf.ip_address.split("/")[0] if "/" in intf.ip_address else intf.ip_address,
            })

            # Add neighbors on this interface
            for neighbor in self.neighbors.values():
                if neighbor.interface == interface:
                    # BUG-006: Should skip neighbors with priority 0
                    # Missing: if neighbor.priority == 0: continue
                    candidates.append({
                        "router_id": neighbor.neighbor_id,
                        "priority": neighbor.priority,
                        "ip": neighbor.neighbor_ip,
                    })

            if not candidates:
                return ("0.0.0.0", "0.0.0.0")

            # Sort by priority (descending), then router_id (descending)
            # Higher priority wins, ties broken by higher router ID
            candidates.sort(key=lambda x: (x["priority"], x["router_id"]), reverse=True)

            dr = candidates[0]["router_id"] if candidates else "0.0.0.0"
            bdr = candidates[1]["router_id"] if len(candidates) > 1 else "0.0.0.0"

            # Update interface
            intf.dr = dr
            intf.bdr = bdr

            return (dr, bdr)

    # =========================================================================
    # Route Calculation
    # =========================================================================

    def get_routes(self) -> List[Dict[str, Any]]:
        """
        Get OSPF routes (simplified SPF result).

        Returns:
            List of route dictionaries
        """
        routes = []

        # In a real implementation, this would run SPF
        # For simulation, we return routes based on LSAs

        for area in self.areas.values():
            for lsa in area.lsdb.values():
                if lsa.ls_type == 1:  # Router LSA
                    for link in lsa.data.get("links", []):
                        routes.append({
                            "prefix": link.get("prefix", ""),
                            "nexthop": lsa.advertising_router,
                            "metric": link.get("metric", 10),
                            "area": area.area_id,
                            "type": "intra-area",
                        })

        return routes

    # =========================================================================
    # Utility Methods
    # =========================================================================

    def get_stats(self) -> Dict[str, Any]:
        """Get OSPF instance statistics."""
        full_count = len(self.get_full_neighbors())
        return {
            "router_id": self.router_id,
            "areas": len(self.areas),
            "interfaces": len(self.interfaces),
            "total_neighbors": len(self.neighbors),
            "full_neighbors": full_count,
        }

    def get_neighbor_summary(self) -> List[Dict[str, Any]]:
        """Get summary of all neighbors."""
        return [n.get_stats() for n in self.neighbors.values()]

    def __repr__(self) -> str:
        return f"OSPFInstance(router_id={self.router_id})"
