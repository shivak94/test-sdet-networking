"""
BGP container mock.

Simulates the BGP/FRRouting container in SONiC, which runs
the BGP routing daemon and manages BGP sessions.
"""

from typing import Any, Dict, List, Optional
from mock_nos.containers.base_container import BaseContainer, ContainerState
from mock_nos.protocols.bgp import BGPSession, BGPNeighbor, BGPState
from mock_nos.errors import ContainerError


class BGPContainer(BaseContainer):
    """
    BGP container mock (FRRouting/Quagga equivalent).

    This container manages:
    - BGP session lifecycle
    - Neighbor configuration from CONFIG_DB
    - Route synchronization to/from APPL_DB
    """

    def __init__(self, databases: Dict[str, Any]):
        """
        Initialize BGP container.

        Args:
            databases: Dict with 'config', 'state', and optionally 'appl' keys
        """
        super().__init__("bgp", databases)

        self.bgp_session: Optional[BGPSession] = None
        self._config_db = databases.get("config")
        self._state_db = databases.get("state")

    def _on_start(self) -> None:
        """Initialize BGP session from configuration."""
        self._log("Initializing BGP session...")

        # Get BGP global config
        bgp_global = None
        if self._config_db:
            bgp_global = self._config_db.get_bgp_global()

        if not bgp_global:
            # Use defaults
            self._log("No BGP global config, using defaults")
            self.bgp_session = BGPSession(
                router_id="0.0.0.0",
                local_as=65000,
            )
        else:
            self.bgp_session = BGPSession(
                router_id=bgp_global.get("router_id", "0.0.0.0"),
                local_as=bgp_global.get("local_as", 65000),
            )

        # Load neighbors from config
        if self._config_db:
            neighbors = self._config_db.get_all_bgp_neighbors()
            for addr, config in neighbors.items():
                self._log(f"Adding neighbor {addr}")
                neighbor = self.bgp_session.add_neighbor({
                    "neighbor_ip": addr,
                    "remote_as": config["remote_as"],
                    "hold_time": config.get("hold_time", 180),
                    "keepalive": config.get("keepalive", 60),
                })

                # Register state change callback
                neighbor.on_state_change(self._on_neighbor_state_change)

        self._log(f"BGP session initialized: {self.bgp_session}")

    def _on_stop(self) -> None:
        """Clean up BGP session."""
        self._log("Stopping BGP session...")

        if self.bgp_session:
            for neighbor in self.bgp_session.neighbors.values():
                neighbor.stop()

            self.bgp_session = None

    def health_check(self) -> bool:
        """Check if BGP container is healthy."""
        if self._state != ContainerState.RUNNING:
            return False

        if self.bgp_session is None:
            return False

        return True

    def _on_neighbor_state_change(
        self,
        neighbor: BGPNeighbor,
        old_state: BGPState,
        new_state: BGPState
    ) -> None:
        """Handle neighbor state changes."""
        self._log(f"Neighbor {neighbor.neighbor_ip} state: {old_state.value} -> {new_state.value}")

        # Update STATE_DB
        if self._state_db:
            self._state_db.set_bgp_neighbor_state(
                neighbor_address=neighbor.neighbor_ip,
                state=new_state.value,
                remote_as=neighbor.remote_as,
                local_as=neighbor.local_as,
                prefixes_received=neighbor.prefixes_received,
                prefixes_sent=neighbor.prefixes_sent,
            )

    # =========================================================================
    # BGP Operations
    # =========================================================================

    def configure_bgp(self, router_id: str, local_as: int) -> None:
        """
        Configure BGP global settings.

        Args:
            router_id: Router ID
            local_as: Local AS number
        """
        if not self.is_running:
            raise ContainerError("Container must be running to configure BGP")

        self.bgp_session = BGPSession(router_id=router_id, local_as=local_as)
        self._log(f"BGP configured: router_id={router_id}, local_as={local_as}")

    def add_neighbor(self, config: Dict[str, Any]) -> BGPNeighbor:
        """
        Add a BGP neighbor.

        Args:
            config: Neighbor configuration

        Returns:
            BGPNeighbor object
        """
        if not self.is_running or not self.bgp_session:
            raise ContainerError("Container must be running with BGP session")

        neighbor = self.bgp_session.add_neighbor(config)
        neighbor.on_state_change(self._on_neighbor_state_change)

        self._log(f"Added neighbor {config['neighbor_ip']} (AS {config['remote_as']})")
        return neighbor

    def remove_neighbor(self, neighbor_ip: str) -> bool:
        """Remove a BGP neighbor."""
        if not self.bgp_session:
            return False

        result = self.bgp_session.remove_neighbor(neighbor_ip)
        if result:
            self._log(f"Removed neighbor {neighbor_ip}")
        return result

    def get_neighbor(self, neighbor_ip: str) -> Optional[BGPNeighbor]:
        """Get a neighbor by IP."""
        if not self.bgp_session:
            return None
        return self.bgp_session.get_neighbor(neighbor_ip)

    def get_neighbor_summary(self) -> List[Dict[str, Any]]:
        """Get summary of all neighbors."""
        if not self.bgp_session:
            return []
        return self.bgp_session.get_neighbor_summary()

    def get_established_count(self) -> int:
        """Get count of established neighbors."""
        if not self.bgp_session:
            return 0
        return sum(
            1 for n in self.bgp_session.neighbors.values()
            if n.is_established
        )

    # =========================================================================
    # Route Operations
    # =========================================================================

    def advertise_route(self, prefix: str, **kwargs) -> None:
        """
        Advertise a route.

        Args:
            prefix: Route prefix to advertise
            **kwargs: BGP attributes
        """
        if not self.bgp_session:
            raise ContainerError("No BGP session")

        from mock_nos.protocols.bgp import BGPAttributes

        attributes = BGPAttributes(
            origin=kwargs.get("origin", "IGP"),
            as_path=kwargs.get("as_path", [self.bgp_session.local_as]),
            next_hop=kwargs.get("next_hop", self.bgp_session.router_id),
            local_pref=kwargs.get("local_pref", 100),
            med=kwargs.get("med", 0),
        )

        self.bgp_session.advertise_route(prefix, attributes)
        self._log(f"Advertised route {prefix}")

    def withdraw_route(self, prefix: str) -> bool:
        """Withdraw a route."""
        if not self.bgp_session:
            return False

        result = self.bgp_session.withdraw_route(prefix)
        if result:
            self._log(f"Withdrawn route {prefix}")
        return result

    def get_rib(self, afi: str = "ipv4", safi: str = "unicast") -> Dict[str, Any]:
        """
        Get the Routing Information Base.

        Args:
            afi: Address Family Identifier
            safi: Subsequent AFI

        Returns:
            Dict of prefix -> route info
        """
        if not self.bgp_session:
            return {}
        return self.bgp_session.get_routes(afi)

    def get_route_count(self) -> int:
        """Get total route count."""
        if not self.bgp_session:
            return 0
        return len(self.bgp_session.loc_rib)

    # =========================================================================
    # Simulation Helpers
    # =========================================================================

    def simulate_neighbor_up(self, neighbor_ip: str) -> bool:
        """
        Simulate a neighbor coming up (for testing).

        This transitions the neighbor through the FSM states to Established.

        Args:
            neighbor_ip: Neighbor IP address

        Returns:
            True if successful
        """
        neighbor = self.get_neighbor(neighbor_ip)
        if not neighbor:
            return False

        from mock_nos.protocols.bgp import BGPOpenMessage

        # Simulate FSM transitions
        neighbor.start()  # IDLE -> CONNECT
        neighbor.tcp_connection_established()  # CONNECT -> OPENSENT

        # Simulate OPEN exchange
        open_msg = BGPOpenMessage(
            version=4,
            my_as=neighbor.remote_as,
            hold_time=180,
            bgp_identifier=neighbor_ip,
        )
        neighbor.receive_open(open_msg)  # OPENSENT -> OPENCONFIRM
        neighbor.receive_keepalive()  # OPENCONFIRM -> ESTABLISHED

        return neighbor.is_established

    def simulate_neighbor_down(self, neighbor_ip: str) -> bool:
        """
        Simulate a neighbor going down.

        Args:
            neighbor_ip: Neighbor IP address

        Returns:
            True if successful
        """
        neighbor = self.get_neighbor(neighbor_ip)
        if not neighbor:
            return False

        neighbor.stop()
        return True
