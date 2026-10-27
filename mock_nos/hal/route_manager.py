"""
Route Manager for HAL layer.

Manages the Forwarding Information Base (FIB) including:
- Route installation/removal
- Next-hop resolution
- Route preference handling
"""

from enum import Enum
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass, field
import ipaddress
import threading
import time


class RouteType(Enum):
    """Route types/protocols."""
    CONNECTED = "connected"
    STATIC = "static"
    BGP = "bgp"
    OSPF = "ospf"
    ISIS = "isis"
    RIP = "rip"
    KERNEL = "kernel"


# Administrative distances (lower = more preferred)
ADMIN_DISTANCES = {
    RouteType.CONNECTED: 0,
    RouteType.STATIC: 1,
    RouteType.BGP: 20,  # eBGP
    RouteType.OSPF: 110,
    RouteType.ISIS: 115,
    RouteType.RIP: 120,
    RouteType.KERNEL: 254,
}


@dataclass
class RouteEntry:
    """FIB route entry."""
    prefix: str
    nexthop: str
    interface: str = ""
    route_type: RouteType = RouteType.STATIC
    metric: int = 0
    admin_distance: int = 0
    vrf: str = "default"
    active: bool = True
    timestamp: float = field(default_factory=time.time)

    # Multi-path support
    nexthops: List[Tuple[str, str]] = field(default_factory=list)  # [(nexthop, interface), ...]

    def __post_init__(self):
        if self.admin_distance == 0:
            self.admin_distance = ADMIN_DISTANCES.get(self.route_type, 255)

        # Add primary nexthop to nexthops list if not already there
        if self.nexthop and (self.nexthop, self.interface) not in self.nexthops:
            self.nexthops.append((self.nexthop, self.interface))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "prefix": self.prefix,
            "nexthop": self.nexthop,
            "interface": self.interface,
            "type": self.route_type.value,
            "metric": self.metric,
            "admin_distance": self.admin_distance,
            "vrf": self.vrf,
            "active": self.active,
            "nexthops": self.nexthops,
        }


class RouteManager:
    """
    HAL for route/FIB management.

    Manages the Forwarding Information Base including route
    installation, removal, and lookup.
    """

    def __init__(self):
        """Initialize route manager."""
        # Routes indexed by VRF and prefix
        # {vrf: {prefix: [RouteEntry, ...]}}
        self._routes: Dict[str, Dict[str, List[RouteEntry]]] = {"default": {}}

        self._lock = threading.RLock()

    def add_route(
        self,
        prefix: str,
        nexthop: str,
        interface: str = "",
        route_type: RouteType = RouteType.STATIC,
        metric: int = 0,
        vrf: str = "default",
    ) -> bool:
        """
        Add a route to the FIB.

        Args:
            prefix: Route prefix (e.g., "10.0.0.0/24")
            nexthop: Next-hop IP address
            interface: Outgoing interface
            route_type: Type of route
            metric: Route metric
            vrf: VRF name

        Returns:
            True if added successfully
        """
        # Validate prefix
        if not self._validate_prefix(prefix):
            return False

        entry = RouteEntry(
            prefix=prefix,
            nexthop=nexthop,
            interface=interface,
            route_type=route_type,
            metric=metric,
            vrf=vrf,
        )

        with self._lock:
            if vrf not in self._routes:
                self._routes[vrf] = {}

            if prefix not in self._routes[vrf]:
                self._routes[vrf][prefix] = []

            # Check for duplicate
            for existing in self._routes[vrf][prefix]:
                if existing.nexthop == nexthop and existing.route_type == route_type:
                    # Update existing route
                    existing.metric = metric
                    existing.interface = interface
                    existing.timestamp = time.time()
                    self._select_active_route(vrf, prefix)
                    return True

            self._routes[vrf][prefix].append(entry)
            self._select_active_route(vrf, prefix)

        return True

    def delete_route(
        self,
        prefix: str,
        nexthop: str = None,
        route_type: RouteType = None,
        vrf: str = "default",
    ) -> bool:
        """
        Delete a route from the FIB.

        Args:
            prefix: Route prefix
            nexthop: Specific next-hop to delete (or None for all)
            route_type: Specific route type to delete (or None for all)
            vrf: VRF name

        Returns:
            True if any routes were deleted
        """
        with self._lock:
            if vrf not in self._routes or prefix not in self._routes[vrf]:
                return False

            original_count = len(self._routes[vrf][prefix])

            # Filter routes to keep
            self._routes[vrf][prefix] = [
                r for r in self._routes[vrf][prefix]
                if not (
                    (nexthop is None or r.nexthop == nexthop) and
                    (route_type is None or r.route_type == route_type)
                )
            ]

            deleted = original_count - len(self._routes[vrf][prefix])

            if not self._routes[vrf][prefix]:
                del self._routes[vrf][prefix]
            else:
                self._select_active_route(vrf, prefix)

            return deleted > 0

    def get_route(self, prefix: str, vrf: str = "default") -> Optional[Dict[str, Any]]:
        """
        Get the active route for a prefix.

        Args:
            prefix: Route prefix
            vrf: VRF name

        Returns:
            Active route entry dict or None
        """
        with self._lock:
            if vrf not in self._routes or prefix not in self._routes[vrf]:
                return None

            for entry in self._routes[vrf][prefix]:
                if entry.active:
                    return entry.to_dict()

            return None

    def get_all_routes_for_prefix(
        self,
        prefix: str,
        vrf: str = "default"
    ) -> List[Dict[str, Any]]:
        """Get all routes for a prefix (including inactive)."""
        with self._lock:
            if vrf not in self._routes or prefix not in self._routes[vrf]:
                return []

            return [r.to_dict() for r in self._routes[vrf][prefix]]

    def get_all_routes(self, vrf: str = None) -> List[Dict[str, Any]]:
        """Get all active routes, optionally filtered by VRF."""
        routes = []
        with self._lock:
            for v, prefixes in self._routes.items():
                if vrf is not None and v != vrf:
                    continue
                for prefix, entries in prefixes.items():
                    for entry in entries:
                        if entry.active:
                            routes.append(entry.to_dict())
        return routes

    def get_routes_by_type(
        self,
        route_type: RouteType,
        vrf: str = None
    ) -> List[Dict[str, Any]]:
        """Get all routes of a specific type."""
        routes = []
        with self._lock:
            for v, prefixes in self._routes.items():
                if vrf is not None and v != vrf:
                    continue
                for prefix, entries in prefixes.items():
                    for entry in entries:
                        if entry.route_type == route_type:
                            routes.append(entry.to_dict())
        return routes

    def _select_active_route(self, vrf: str, prefix: str) -> None:
        """Select the active route for a prefix based on admin distance and metric."""
        if vrf not in self._routes or prefix not in self._routes[vrf]:
            return

        routes = self._routes[vrf][prefix]
        if not routes:
            return

        # Deactivate all first
        for r in routes:
            r.active = False

        # Sort by admin distance (lower better), then metric (lower better)
        routes.sort(key=lambda r: (r.admin_distance, r.metric))

        # Activate the best route
        routes[0].active = True

    def _validate_prefix(self, prefix: str) -> bool:
        """
        Validate an IP prefix.

        BUG-005: Prefix mask validation is incomplete.
        This should reject invalid masks like /33 for IPv4
        but only checks if the string format is valid.
        """
        # BUG-005: Incomplete validation
        # Should properly validate mask range (0-32 for IPv4, 0-128 for IPv6)
        try:
            parts = prefix.split("/")
            if len(parts) != 2:
                return False

            # Check if IP part is valid
            ip_part = parts[0]
            mask_part = parts[1]

            # Validate IP
            ipaddress.ip_address(ip_part)

            # BUG-005: Only checks if mask is numeric, not if it's in valid range
            # Should be: mask = int(mask_part); if mask < 0 or mask > 32: return False
            # Bug: Accepts /33, /128 for IPv4
            int(mask_part)  # Just checks it's a number, not the range

            return True

        except (ValueError, AttributeError):
            return False

    # =========================================================================
    # Lookup Operations
    # =========================================================================

    def lookup(self, ip: str, vrf: str = "default") -> Optional[Dict[str, Any]]:
        """
        Perform longest prefix match lookup.

        Args:
            ip: IP address to lookup
            vrf: VRF name

        Returns:
            Matching route or None
        """
        try:
            lookup_ip = ipaddress.ip_address(ip)
        except ValueError:
            return None

        best_match = None
        best_prefix_len = -1

        with self._lock:
            if vrf not in self._routes:
                return None

            for prefix, entries in self._routes[vrf].items():
                try:
                    network = ipaddress.ip_network(prefix, strict=False)
                    if lookup_ip in network:
                        prefix_len = network.prefixlen
                        if prefix_len > best_prefix_len:
                            # Find active route for this prefix
                            for entry in entries:
                                if entry.active:
                                    best_match = entry
                                    best_prefix_len = prefix_len
                                    break
                except ValueError:
                    continue

        return best_match.to_dict() if best_match else None

    # =========================================================================
    # ECMP (Equal Cost Multi-Path)
    # =========================================================================

    def add_nexthop(
        self,
        prefix: str,
        nexthop: str,
        interface: str = "",
        vrf: str = "default"
    ) -> bool:
        """
        Add an ECMP next-hop to an existing route.

        Args:
            prefix: Route prefix
            nexthop: Next-hop to add
            interface: Outgoing interface
            vrf: VRF name

        Returns:
            True if successful
        """
        with self._lock:
            if vrf not in self._routes or prefix not in self._routes[vrf]:
                return False

            # Find active route
            for entry in self._routes[vrf][prefix]:
                if entry.active:
                    nh_tuple = (nexthop, interface)
                    if nh_tuple not in entry.nexthops:
                        entry.nexthops.append(nh_tuple)
                    return True

        return False

    def remove_nexthop(
        self,
        prefix: str,
        nexthop: str,
        vrf: str = "default"
    ) -> bool:
        """
        Remove an ECMP next-hop from a route.

        Args:
            prefix: Route prefix
            nexthop: Next-hop to remove
            vrf: VRF name

        Returns:
            True if successful
        """
        with self._lock:
            if vrf not in self._routes or prefix not in self._routes[vrf]:
                return False

            for entry in self._routes[vrf][prefix]:
                if entry.active:
                    entry.nexthops = [
                        nh for nh in entry.nexthops
                        if nh[0] != nexthop
                    ]

                    # If no nexthops left, delete the route
                    if not entry.nexthops:
                        return self.delete_route(prefix, nexthop, entry.route_type, vrf)

                    # Update primary nexthop
                    if entry.nexthops:
                        entry.nexthop, entry.interface = entry.nexthops[0]

                    return True

        return False

    # =========================================================================
    # Statistics
    # =========================================================================

    def get_stats(self) -> Dict[str, Any]:
        """Get route manager statistics."""
        total_routes = 0
        active_routes = 0
        routes_by_type = {}

        with self._lock:
            for vrf, prefixes in self._routes.items():
                for prefix, entries in prefixes.items():
                    for entry in entries:
                        total_routes += 1
                        if entry.active:
                            active_routes += 1

                        type_name = entry.route_type.value
                        routes_by_type[type_name] = routes_by_type.get(type_name, 0) + 1

        return {
            "total_routes": total_routes,
            "active_routes": active_routes,
            "vrfs": len(self._routes),
            "routes_by_type": routes_by_type,
        }

    def clear(self, vrf: str = None) -> int:
        """
        Clear routes.

        Args:
            vrf: VRF to clear, or None for all

        Returns:
            Number of routes cleared
        """
        cleared = 0
        with self._lock:
            if vrf:
                if vrf in self._routes:
                    for entries in self._routes[vrf].values():
                        cleared += len(entries)
                    self._routes[vrf] = {}
            else:
                for v in self._routes:
                    for entries in self._routes[v].values():
                        cleared += len(entries)
                self._routes = {"default": {}}

        return cleared
