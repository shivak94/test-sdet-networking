"""
Switch State Service (SWSS) container mock.

Simulates the SWSS container in SONiC, which runs the orchagent
and handles the synchronization between application databases
and the ASIC database.
"""

from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime
import threading
import time

from mock_nos.containers.base_container import BaseContainer, ContainerState
from mock_nos.errors import ContainerError


@dataclass
class RouteEntry:
    """Route entry for SWSS processing."""
    prefix: str
    nexthop: str
    interface: str = ""
    vrf: str = "default"
    protocol: str = "static"
    timestamp: float = field(default_factory=time.time)


@dataclass
class FDBEntry:
    """FDB entry for SWSS processing."""
    mac: str
    vlan: int
    port: str
    entry_type: str = "dynamic"  # "static" or "dynamic"
    timestamp: float = field(default_factory=time.time)


@dataclass
class NeighborEntry:
    """Neighbor (ARP/ND) entry."""
    ip_address: str
    mac_address: str
    interface: str
    family: str = "IPv4"  # "IPv4" or "IPv6"
    state: str = "reachable"
    timestamp: float = field(default_factory=time.time)


class SwssContainer(BaseContainer):
    """
    Switch State Service container mock.

    This container manages:
    - Route synchronization (APPL_DB -> ASIC_DB)
    - FDB synchronization
    - Neighbor table management
    - Port state management

    In SONiC, SWSS contains orchagent which orchestrates the
    synchronization between application state and hardware state.
    """

    def __init__(self, databases: Dict[str, Any]):
        """
        Initialize SWSS container.

        Args:
            databases: Dict with database instances
        """
        super().__init__("swss", databases)

        # Internal state (simulating ASIC_DB)
        self._route_table: Dict[str, RouteEntry] = {}
        self._fdb_table: Dict[Tuple[str, int], FDBEntry] = {}  # (mac, vlan) -> entry
        self._neighbor_table: Dict[str, NeighborEntry] = {}  # ip -> entry

        # Orchagent ready flag
        self.orchagent_ready: bool = False

        # Processing queue
        self._pending_updates: List[Dict[str, Any]] = []

        # BUG-003: No lock for _route_table access
        # This should use self._lock but doesn't in _sync_to_asic
        # causing potential race conditions

    def _on_start(self) -> None:
        """Initialize SWSS."""
        self._log("Starting orchagent...")

        # Clear internal state
        self._route_table.clear()
        self._fdb_table.clear()
        self._neighbor_table.clear()
        self._pending_updates.clear()

        # Simulate orchagent initialization delay
        time.sleep(0.05)

        self.orchagent_ready = True
        self._log("Orchagent ready")

    def _on_stop(self) -> None:
        """Clean up SWSS."""
        self._log("Stopping orchagent...")
        self.orchagent_ready = False

    def health_check(self) -> bool:
        """Check if SWSS is healthy."""
        if self._state != ContainerState.RUNNING:
            return False

        return self.orchagent_ready

    # =========================================================================
    # Route Management
    # =========================================================================

    def add_route(
        self,
        prefix: str,
        nexthop: str,
        interface: str = "",
        vrf: str = "default"
    ) -> bool:
        """
        Add a route to the routing table.

        Args:
            prefix: Route prefix (e.g., "10.0.0.0/24")
            nexthop: Next-hop IP address
            interface: Outgoing interface
            vrf: VRF name

        Returns:
            True if added successfully
        """
        if not self.orchagent_ready:
            raise ContainerError("Orchagent not ready")

        entry = RouteEntry(
            prefix=prefix,
            nexthop=nexthop,
            interface=interface,
            vrf=vrf,
        )

        # Sync to ASIC (this has a bug)
        self._sync_route_to_asic(entry)

        self._log(f"Route added: {prefix} via {nexthop}")
        return True

    def delete_route(self, prefix: str, vrf: str = "default") -> bool:
        """Delete a route from the routing table."""
        if not self.orchagent_ready:
            raise ContainerError("Orchagent not ready")

        key = f"{vrf}:{prefix}"
        if key in self._route_table:
            del self._route_table[key]
            self._log(f"Route deleted: {prefix}")
            return True
        return False

    def get_route(self, prefix: str, vrf: str = "default") -> Optional[Dict[str, Any]]:
        """Get a route by prefix."""
        key = f"{vrf}:{prefix}"
        entry = self._route_table.get(key)
        if entry:
            return {
                "prefix": entry.prefix,
                "nexthop": entry.nexthop,
                "interface": entry.interface,
                "vrf": entry.vrf,
            }
        return None

    def get_all_routes(self, vrf: str = None) -> List[Dict[str, Any]]:
        """Get all routes, optionally filtered by VRF."""
        routes = []
        for key, entry in self._route_table.items():
            if vrf is None or entry.vrf == vrf:
                routes.append({
                    "prefix": entry.prefix,
                    "nexthop": entry.nexthop,
                    "interface": entry.interface,
                    "vrf": entry.vrf,
                })
        return routes

    def _sync_route_to_asic(self, entry: RouteEntry) -> None:
        """
        Sync route to ASIC database.

        BUG-003: Race condition - this method doesn't use locking
        when modifying _route_table, which can cause issues with
        concurrent updates.
        """
        # BUG-003: Missing lock acquisition
        # Should be: with self._lock:
        # Simulating async processing without proper synchronization
        time.sleep(0.001)  # Simulate async delay

        # This write is not protected by a lock
        key = f"{entry.vrf}:{entry.prefix}"
        self._route_table[key] = entry

        # In a correct implementation, we would do:
        # with self._lock:
        #     self._route_table[key] = entry

    # =========================================================================
    # FDB Management
    # =========================================================================

    def add_fdb_entry(
        self,
        mac: str,
        vlan: int,
        port: str,
        entry_type: str = "dynamic"
    ) -> bool:
        """
        Add an FDB entry.

        Args:
            mac: MAC address
            vlan: VLAN ID
            port: Port name
            entry_type: "static" or "dynamic"

        Returns:
            True if added
        """
        if not self.orchagent_ready:
            raise ContainerError("Orchagent not ready")

        entry = FDBEntry(
            mac=mac.lower(),
            vlan=vlan,
            port=port,
            entry_type=entry_type,
        )

        with self._lock:
            self._fdb_table[(mac.lower(), vlan)] = entry

        self._log(f"FDB entry added: {mac} on VLAN {vlan} port {port}")
        return True

    def delete_fdb_entry(self, mac: str, vlan: int) -> bool:
        """Delete an FDB entry."""
        with self._lock:
            key = (mac.lower(), vlan)
            if key in self._fdb_table:
                del self._fdb_table[key]
                self._log(f"FDB entry deleted: {mac} on VLAN {vlan}")
                return True
        return False

    def get_fdb_entry(self, mac: str, vlan: int) -> Optional[Dict[str, Any]]:
        """Get an FDB entry."""
        with self._lock:
            entry = self._fdb_table.get((mac.lower(), vlan))
            if entry:
                return {
                    "mac": entry.mac,
                    "vlan": entry.vlan,
                    "port": entry.port,
                    "type": entry.entry_type,
                }
        return None

    def get_fdb_by_vlan(self, vlan: int) -> List[Dict[str, Any]]:
        """Get all FDB entries for a VLAN."""
        entries = []
        with self._lock:
            for (mac, vid), entry in self._fdb_table.items():
                if vid == vlan:
                    entries.append({
                        "mac": entry.mac,
                        "vlan": entry.vlan,
                        "port": entry.port,
                        "type": entry.entry_type,
                    })
        return entries

    def flush_fdb(self, vlan: int = None, port: str = None) -> int:
        """
        Flush FDB entries.

        Args:
            vlan: Optional VLAN to flush
            port: Optional port to flush

        Returns:
            Number of entries flushed
        """
        flushed = 0
        with self._lock:
            keys_to_delete = []
            for key, entry in self._fdb_table.items():
                if entry.entry_type != "static":  # Don't flush static entries
                    if vlan is None or entry.vlan == vlan:
                        if port is None or entry.port == port:
                            keys_to_delete.append(key)

            for key in keys_to_delete:
                del self._fdb_table[key]
                flushed += 1

        self._log(f"Flushed {flushed} FDB entries")
        return flushed

    # =========================================================================
    # Neighbor Table Management
    # =========================================================================

    def add_neighbor(
        self,
        ip_address: str,
        mac_address: str,
        interface: str,
        family: str = "IPv4"
    ) -> bool:
        """
        Add a neighbor (ARP/ND) entry.

        Args:
            ip_address: IP address
            mac_address: MAC address
            interface: Interface name
            family: "IPv4" or "IPv6"

        Returns:
            True if added
        """
        if not self.orchagent_ready:
            raise ContainerError("Orchagent not ready")

        entry = NeighborEntry(
            ip_address=ip_address,
            mac_address=mac_address.lower(),
            interface=interface,
            family=family,
        )

        with self._lock:
            self._neighbor_table[ip_address] = entry

        self._log(f"Neighbor added: {ip_address} -> {mac_address}")
        return True

    def delete_neighbor(self, ip_address: str) -> bool:
        """Delete a neighbor entry."""
        with self._lock:
            if ip_address in self._neighbor_table:
                del self._neighbor_table[ip_address]
                self._log(f"Neighbor deleted: {ip_address}")
                return True
        return False

    def get_neighbor(self, ip_address: str) -> Optional[Dict[str, Any]]:
        """Get a neighbor entry."""
        with self._lock:
            entry = self._neighbor_table.get(ip_address)
            if entry:
                return {
                    "ip_address": entry.ip_address,
                    "mac_address": entry.mac_address,
                    "interface": entry.interface,
                    "family": entry.family,
                    "state": entry.state,
                }
        return None

    def get_all_neighbors(self) -> List[Dict[str, Any]]:
        """Get all neighbor entries."""
        with self._lock:
            return [
                {
                    "ip_address": e.ip_address,
                    "mac_address": e.mac_address,
                    "interface": e.interface,
                    "family": e.family,
                    "state": e.state,
                }
                for e in self._neighbor_table.values()
            ]

    # =========================================================================
    # Bulk Operations
    # =========================================================================

    def process_route_update(self, routes: List[Dict[str, Any]]) -> int:
        """
        Process multiple route updates.

        Args:
            routes: List of route dictionaries

        Returns:
            Number of routes processed
        """
        processed = 0
        for route in routes:
            action = route.get("action", "add")
            if action == "add":
                self.add_route(
                    prefix=route["prefix"],
                    nexthop=route["nexthop"],
                    interface=route.get("interface", ""),
                    vrf=route.get("vrf", "default"),
                )
                processed += 1
            elif action == "delete":
                if self.delete_route(route["prefix"], route.get("vrf", "default")):
                    processed += 1

        return processed

    # =========================================================================
    # Statistics
    # =========================================================================

    def get_stats(self) -> Dict[str, Any]:
        """Get SWSS statistics."""
        base_stats = super().get_stats()
        base_stats.update({
            "orchagent_ready": self.orchagent_ready,
            "route_count": len(self._route_table),
            "fdb_count": len(self._fdb_table),
            "neighbor_count": len(self._neighbor_table),
        })
        return base_stats
