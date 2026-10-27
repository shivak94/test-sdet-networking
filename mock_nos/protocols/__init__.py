"""
Protocol implementations for Mock NOS.

This module provides simulated network protocol implementations:
    - BGP: Border Gateway Protocol with FSM
    - OSPF: Open Shortest Path First with neighbor states
"""

from mock_nos.protocols.bgp import (
    BGPState,
    BGPNeighbor,
    BGPSession,
    BGPOpenMessage,
    BGPUpdateMessage,
    BGPAttributes,
)
from mock_nos.protocols.ospf import (
    OSPFNeighborState,
    OSPFNeighbor,
    OSPFInstance,
    OSPFArea,
)

__all__ = [
    "BGPState",
    "BGPNeighbor",
    "BGPSession",
    "BGPOpenMessage",
    "BGPUpdateMessage",
    "BGPAttributes",
    "OSPFNeighborState",
    "OSPFNeighbor",
    "OSPFInstance",
    "OSPFArea",
]
