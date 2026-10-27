"""
Custom exceptions for the Mock NOS package.

All exceptions inherit from NOSError for easy catching of any NOS-related error.
"""


class NOSError(Exception):
    """Base exception for all NOS-related errors."""

    def __init__(self, message: str, details: dict = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}

    def __str__(self) -> str:
        if self.details:
            return f"{self.message} - Details: {self.details}"
        return self.message


class ConfigError(NOSError):
    """Raised when there's a configuration error."""

    pass


class ValidationError(NOSError):
    """Raised when validation fails."""

    pass


class ProtocolError(NOSError):
    """Raised when there's a protocol-related error."""

    pass


class ContainerError(NOSError):
    """Raised when there's a container lifecycle error."""

    pass


class TopologyError(NOSError):
    """Raised when there's a topology construction error."""

    pass


class DatabaseError(NOSError):
    """Raised when there's a database operation error."""

    pass


class HALError(NOSError):
    """Raised when there's a Hardware Abstraction Layer error."""

    pass


class TimeoutError(NOSError):
    """Raised when an operation times out."""

    pass


class StateError(NOSError):
    """Raised when an invalid state transition is attempted."""

    pass
