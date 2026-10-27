"""
In-memory Redis-like database mock.

This module provides a simplified Redis implementation for testing,
supporting basic key-value operations and pub/sub messaging.
"""

from typing import Any, Callable, Dict, List, Optional, Set
from collections import defaultdict
import threading
import time


class RedisMock:
    """
    In-memory Redis mock with basic operations and pub/sub support.

    This simulates the Redis database used in SONiC for inter-process
    communication between containers.

    Supported operations:
        - Hash operations: hset, hget, hgetall, hdel, hexists
        - Key operations: set, get, delete, exists, keys
        - Pub/Sub: subscribe, publish
    """

    def __init__(self):
        """Initialize empty Redis mock."""
        self._data: Dict[str, Dict[str, Any]] = defaultdict(dict)
        self._simple_keys: Dict[str, Any] = {}
        self._subscribers: Dict[str, List[Callable]] = defaultdict(list)
        self._lock = threading.RLock()
        self._key_timestamps: Dict[str, float] = {}

    def clear(self) -> None:
        """Clear all data from the database."""
        with self._lock:
            self._data.clear()
            self._simple_keys.clear()
            self._subscribers.clear()
            self._key_timestamps.clear()

    # =========================================================================
    # Hash Operations
    # =========================================================================

    def hset(self, table: str, key: str, value: Any) -> int:
        """
        Set a hash field value.

        Args:
            table: Hash table name
            key: Field key within the hash
            value: Value to store

        Returns:
            1 if new field, 0 if updated existing field
        """
        with self._lock:
            is_new = key not in self._data[table]
            self._data[table][key] = value
            self._key_timestamps[f"{table}:{key}"] = time.time()

            # Notify subscribers
            self._notify(f"__keyspace@0__:{table}", f"hset {key}")

            return 1 if is_new else 0

    def hget(self, table: str, key: str) -> Optional[Any]:
        """
        Get a hash field value.

        Args:
            table: Hash table name
            key: Field key within the hash

        Returns:
            The value or None if not found
        """
        with self._lock:
            return self._data.get(table, {}).get(key)

    def hgetall(self, table: str) -> Dict[str, Any]:
        """
        Get all fields and values in a hash.

        Args:
            table: Hash table name

        Returns:
            Dictionary of all key-value pairs in the hash
        """
        with self._lock:
            return dict(self._data.get(table, {}))

    def hdel(self, table: str, *keys: str) -> int:
        """
        Delete one or more hash fields.

        Args:
            table: Hash table name
            keys: Field keys to delete

        Returns:
            Number of fields deleted
        """
        with self._lock:
            deleted = 0
            for key in keys:
                if key in self._data.get(table, {}):
                    del self._data[table][key]
                    self._key_timestamps.pop(f"{table}:{key}", None)
                    deleted += 1
                    self._notify(f"__keyspace@0__:{table}", f"hdel {key}")
            return deleted

    def hexists(self, table: str, key: str) -> bool:
        """
        Check if a hash field exists.

        Args:
            table: Hash table name
            key: Field key to check

        Returns:
            True if exists, False otherwise
        """
        with self._lock:
            return key in self._data.get(table, {})

    def hkeys(self, table: str) -> List[str]:
        """
        Get all field names in a hash.

        Args:
            table: Hash table name

        Returns:
            List of field names
        """
        with self._lock:
            return list(self._data.get(table, {}).keys())

    # =========================================================================
    # Simple Key Operations
    # =========================================================================

    def set(self, key: str, value: Any) -> bool:
        """Set a simple key-value pair."""
        with self._lock:
            self._simple_keys[key] = value
            self._key_timestamps[key] = time.time()
            return True

    def get(self, key: str) -> Optional[Any]:
        """Get a simple key value."""
        with self._lock:
            return self._simple_keys.get(key)

    def delete(self, *keys: str) -> int:
        """Delete one or more keys."""
        with self._lock:
            deleted = 0
            for key in keys:
                if key in self._simple_keys:
                    del self._simple_keys[key]
                    deleted += 1
            return deleted

    def exists(self, *keys: str) -> int:
        """Check how many of the specified keys exist."""
        with self._lock:
            return sum(1 for key in keys if key in self._simple_keys)

    def keys(self, pattern: str = "*") -> List[str]:
        """
        Get keys matching pattern.

        Args:
            pattern: Glob-style pattern (* matches any sequence)

        Returns:
            List of matching keys
        """
        with self._lock:
            if pattern == "*":
                return list(self._simple_keys.keys())

            # Simple pattern matching
            import fnmatch
            return [k for k in self._simple_keys.keys() if fnmatch.fnmatch(k, pattern)]

    # =========================================================================
    # Table Operations (Hash-based tables)
    # =========================================================================

    def get_tables(self) -> List[str]:
        """Get list of all hash tables."""
        with self._lock:
            return list(self._data.keys())

    def table_exists(self, table: str) -> bool:
        """Check if a table exists."""
        with self._lock:
            return table in self._data

    def drop_table(self, table: str) -> bool:
        """Drop an entire hash table."""
        with self._lock:
            if table in self._data:
                del self._data[table]
                return True
            return False

    # =========================================================================
    # Pub/Sub Operations
    # =========================================================================

    def subscribe(self, pattern: str, callback: Callable[[str, str], None]) -> None:
        """
        Subscribe to messages matching pattern.

        Args:
            pattern: Channel pattern to subscribe to
            callback: Function(channel, message) to call on messages
        """
        with self._lock:
            self._subscribers[pattern].append(callback)

    def unsubscribe(self, pattern: str, callback: Callable = None) -> None:
        """
        Unsubscribe from messages.

        Args:
            pattern: Channel pattern to unsubscribe from
            callback: Specific callback to remove, or None for all
        """
        with self._lock:
            if callback is None:
                self._subscribers[pattern].clear()
            elif callback in self._subscribers[pattern]:
                self._subscribers[pattern].remove(callback)

    def publish(self, channel: str, message: Any) -> int:
        """
        Publish a message to a channel.

        Args:
            channel: Channel name
            message: Message to publish

        Returns:
            Number of subscribers that received the message
        """
        with self._lock:
            callbacks = list(self._subscribers.get(channel, []))

        # Call callbacks outside lock to prevent deadlocks
        for callback in callbacks:
            try:
                callback(channel, message)
            except Exception:
                pass  # Ignore callback errors

        return len(callbacks)

    def _notify(self, channel: str, message: str) -> None:
        """Internal notification helper."""
        self.publish(channel, message)

    # =========================================================================
    # Utility Methods
    # =========================================================================

    def get_stats(self) -> Dict[str, Any]:
        """Get database statistics."""
        with self._lock:
            return {
                "tables": len(self._data),
                "total_keys": sum(len(v) for v in self._data.values()),
                "simple_keys": len(self._simple_keys),
                "subscribers": sum(len(v) for v in self._subscribers.values()),
            }

    def dump(self) -> Dict[str, Any]:
        """Dump entire database state for debugging."""
        with self._lock:
            return {
                "hash_tables": {k: dict(v) for k, v in self._data.items()},
                "simple_keys": dict(self._simple_keys),
            }
