"""
Container mocks for Mock NOS.

This module provides Docker-like container mocks that simulate
the containerized architecture of SONiC and similar NOS platforms.

Containers:
    - BGPContainer: FRRouting/BGP daemon container
    - SwssContainer: Switch State Service (orchagent) container
"""

from mock_nos.containers.base_container import BaseContainer, ContainerState
from mock_nos.containers.bgp_container import BGPContainer
from mock_nos.containers.swss_container import SwssContainer

__all__ = [
    "BaseContainer",
    "ContainerState",
    "BGPContainer",
    "SwssContainer",
]
