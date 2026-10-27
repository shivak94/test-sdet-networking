# Mock NOS Architecture

This document describes the architecture of the Mock Network Operating System (NOS) used in this assessment.

## Overview

The Mock NOS is a simplified simulation of a modern network operating system, inspired by SONiC (Software for Open Networking in the Cloud). It provides a containerized architecture with layered components for testing purposes.

## Architecture Layers

```
┌─────────────────────────────────────────────────────────────────┐
│                    Application Layer                            │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐              │
│  │ BGP Session │  │OSPF Instance│  │   Other     │              │
│  │             │  │             │  │  Protocols  │              │
│  └─────────────┘  └─────────────┘  └─────────────┘              │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Container Layer                              │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐              │
│  │BGPContainer │  │SwssContainer│  │   Other     │              │
│  │   (FRR)     │  │ (orchagent) │  │ Containers  │              │
│  └─────────────┘  └─────────────┘  └─────────────┘              │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Database Layer                               │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐              │
│  │  CONFIG_DB  │  │  STATE_DB   │  │  RedisMock  │              │
│  │             │  │             │  │             │              │
│  └─────────────┘  └─────────────┘  └─────────────┘              │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│              Hardware Abstraction Layer (HAL)                   │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐              │
│  │PortManager  │  │RouteManager │  │   Other     │              │
│  │             │  │    (FIB)    │  │  Managers   │              │
│  └─────────────┘  └─────────────┘  └─────────────┘              │
└─────────────────────────────────────────────────────────────────┘
```

## Component Details

### 1. Database Layer (`mock_nos/database/`)

The database layer provides in-memory data storage, simulating the Redis-based architecture used in SONiC.

#### RedisMock
- In-memory key-value store
- Supports hash operations (hset, hget, hgetall)
- Supports pub/sub for inter-process communication
- Thread-safe operations

#### CONFIG_DB
- Stores desired configuration state
- Tables: PORT, VLAN, BGP_NEIGHBOR, INTERFACE, LOOPBACK
- Configuration is written here, then processed by containers

#### STATE_DB
- Stores operational state
- Updated by daemons/containers
- Reflects actual system state (port status, BGP neighbor state, etc.)

### 2. Protocol Layer (`mock_nos/protocols/`)

Implements network protocol state machines and logic.

#### BGP (`bgp.py`)
- **BGPState**: Enum for FSM states (IDLE, CONNECT, ACTIVE, OPENSENT, OPENCONFIRM, ESTABLISHED)
- **BGPNeighbor**: Individual neighbor with state machine
- **BGPSession**: Manages multiple neighbors, RIB, route advertisement

Key concepts:
- iBGP vs eBGP detection based on AS numbers
- Hold timer and keepalive management
- Route advertisement and withdrawal
- Best path selection

#### OSPF (`ospf.py`)
- **OSPFNeighborState**: Enum for states (DOWN through FULL)
- **OSPFNeighbor**: Neighbor with Hello processing
- **OSPFInstance**: Manages areas, interfaces, and neighbors

Key concepts:
- Neighbor state machine
- DR/BDR election on broadcast networks
- Area-based routing

### 3. Container Layer (`mock_nos/containers/`)

Simulates Docker containers that run in a real NOS.

#### BaseContainer
- Lifecycle management (start, stop, restart)
- Health checking
- Logging

#### BGPContainer
- Wraps BGPSession
- Loads configuration from CONFIG_DB
- Updates STATE_DB with neighbor states

#### SwssContainer (Switch State Service)
- Simulates orchagent
- Route synchronization
- FDB management
- Neighbor table management

### 4. HAL Layer (`mock_nos/hal/`)

Hardware Abstraction Layer for managing "hardware" resources.

#### PortManager
- Port state management (admin/operational)
- Port counters (rx/tx packets, bytes, errors)
- Speed/MTU configuration

#### RouteManager
- FIB (Forwarding Information Base) management
- Longest prefix match lookup
- Route preference based on admin distance
- ECMP (Equal Cost Multi-Path) support

### 5. Topology Layer (`mock_nos/topology/`)

Utilities for building network topologies.

#### Device
- Represents a switch/router
- Has role (spine, leaf, etc.)
- Has ports and connections

#### TopologyBuilder
- Builds topologies programmatically or from YAML
- Factory methods for common patterns (spine-leaf, Clos)
- Automatic IP allocation

## Data Flow

### Configuration Flow
```
User Config → CONFIG_DB → Container reads config → Container processes → STATE_DB updated
```

### Route Advertisement Flow
```
BGP receives route → RIB update → Best path selection → Local RIB → FIB (RouteManager)
```

### Port State Change Flow
```
Link event → PortManager → STATE_DB → Containers notified via pub/sub
```

## Key Classes Reference

| Module | Class | Purpose |
|--------|-------|---------|
| `database` | `RedisMock` | In-memory key-value store |
| `database` | `ConfigDB` | Configuration storage |
| `database` | `StateDB` | Operational state storage |
| `protocols` | `BGPSession` | BGP routing instance |
| `protocols` | `BGPNeighbor` | Individual BGP peer |
| `protocols` | `OSPFInstance` | OSPF routing instance |
| `containers` | `BGPContainer` | BGP daemon container |
| `containers` | `SwssContainer` | Orchestration container |
| `hal` | `PortManager` | Port management |
| `hal` | `RouteManager` | Route/FIB management |
| `topology` | `TopologyBuilder` | Topology construction |

## Testing Approach

When testing this system:

1. **Unit tests**: Test individual components (BGP state machine, route lookup)
2. **Integration tests**: Test component interactions (container + database)
3. **Topology tests**: Test multi-device scenarios

Use fixtures to set up test environments and ensure proper cleanup.
