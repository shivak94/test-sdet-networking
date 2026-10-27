"""
BGP (Border Gateway Protocol) implementation.

This module provides a simulated BGP implementation with:
- BGP Finite State Machine (FSM)
- Neighbor management
- Basic route advertisement/withdrawal
- iBGP/eBGP detection

Reference: RFC 4271 - A Border Gateway Protocol 4 (BGP-4)
"""

from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set
from dataclasses import dataclass, field
from datetime import datetime
import time
import threading


class BGPState(Enum):
    """
    BGP Finite State Machine states.

    State transitions:
        IDLE -> CONNECT (Start event)
        CONNECT -> OPENSENT (TCP connection established, OPEN sent)
        CONNECT -> ACTIVE (TCP connection failed)
        ACTIVE -> OPENSENT (TCP connection established, OPEN sent)
        ACTIVE -> CONNECT (ConnectRetry timer expired)
        OPENSENT -> OPENCONFIRM (Valid OPEN received, KEEPALIVE sent)
        OPENCONFIRM -> ESTABLISHED (KEEPALIVE received)
        Any -> IDLE (Error or Stop event)
    """
    IDLE = "Idle"
    CONNECT = "Connect"
    ACTIVE = "Active"
    OPENSENT = "OpenSent"
    OPENCONFIRM = "OpenConfirm"
    ESTABLISHED = "Established"


@dataclass
class BGPOpenMessage:
    """BGP OPEN message structure."""
    version: int = 4
    my_as: int = 0
    hold_time: int = 180
    bgp_identifier: str = ""  # Router ID
    capabilities: List[str] = field(default_factory=list)


@dataclass
class BGPUpdateMessage:
    """BGP UPDATE message structure."""
    withdrawn_routes: List[str] = field(default_factory=list)
    path_attributes: Dict[str, Any] = field(default_factory=dict)
    nlri: List[str] = field(default_factory=list)  # Network Layer Reachability Information


@dataclass
class BGPAttributes:
    """BGP path attributes."""
    origin: str = "IGP"  # IGP, EGP, or INCOMPLETE
    as_path: List[int] = field(default_factory=list)
    next_hop: str = ""
    med: int = 0  # Multi-Exit Discriminator
    local_pref: int = 100
    communities: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "origin": self.origin,
            "as_path": self.as_path,
            "next_hop": self.next_hop,
            "med": self.med,
            "local_pref": self.local_pref,
            "communities": self.communities,
        }


@dataclass
class RouteEntry:
    """BGP route entry."""
    prefix: str
    attributes: BGPAttributes
    neighbor: str  # Source neighbor
    timestamp: float = field(default_factory=time.time)
    best: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "prefix": self.prefix,
            "attributes": self.attributes.to_dict(),
            "neighbor": self.neighbor,
            "best": self.best,
        }


class BGPNeighbor:
    """
    BGP neighbor with FSM implementation.

    This class simulates a BGP neighbor relationship including:
    - State machine transitions
    - Timer management (hold, keepalive, connect retry)
    - Message handling
    """

    def __init__(
        self,
        neighbor_ip: str,
        remote_as: int,
        local_as: int,
        local_router_id: str = "0.0.0.0",
        hold_time: int = 180,
        keepalive_interval: int = 60,
    ):
        """
        Initialize BGP neighbor.

        Args:
            neighbor_ip: Neighbor's IP address
            remote_as: Neighbor's AS number
            local_as: Local AS number
            local_router_id: Local router ID
            hold_time: Hold time in seconds (0 to disable)
            keepalive_interval: Keepalive interval in seconds
        """
        self.neighbor_ip = neighbor_ip
        self.remote_as = remote_as
        self.local_as = local_as
        self.local_router_id = local_router_id

        # Timers
        self._hold_time = hold_time
        self._keepalive_interval = keepalive_interval
        self._connect_retry_time = 30

        # State
        self._state = BGPState.IDLE
        self._uptime: Optional[datetime] = None
        self._last_state_change: datetime = datetime.now()

        # Counters
        self.prefixes_received: int = 0
        self.prefixes_sent: int = 0
        self.messages_received: int = 0
        self.messages_sent: int = 0
        self.state_changes: int = 0

        # Timer tracking
        self._last_keepalive_sent: float = 0
        self._last_keepalive_received: float = 0
        self._hold_timer_expiry: float = 0

        # Remote peer info (populated after OPEN exchange)
        self._remote_router_id: str = ""
        self._remote_hold_time: int = 0

        # Lock for thread safety
        self._lock = threading.RLock()

        # Event callbacks
        self._state_change_callbacks: List[Callable] = []

    @property
    def state(self) -> BGPState:
        """Get current FSM state."""
        return self._state

    @property
    def hold_time(self) -> int:
        """Get negotiated hold time."""
        return self._hold_time

    @property
    def keepalive_interval(self) -> int:
        """Get keepalive interval."""
        return self._keepalive_interval

    @property
    def uptime(self) -> Optional[datetime]:
        """Get session uptime (None if not Established)."""
        return self._uptime

    @property
    def uptime_seconds(self) -> int:
        """Get session uptime in seconds."""
        if self._uptime:
            return int((datetime.now() - self._uptime).total_seconds())
        return 0

    @property
    def is_established(self) -> bool:
        """Check if session is Established."""
        return self._state == BGPState.ESTABLISHED

    @property
    def is_ibgp(self) -> bool:
        """Check if this is an iBGP session."""
        return self.local_as == self.remote_as

    @property
    def is_ebgp(self) -> bool:
        """Check if this is an eBGP session."""
        return self.local_as != self.remote_as

    def _set_state(self, new_state: BGPState) -> None:
        """Internal state transition with callbacks."""
        with self._lock:
            old_state = self._state
            if old_state == new_state:
                return

            self._state = new_state
            self._last_state_change = datetime.now()
            self.state_changes += 1

            if new_state == BGPState.ESTABLISHED:
                self._uptime = datetime.now()
            elif old_state == BGPState.ESTABLISHED:
                self._uptime = None

            # Notify callbacks
            for callback in self._state_change_callbacks:
                try:
                    callback(self, old_state, new_state)
                except Exception:
                    pass

    def on_state_change(self, callback: Callable) -> None:
        """Register state change callback."""
        self._state_change_callbacks.append(callback)

    # =========================================================================
    # FSM Events
    # =========================================================================

    def start(self) -> None:
        """
        Start the BGP session (Manual Start event).

        Transitions: IDLE -> CONNECT
        """
        with self._lock:
            if self._state == BGPState.IDLE:
                self._set_state(BGPState.CONNECT)

    def stop(self) -> None:
        """
        Stop the BGP session (Manual Stop event).

        Transitions: Any -> IDLE
        """
        with self._lock:
            self._set_state(BGPState.IDLE)
            self._uptime = None

    def tcp_connection_established(self) -> None:
        """
        Handle TCP connection established event.

        Transitions:
            CONNECT -> OPENSENT
            ACTIVE -> OPENSENT
        """
        with self._lock:
            if self._state in (BGPState.CONNECT, BGPState.ACTIVE):
                self._set_state(BGPState.OPENSENT)
                self.messages_sent += 1  # OPEN message sent

    def tcp_connection_failed(self) -> None:
        """
        Handle TCP connection failed event.

        Transitions: CONNECT -> ACTIVE
        """
        with self._lock:
            if self._state == BGPState.CONNECT:
                self._set_state(BGPState.ACTIVE)

    def receive_open(self, open_msg: BGPOpenMessage) -> bool:
        """
        Handle received OPEN message.

        Args:
            open_msg: Received OPEN message

        Returns:
            True if OPEN was accepted, False otherwise

        Transitions: OPENSENT -> OPENCONFIRM
        """
        with self._lock:
            self.messages_received += 1

            if self._state != BGPState.OPENSENT:
                return False

            # Validate OPEN message
            if open_msg.version != 4:
                return False

            # Store remote peer info
            self._remote_router_id = open_msg.bgp_identifier
            self._remote_hold_time = open_msg.hold_time

            # Negotiate hold time (use smaller of the two)
            if open_msg.hold_time > 0 and self._hold_time > 0:
                self._hold_time = min(self._hold_time, open_msg.hold_time)
                # Keepalive is 1/3 of hold time
                self._keepalive_interval = self._hold_time // 3
            elif open_msg.hold_time == 0 or self._hold_time == 0:
                # Either side wants to disable hold timer
                self._hold_time = 0
                self._keepalive_interval = 0

            self._set_state(BGPState.OPENCONFIRM)
            self.messages_sent += 1  # KEEPALIVE sent
            self._last_keepalive_sent = time.time()

            return True

    def receive_keepalive(self) -> bool:
        """
        Handle received KEEPALIVE message.

        Returns:
            True if processed successfully

        Transitions: OPENCONFIRM -> ESTABLISHED
        """
        with self._lock:
            self.messages_received += 1

            if self._state == BGPState.OPENCONFIRM:
                self._set_state(BGPState.ESTABLISHED)
                self._reset_hold_timer()
                return True
            elif self._state == BGPState.ESTABLISHED:
                # BUG-002: Hold timer not properly reset on keepalive
                # Should call self._reset_hold_timer() here
                # Bug: Only updates _last_keepalive_received but not _hold_timer_expiry
                self._last_keepalive_received = time.time()
                # Missing: self._hold_timer_expiry = time.time() + self._hold_time
                return True

            return False

    def receive_update(self, update_msg: BGPUpdateMessage) -> bool:
        """
        Handle received UPDATE message.

        Args:
            update_msg: Received UPDATE message

        Returns:
            True if processed successfully
        """
        with self._lock:
            self.messages_received += 1

            if self._state != BGPState.ESTABLISHED:
                return False

            # Process withdrawn routes
            for prefix in update_msg.withdrawn_routes:
                self.prefixes_received -= 1

            # Process new routes
            for prefix in update_msg.nlri:
                self.prefixes_received += 1

            self._reset_hold_timer()
            return True

    def receive_notification(self, error_code: int, error_subcode: int) -> None:
        """
        Handle received NOTIFICATION message.

        Args:
            error_code: BGP error code
            error_subcode: BGP error subcode

        Transitions: Any -> IDLE
        """
        with self._lock:
            self.messages_received += 1
            self._set_state(BGPState.IDLE)

    def _reset_hold_timer(self) -> None:
        """Reset the hold timer."""
        self._last_keepalive_received = time.time()
        if self._hold_time > 0:
            self._hold_timer_expiry = time.time() + self._hold_time

    def check_hold_timer(self) -> bool:
        """
        Check if hold timer has expired.

        Returns:
            True if expired (session should be reset)
        """
        if self._hold_time == 0:
            return False

        with self._lock:
            if self._state == BGPState.ESTABLISHED:
                if time.time() > self._hold_timer_expiry:
                    self._set_state(BGPState.IDLE)
                    return True
            return False

    def should_send_keepalive(self) -> bool:
        """Check if it's time to send a keepalive."""
        if self._keepalive_interval == 0:
            return False

        with self._lock:
            if self._state == BGPState.ESTABLISHED:
                return time.time() - self._last_keepalive_sent >= self._keepalive_interval
            return False

    def send_keepalive(self) -> None:
        """Record that a keepalive was sent."""
        with self._lock:
            self._last_keepalive_sent = time.time()
            self.messages_sent += 1

    # =========================================================================
    # Utility Methods
    # =========================================================================

    def get_stats(self) -> Dict[str, Any]:
        """Get neighbor statistics."""
        return {
            "neighbor_ip": self.neighbor_ip,
            "remote_as": self.remote_as,
            "local_as": self.local_as,
            "state": self._state.value,
            "is_ibgp": self.is_ibgp,
            "is_ebgp": self.is_ebgp,
            "uptime_seconds": self.uptime_seconds,
            "hold_time": self._hold_time,
            "keepalive_interval": self._keepalive_interval,
            "prefixes_received": self.prefixes_received,
            "prefixes_sent": self.prefixes_sent,
            "messages_received": self.messages_received,
            "messages_sent": self.messages_sent,
            "state_changes": self.state_changes,
        }

    def __repr__(self) -> str:
        return (
            f"BGPNeighbor(ip={self.neighbor_ip}, remote_as={self.remote_as}, "
            f"state={self._state.value})"
        )


class BGPSession:
    """
    BGP routing session managing multiple neighbors.

    This class provides:
    - Neighbor management
    - Route advertisement/withdrawal
    - RIB management
    - Best path selection
    """

    def __init__(self, router_id: str, local_as: int):
        """
        Initialize BGP session.

        Args:
            router_id: Local router ID (IPv4 format)
            local_as: Local AS number
        """
        self.router_id = router_id
        self.local_as = local_as
        self.neighbors: Dict[str, BGPNeighbor] = {}

        # Routing Information Bases
        self.rib_in: Dict[str, List[RouteEntry]] = {}  # Received routes by prefix
        self.rib_out: Dict[str, RouteEntry] = {}  # Routes to advertise
        self.loc_rib: Dict[str, RouteEntry] = {}  # Local RIB (best paths)

        # Locally originated routes
        self._local_routes: Set[str] = set()

        self._lock = threading.RLock()

    def add_neighbor(self, config: Dict[str, Any]) -> BGPNeighbor:
        """
        Add a BGP neighbor.

        Args:
            config: Neighbor configuration with keys:
                - neighbor_ip: Neighbor IP address (required)
                - remote_as: Remote AS number (required)
                - hold_time: Hold time (optional, default 180)
                - keepalive: Keepalive interval (optional, default 60)

        Returns:
            BGPNeighbor object
        """
        neighbor_ip = config["neighbor_ip"]
        remote_as = config["remote_as"]

        neighbor = BGPNeighbor(
            neighbor_ip=neighbor_ip,
            remote_as=remote_as,
            local_as=self.local_as,
            local_router_id=self.router_id,
            hold_time=config.get("hold_time", 180),
            keepalive_interval=config.get("keepalive", 60),
        )

        with self._lock:
            self.neighbors[neighbor_ip] = neighbor

        return neighbor

    def remove_neighbor(self, neighbor_ip: str) -> bool:
        """Remove a BGP neighbor."""
        with self._lock:
            if neighbor_ip in self.neighbors:
                self.neighbors[neighbor_ip].stop()
                del self.neighbors[neighbor_ip]

                # Remove routes from this neighbor
                for prefix in list(self.rib_in.keys()):
                    self.rib_in[prefix] = [
                        r for r in self.rib_in[prefix]
                        if r.neighbor != neighbor_ip
                    ]
                    if not self.rib_in[prefix]:
                        del self.rib_in[prefix]

                return True
            return False

    def get_neighbor(self, neighbor_ip: str) -> Optional[BGPNeighbor]:
        """Get a neighbor by IP address."""
        return self.neighbors.get(neighbor_ip)

    def get_neighbor_summary(self) -> List[Dict[str, Any]]:
        """Get summary of all neighbors."""
        return [n.get_stats() for n in self.neighbors.values()]

    # =========================================================================
    # Route Management
    # =========================================================================

    def advertise_route(self, prefix: str, attributes: BGPAttributes = None) -> None:
        """
        Advertise a route to all neighbors.

        Args:
            prefix: Route prefix (e.g., "10.0.0.0/24")
            attributes: BGP path attributes
        """
        if attributes is None:
            attributes = BGPAttributes(
                origin="IGP",
                as_path=[self.local_as],
                next_hop=self.router_id,
            )

        route = RouteEntry(
            prefix=prefix,
            attributes=attributes,
            neighbor="local",
            best=True,
        )

        with self._lock:
            self.rib_out[prefix] = route
            self._local_routes.add(prefix)
            self.loc_rib[prefix] = route

    def withdraw_route(self, prefix: str) -> bool:
        """
        Withdraw a previously advertised route.

        Args:
            prefix: Route prefix to withdraw

        Returns:
            True if route was withdrawn
        """
        with self._lock:
            if prefix in self.rib_out:
                del self.rib_out[prefix]
                self._local_routes.discard(prefix)
                if prefix in self.loc_rib and self.loc_rib[prefix].neighbor == "local":
                    del self.loc_rib[prefix]
                return True
            return False

    def receive_route(
        self,
        prefix: str,
        attributes: BGPAttributes,
        neighbor_ip: str
    ) -> None:
        """
        Process a received route from a neighbor.

        Args:
            prefix: Route prefix
            attributes: BGP path attributes
            neighbor_ip: Source neighbor IP
        """
        route = RouteEntry(
            prefix=prefix,
            attributes=attributes,
            neighbor=neighbor_ip,
        )

        with self._lock:
            if prefix not in self.rib_in:
                self.rib_in[prefix] = []
            self.rib_in[prefix].append(route)

            # Run best path selection
            self._select_best_path(prefix)

    def withdraw_received_route(self, prefix: str, neighbor_ip: str) -> None:
        """Remove a received route from a neighbor."""
        with self._lock:
            if prefix in self.rib_in:
                self.rib_in[prefix] = [
                    r for r in self.rib_in[prefix]
                    if r.neighbor != neighbor_ip
                ]
                if not self.rib_in[prefix]:
                    del self.rib_in[prefix]

                self._select_best_path(prefix)

    def _select_best_path(self, prefix: str) -> None:
        """
        Select best path for a prefix using BGP best path algorithm.

        Selection criteria (simplified):
        1. Highest local preference
        2. Shortest AS path
        3. Lowest origin type (IGP < EGP < INCOMPLETE)
        4. Lowest MED (from same AS)
        5. eBGP over iBGP
        """
        candidates = list(self.rib_in.get(prefix, []))

        # Include local route if exists
        if prefix in self._local_routes:
            candidates.append(self.rib_out[prefix])

        if not candidates:
            self.loc_rib.pop(prefix, None)
            return

        # Mark all as non-best first
        for route in candidates:
            route.best = False

        # Sort by selection criteria
        def sort_key(route: RouteEntry):
            attr = route.attributes
            origin_val = {"IGP": 0, "EGP": 1, "INCOMPLETE": 2}.get(attr.origin, 2)
            is_ebgp = route.neighbor == "local" or (
                route.neighbor in self.neighbors and
                self.neighbors[route.neighbor].is_ebgp
            )
            return (
                -attr.local_pref,  # Higher is better
                len(attr.as_path),  # Shorter is better
                origin_val,  # Lower is better
                attr.med,  # Lower is better
                0 if is_ebgp else 1,  # eBGP preferred
            )

        candidates.sort(key=sort_key)
        best = candidates[0]
        best.best = True
        self.loc_rib[prefix] = best

    def get_routes(self, afi: str = "ipv4") -> Dict[str, Dict[str, Any]]:
        """Get all routes in local RIB."""
        return {prefix: route.to_dict() for prefix, route in self.loc_rib.items()}

    def get_best_path(self, prefix: str) -> Optional[RouteEntry]:
        """Get the best path for a prefix."""
        return self.loc_rib.get(prefix)

    def get_received_routes(self, neighbor_ip: str) -> List[Dict[str, Any]]:
        """Get all routes received from a specific neighbor."""
        routes = []
        for prefix, entries in self.rib_in.items():
            for entry in entries:
                if entry.neighbor == neighbor_ip:
                    routes.append(entry.to_dict())
        return routes

    # =========================================================================
    # Utility Methods
    # =========================================================================

    def get_stats(self) -> Dict[str, Any]:
        """Get session statistics."""
        established = sum(1 for n in self.neighbors.values() if n.is_established)
        return {
            "router_id": self.router_id,
            "local_as": self.local_as,
            "total_neighbors": len(self.neighbors),
            "established_neighbors": established,
            "total_routes": len(self.loc_rib),
            "local_routes": len(self._local_routes),
        }

    def __repr__(self) -> str:
        return f"BGPSession(router_id={self.router_id}, local_as={self.local_as})"
