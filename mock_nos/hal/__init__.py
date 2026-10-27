"""
Hardware Abstraction Layer (HAL) for Mock NOS.

This module provides abstractions for hardware resources:
    - PortManager: Physical port management
    - RouteManager: Route/FIB management
"""

from mock_nos.hal.port_manager import PortManager, Port, PortState, PortCounters
from mock_nos.hal.route_manager import RouteManager, RouteEntry, RouteType

__all__ = [
    "PortManager",
    "Port",
    "PortState",
    "PortCounters",
    "RouteManager",
    "RouteEntry",
    "RouteType",
]
