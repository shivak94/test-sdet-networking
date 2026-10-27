# Network Protocol Reference

This document provides essential networking concepts needed for the assessment. You don't need to be a networking expert - this reference covers what you need to know.

## BGP (Border Gateway Protocol)

BGP is the routing protocol that makes the Internet work. It's used to exchange routing information between networks (Autonomous Systems).

### Key Concepts

#### Autonomous System (AS)
- A network under single administrative control
- Identified by an AS Number (ASN)
- Examples: 65001, 65100, 4200000000

#### iBGP vs eBGP
- **iBGP (Internal BGP)**: Between routers in the SAME AS (local_as == remote_as)
- **eBGP (External BGP)**: Between routers in DIFFERENT AS numbers

```python
# iBGP example
session = BGPSession(router_id="10.0.0.1", local_as=65001)
neighbor = session.add_neighbor({"neighbor_ip": "10.0.0.2", "remote_as": 65001})
assert neighbor.is_ibgp == True

# eBGP example
neighbor = session.add_neighbor({"neighbor_ip": "10.0.0.3", "remote_as": 65002})
assert neighbor.is_ebgp == True
```

### BGP State Machine (FSM)

BGP neighbors go through these states to establish a session:

```
IDLE → CONNECT → OPENSENT → OPENCONFIRM → ESTABLISHED
         ↓
       ACTIVE (if TCP fails)
```

| State | Description |
|-------|-------------|
| **IDLE** | Initial state, no connection |
| **CONNECT** | Trying to establish TCP connection |
| **ACTIVE** | TCP connection failed, retrying |
| **OPENSENT** | TCP connected, OPEN message sent |
| **OPENCONFIRM** | OPEN received and validated, waiting for KEEPALIVE |
| **ESTABLISHED** | Session up, can exchange routes |

```python
# State transitions in code
neighbor.start()  # IDLE → CONNECT
neighbor.tcp_connection_established()  # CONNECT → OPENSENT
neighbor.receive_open(open_msg)  # OPENSENT → OPENCONFIRM
neighbor.receive_keepalive()  # OPENCONFIRM → ESTABLISHED
```

### BGP Timers

- **Hold Time**: How long to wait for messages before declaring peer dead (default: 180 seconds)
- **Keepalive**: How often to send keepalive messages (default: 60 seconds, always 1/3 of hold time)

```python
# If hold_time is 180, keepalive should be 60
# If hold_time is 0, keepalives are disabled
```

### BGP Routes

Routes are advertised with attributes:

| Attribute | Description |
|-----------|-------------|
| **Origin** | How the route was learned (IGP, EGP, INCOMPLETE) |
| **AS Path** | List of AS numbers the route has traversed |
| **Next Hop** | Where to send traffic |
| **Local Pref** | Preference within an AS (higher = better) |
| **MED** | Metric to influence incoming traffic |

### Best Path Selection

When multiple paths exist, BGP selects the best using these criteria (in order):
1. Highest Local Preference
2. Shortest AS Path
3. Lowest Origin type (IGP < EGP < INCOMPLETE)
4. Lowest MED
5. eBGP over iBGP

---

## OSPF (Open Shortest Path First)

OSPF is an interior gateway protocol (IGP) used within a single AS.

### Key Concepts

#### Router ID
- Unique identifier for each OSPF router
- Usually the highest loopback IP or highest interface IP
- Format: IPv4 address (e.g., "10.0.0.1")

#### Areas
- OSPF divides networks into areas
- Area 0 is the backbone (all other areas must connect to it)
- Reduces routing table size and LSA flooding

#### Network Types
- **Broadcast**: Ethernet LANs (elects DR/BDR)
- **Point-to-Point**: Direct links (no DR/BDR)
- **NBMA**: Non-broadcast multi-access

### OSPF Neighbor States

```
DOWN → INIT → 2-WAY → EXSTART → EXCHANGE → LOADING → FULL
```

| State | Description |
|-------|-------------|
| **DOWN** | No Hello received |
| **INIT** | Hello received, but not bidirectional |
| **2-WAY** | Bidirectional communication established |
| **EXSTART** | Negotiating master/slave for DD exchange |
| **EXCHANGE** | Exchanging Database Description packets |
| **LOADING** | Requesting missing LSAs |
| **FULL** | Fully adjacent, databases synchronized |

### DR/BDR Election

On broadcast networks, OSPF elects a Designated Router (DR) and Backup DR:

- **Priority**: Higher priority wins (0-255)
- **Priority 0**: Router CANNOT become DR/BDR
- **Tie breaker**: Higher Router ID wins

```python
# Priority 0 should NOT participate in DR election
router_priority = 0  # This router cannot be DR or BDR
```

---

## Common Data Center Topologies

### Spine-Leaf

```
        ┌─────┐       ┌─────┐
        │Spine│       │Spine│
        │  1  │       │  2  │
        └──┬──┘       └──┬──┘
           │    ╲   ╱    │
           │     ╲ ╱     │
           │      ╳      │
           │     ╱ ╲     │
           │    ╱   ╲    │
        ┌──┴──┐       ┌──┴──┐
        │Leaf │       │Leaf │
        │  1  │       │  2  │
        └─────┘       └─────┘
```

**Characteristics:**
- 2 tiers: Spine (aggregation) and Leaf (access)
- Full mesh between spines and leaves
- Leaves don't connect to each other
- Typically uses eBGP with unique AS per leaf

### BGP in Spine-Leaf

- Each spine has one AS (e.g., 65100)
- Each leaf has unique AS (e.g., 65001, 65002, ...)
- All BGP sessions are eBGP
- Leaf advertises its loopback and connected networks

---

## IP Addressing Basics

### CIDR Notation
- `10.0.0.0/24` = Network with 256 addresses (10.0.0.0 - 10.0.0.255)
- `10.0.0.1/32` = Single host address
- `/31` = Point-to-point link (2 addresses)

### Valid IPv4 Prefix Lengths
- Range: /0 to /32
- `/33` and above are INVALID for IPv4

### VLAN IDs
- Valid range: 1 to 4094
- VLAN 0 and 4095 are reserved

---

## Quick Reference

### BGP Neighbor Setup
```python
session = BGPSession(router_id="10.0.0.1", local_as=65001)
neighbor = session.add_neighbor({
    "neighbor_ip": "10.0.0.2",
    "remote_as": 65002,
    "hold_time": 180,
})
```

### OSPF Setup
```python
ospf = OSPFInstance(router_id="10.0.0.1")
ospf.add_area(0)  # Add backbone area
ospf.add_interface("Ethernet1", "10.0.0.1/24", area_id=0)
```

### Common AS Numbers
| Range | Type |
|-------|------|
| 1-64495 | Public 2-byte |
| 64496-64511 | Reserved for documentation |
| 64512-65534 | Private 2-byte |
| 65535 | Reserved |
| 65536-4199999999 | Public 4-byte |
| 4200000000-4294967294 | Private 4-byte |
