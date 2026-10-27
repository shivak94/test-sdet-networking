"""
Mock Network Operating System (NOS) Package

This package provides a simulated NOS environment for testing purposes,
inspired by SONiC, VyOS, and other modern network operating systems.

Architecture:
    - database: In-memory databases (CONFIG_DB, STATE_DB, APPL_DB)
    - protocols: Network protocol implementations (BGP, OSPF)
    - containers: Docker-like container mocks (BGP, SWSS)
    - hal: Hardware Abstraction Layer (ports, routes, FDB)
    - topology: Network topology construction utilities
"""

__version__ = "1.0.0"

from mock_nos.errors import (
    NOSError,
    ConfigError,
    ProtocolError,
    ContainerError,
    TopologyError,
    ValidationError,
)

__all__ = [
    "NOSError",
    "ConfigError",
    "ProtocolError",
    "ContainerError",
    "TopologyError",
    "ValidationError",
]
