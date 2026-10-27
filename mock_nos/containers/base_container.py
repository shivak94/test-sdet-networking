"""
Base container class for Mock NOS containers.

Provides common lifecycle management, health checking, and logging
functionality for all container mocks.
"""

from abc import ABC, abstractmethod
from enum import Enum
from typing import Any, Dict, List, Optional
from datetime import datetime
import threading
import time


class ContainerState(Enum):
    """Container lifecycle states."""
    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    FAILED = "failed"
    RESTARTING = "restarting"


class BaseContainer(ABC):
    """
    Abstract base class for SONiC-style container mocks.

    Provides:
    - Lifecycle management (start, stop, restart)
    - Health checking
    - Log management
    - State tracking
    """

    def __init__(self, name: str, databases: Dict[str, Any]):
        """
        Initialize container.

        Args:
            name: Container name
            databases: Dictionary of database instances to use
        """
        self.name = name
        self.databases = databases

        # State
        self._state = ContainerState.STOPPED
        self._start_time: Optional[datetime] = None
        self._restart_count: int = 0

        # Logs
        self._logs: List[str] = []
        self._max_log_lines: int = 1000

        # Health
        self._healthy: bool = False
        self._last_health_check: Optional[datetime] = None

        # Threading
        self._lock = threading.RLock()
        self._stop_event = threading.Event()

    @property
    def state(self) -> ContainerState:
        """Get current container state."""
        return self._state

    @property
    def is_running(self) -> bool:
        """Check if container is running."""
        return self._state == ContainerState.RUNNING

    @property
    def uptime_seconds(self) -> int:
        """Get container uptime in seconds."""
        if self._start_time and self._state == ContainerState.RUNNING:
            return int((datetime.now() - self._start_time).total_seconds())
        return 0

    def _set_state(self, new_state: ContainerState) -> None:
        """Set container state with logging."""
        with self._lock:
            old_state = self._state
            self._state = new_state
            self._log(f"State changed: {old_state.value} -> {new_state.value}")

    def _log(self, message: str) -> None:
        """Add a log message."""
        with self._lock:
            timestamp = datetime.now().isoformat()
            log_line = f"[{timestamp}] [{self.name}] {message}"
            self._logs.append(log_line)

            # Trim logs if needed
            if len(self._logs) > self._max_log_lines:
                self._logs = self._logs[-self._max_log_lines:]

    # =========================================================================
    # Lifecycle Management
    # =========================================================================

    def start(self) -> bool:
        """
        Start the container.

        Returns:
            True if started successfully
        """
        with self._lock:
            if self._state == ContainerState.RUNNING:
                self._log("Already running")
                return True

            if self._state not in (ContainerState.STOPPED, ContainerState.FAILED):
                self._log(f"Cannot start from state {self._state.value}")
                return False

            self._set_state(ContainerState.STARTING)
            self._stop_event.clear()

        try:
            self._log("Starting container...")
            self._on_start()
            self._start_time = datetime.now()
            self._set_state(ContainerState.RUNNING)
            self._log("Container started successfully")
            return True

        except Exception as e:
            self._log(f"Failed to start: {e}")
            self._set_state(ContainerState.FAILED)
            return False

    def stop(self) -> bool:
        """
        Stop the container.

        Returns:
            True if stopped successfully
        """
        with self._lock:
            if self._state == ContainerState.STOPPED:
                self._log("Already stopped")
                return True

            if self._state == ContainerState.STOPPING:
                self._log("Already stopping")
                return False

            self._set_state(ContainerState.STOPPING)
            self._stop_event.set()

        try:
            self._log("Stopping container...")
            self._on_stop()
            self._start_time = None
            self._healthy = False
            self._set_state(ContainerState.STOPPED)
            self._log("Container stopped successfully")
            return True

        except Exception as e:
            self._log(f"Error during stop: {e}")
            self._set_state(ContainerState.FAILED)
            return False

    def restart(self) -> bool:
        """
        Restart the container.

        Returns:
            True if restarted successfully
        """
        self._set_state(ContainerState.RESTARTING)
        self._restart_count += 1

        if not self.stop():
            return False

        time.sleep(0.1)  # Brief pause between stop and start

        return self.start()

    @abstractmethod
    def _on_start(self) -> None:
        """
        Called during container start.

        Subclasses should override to perform initialization.
        Raise exception to indicate failure.
        """
        pass

    @abstractmethod
    def _on_stop(self) -> None:
        """
        Called during container stop.

        Subclasses should override to perform cleanup.
        """
        pass

    # =========================================================================
    # Health Checking
    # =========================================================================

    @abstractmethod
    def health_check(self) -> bool:
        """
        Perform health check.

        Returns:
            True if container is healthy
        """
        pass

    def run_health_check(self) -> bool:
        """Run health check and update state."""
        with self._lock:
            if self._state != ContainerState.RUNNING:
                self._healthy = False
                return False

            try:
                self._healthy = self.health_check()
                self._last_health_check = datetime.now()
                return self._healthy
            except Exception as e:
                self._log(f"Health check failed: {e}")
                self._healthy = False
                return False

    @property
    def is_healthy(self) -> bool:
        """Get last health check result."""
        return self._healthy

    # =========================================================================
    # Logging
    # =========================================================================

    def get_logs(self, lines: int = 100, since: datetime = None) -> List[str]:
        """
        Get container logs.

        Args:
            lines: Maximum number of lines to return
            since: Only return logs after this time

        Returns:
            List of log lines
        """
        with self._lock:
            logs = self._logs[-lines:]

            if since:
                # Filter logs by timestamp
                since_str = since.isoformat()
                logs = [
                    log for log in logs
                    if log.split("]")[0][1:] >= since_str
                ]

            return logs

    def clear_logs(self) -> None:
        """Clear container logs."""
        with self._lock:
            self._logs.clear()

    # =========================================================================
    # Utility Methods
    # =========================================================================

    def get_stats(self) -> Dict[str, Any]:
        """Get container statistics."""
        return {
            "name": self.name,
            "state": self._state.value,
            "is_running": self.is_running,
            "is_healthy": self._healthy,
            "uptime_seconds": self.uptime_seconds,
            "restart_count": self._restart_count,
            "log_lines": len(self._logs),
        }

    def wait_for_running(self, timeout: float = 30.0) -> bool:
        """
        Wait for container to be running.

        Args:
            timeout: Maximum time to wait in seconds

        Returns:
            True if container is running within timeout
        """
        start = time.time()
        while time.time() - start < timeout:
            if self._state == ContainerState.RUNNING:
                return True
            if self._state in (ContainerState.FAILED, ContainerState.STOPPED):
                return False
            time.sleep(0.1)
        return False

    def wait_for_healthy(self, timeout: float = 60.0) -> bool:
        """
        Wait for container to be healthy.

        Args:
            timeout: Maximum time to wait in seconds

        Returns:
            True if container is healthy within timeout
        """
        start = time.time()
        while time.time() - start < timeout:
            if self.run_health_check():
                return True
            time.sleep(1.0)
        return False

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(name={self.name}, state={self._state.value})"
