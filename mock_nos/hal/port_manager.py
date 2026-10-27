"""
Port Manager for HAL layer.

Manages physical port resources including:
- Port state (admin/operational)
- Port counters (rx/tx packets, bytes, errors)
- Speed/duplex/MTU configuration
"""

from enum import Enum
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field
import threading
import time


class PortState(Enum):
    """Port operational states."""
    UP = "up"
    DOWN = "down"
    ADMIN_DOWN = "admin_down"
    ERROR = "error"


@dataclass
class PortCounters:
    """Port statistics counters."""
    rx_packets: int = 0
    tx_packets: int = 0
    rx_bytes: int = 0
    tx_bytes: int = 0
    rx_errors: int = 0
    tx_errors: int = 0
    rx_drops: int = 0
    tx_drops: int = 0
    rx_broadcast: int = 0
    tx_broadcast: int = 0
    rx_multicast: int = 0
    tx_multicast: int = 0

    def to_dict(self) -> Dict[str, int]:
        return {
            "rx_packets": self.rx_packets,
            "tx_packets": self.tx_packets,
            "rx_bytes": self.rx_bytes,
            "tx_bytes": self.tx_bytes,
            "rx_errors": self.rx_errors,
            "tx_errors": self.tx_errors,
            "rx_drops": self.rx_drops,
            "tx_drops": self.tx_drops,
            "rx_broadcast": self.rx_broadcast,
            "tx_broadcast": self.tx_broadcast,
            "rx_multicast": self.rx_multicast,
            "tx_multicast": self.tx_multicast,
        }

    def clear(self) -> None:
        """Clear all counters."""
        self.rx_packets = 0
        self.tx_packets = 0
        self.rx_bytes = 0
        self.tx_bytes = 0
        self.rx_errors = 0
        self.tx_errors = 0
        self.rx_drops = 0
        self.tx_drops = 0
        self.rx_broadcast = 0
        self.tx_broadcast = 0
        self.rx_multicast = 0
        self.tx_multicast = 0


@dataclass
class Port:
    """Network port abstraction."""
    name: str
    speed: int = 100000  # Mbps
    mtu: int = 9100
    mac_address: str = ""
    admin_state: PortState = PortState.UP
    oper_state: PortState = PortState.DOWN
    fec: str = "none"
    autoneg: bool = True
    description: str = ""
    counters: PortCounters = field(default_factory=PortCounters)

    # Link partner info
    link_partner_speed: int = 0
    link_partner_duplex: str = "full"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "speed": self.speed,
            "mtu": self.mtu,
            "mac_address": self.mac_address,
            "admin_state": self.admin_state.value,
            "oper_state": self.oper_state.value,
            "fec": self.fec,
            "autoneg": self.autoneg,
            "description": self.description,
        }


class PortManager:
    """
    HAL for port management.

    Manages physical ports including state, configuration,
    and statistics counters.
    """

    # Maximum counter value (64-bit)
    MAX_COUNTER_VALUE = 2**64 - 1

    def __init__(self):
        """Initialize port manager."""
        self.ports: Dict[str, Port] = {}
        self._lock = threading.RLock()

        # State change callbacks
        self._state_callbacks: List = []

    def add_port(self, name: str, **kwargs) -> Port:
        """
        Add a port.

        Args:
            name: Port name (e.g., "Ethernet0")
            **kwargs: Port configuration options

        Returns:
            Port object
        """
        with self._lock:
            port = Port(
                name=name,
                speed=kwargs.get("speed", 100000),
                mtu=kwargs.get("mtu", 9100),
                mac_address=kwargs.get("mac_address", self._generate_mac(name)),
                admin_state=PortState(kwargs.get("admin_state", "up")),
                fec=kwargs.get("fec", "none"),
                autoneg=kwargs.get("autoneg", True),
                description=kwargs.get("description", ""),
            )

            self.ports[name] = port
            return port

    def remove_port(self, name: str) -> bool:
        """Remove a port."""
        with self._lock:
            if name in self.ports:
                del self.ports[name]
                return True
            return False

    def get_port(self, name: str) -> Optional[Port]:
        """Get a port by name."""
        return self.ports.get(name)

    def get_all_ports(self) -> Dict[str, Port]:
        """Get all ports."""
        return dict(self.ports)

    def _generate_mac(self, port_name: str) -> str:
        """Generate a MAC address for a port."""
        # Extract port number from name
        import re
        match = re.search(r'\d+', port_name)
        port_num = int(match.group()) if match else 0

        # Generate MAC: 00:00:00:00:XX:XX where XX:XX is port number
        return f"00:00:00:00:{port_num // 256:02x}:{port_num % 256:02x}"

    # =========================================================================
    # Port State Management
    # =========================================================================

    def set_admin_state(self, port_name: str, state: PortState) -> bool:
        """
        Set port admin state.

        Args:
            port_name: Port name
            state: New admin state

        Returns:
            True if successful
        """
        with self._lock:
            port = self.ports.get(port_name)
            if not port:
                return False

            old_state = port.admin_state
            port.admin_state = state

            # Update operational state based on admin state
            if state == PortState.ADMIN_DOWN:
                port.oper_state = PortState.DOWN
            elif state == PortState.UP and port.oper_state == PortState.DOWN:
                # Could transition to UP if link is present
                pass

            if old_state != state:
                self._notify_state_change(port_name, old_state, state)

            return True

    def set_oper_state(self, port_name: str, state: PortState) -> bool:
        """
        Set port operational state (simulating link events).

        Args:
            port_name: Port name
            state: New operational state

        Returns:
            True if successful
        """
        with self._lock:
            port = self.ports.get(port_name)
            if not port:
                return False

            # Can't bring up operationally if admin down
            if port.admin_state == PortState.ADMIN_DOWN and state == PortState.UP:
                return False

            old_state = port.oper_state
            port.oper_state = state

            if old_state != state:
                self._notify_state_change(port_name, old_state, state)

            return True

    def _notify_state_change(self, port_name: str, old_state: PortState, new_state: PortState):
        """Notify registered callbacks of state change."""
        for callback in self._state_callbacks:
            try:
                callback(port_name, old_state, new_state)
            except Exception:
                pass

    def on_state_change(self, callback) -> None:
        """Register a state change callback."""
        self._state_callbacks.append(callback)

    # =========================================================================
    # Port Configuration
    # =========================================================================

    def set_speed(self, port_name: str, speed: int) -> bool:
        """Set port speed in Mbps."""
        with self._lock:
            port = self.ports.get(port_name)
            if not port:
                return False

            valid_speeds = [1000, 10000, 25000, 40000, 50000, 100000, 200000, 400000]
            if speed not in valid_speeds:
                return False

            port.speed = speed
            return True

    def set_mtu(self, port_name: str, mtu: int) -> bool:
        """Set port MTU."""
        with self._lock:
            port = self.ports.get(port_name)
            if not port:
                return False

            if not (68 <= mtu <= 9216):
                return False

            port.mtu = mtu
            return True

    def set_fec(self, port_name: str, fec: str) -> bool:
        """Set port Forward Error Correction mode."""
        with self._lock:
            port = self.ports.get(port_name)
            if not port:
                return False

            valid_fec = ["none", "rs", "fc", "auto"]
            if fec not in valid_fec:
                return False

            port.fec = fec
            return True

    # =========================================================================
    # Counter Management
    # =========================================================================

    def get_counters(self, port_name: str) -> Optional[Dict[str, int]]:
        """Get port counters."""
        port = self.ports.get(port_name)
        if not port:
            return None
        return port.counters.to_dict()

    def clear_counters(self, port_name: str = None) -> bool:
        """
        Clear port counters.

        Args:
            port_name: Port to clear, or None for all ports

        Returns:
            True if successful
        """
        with self._lock:
            if port_name:
                port = self.ports.get(port_name)
                if not port:
                    return False
                port.counters.clear()
            else:
                for port in self.ports.values():
                    port.counters.clear()
            return True

    def increment_counter(
        self,
        port_name: str,
        counter: str,
        value: int = 1
    ) -> bool:
        """
        Increment a port counter.

        Args:
            port_name: Port name
            counter: Counter name (e.g., "rx_packets")
            value: Value to add

        Returns:
            True if successful

        BUG-004: Counter overflow not handled properly.
        64-bit counters should wrap around at MAX_COUNTER_VALUE,
        but this implementation doesn't handle overflow.
        """
        with self._lock:
            port = self.ports.get(port_name)
            if not port:
                return False

            counters = port.counters
            if not hasattr(counters, counter):
                return False

            current = getattr(counters, counter)

            # BUG-004: No overflow handling
            # Should be: new_value = (current + value) % (self.MAX_COUNTER_VALUE + 1)
            # Bug: Just adds without checking for overflow
            new_value = current + value

            setattr(counters, counter, new_value)
            return True

    def simulate_traffic(
        self,
        port_name: str,
        rx_packets: int = 0,
        tx_packets: int = 0,
        rx_bytes: int = 0,
        tx_bytes: int = 0,
    ) -> bool:
        """
        Simulate traffic on a port (for testing).

        Args:
            port_name: Port name
            rx_packets: Received packets
            tx_packets: Transmitted packets
            rx_bytes: Received bytes
            tx_bytes: Transmitted bytes

        Returns:
            True if successful
        """
        port = self.ports.get(port_name)
        if not port:
            return False

        if rx_packets:
            self.increment_counter(port_name, "rx_packets", rx_packets)
        if tx_packets:
            self.increment_counter(port_name, "tx_packets", tx_packets)
        if rx_bytes:
            self.increment_counter(port_name, "rx_bytes", rx_bytes)
        if tx_bytes:
            self.increment_counter(port_name, "tx_bytes", tx_bytes)

        return True

    # =========================================================================
    # Bulk Operations
    # =========================================================================

    def get_ports_by_state(self, state: PortState) -> List[str]:
        """Get list of ports in a given state."""
        return [
            name for name, port in self.ports.items()
            if port.oper_state == state
        ]

    def get_up_ports(self) -> List[str]:
        """Get list of operationally up ports."""
        return self.get_ports_by_state(PortState.UP)

    def get_down_ports(self) -> List[str]:
        """Get list of operationally down ports."""
        return self.get_ports_by_state(PortState.DOWN)

    def get_stats(self) -> Dict[str, Any]:
        """Get port manager statistics."""
        return {
            "total_ports": len(self.ports),
            "up_ports": len(self.get_up_ports()),
            "down_ports": len(self.get_down_ports()),
        }
