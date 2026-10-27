# SDET Track - Task Description

**Position**: Software Developer in Test (Networking)
**Time Estimate**: 2-3 hours
**Difficulty**: Intermediate

## Overview

In this assessment, you will work with a Mock Network Operating System (NOS) to demonstrate your skills in test automation using Python and pytest.

## Your Tasks

### Task 1: Complete Test Fixtures (30 minutes)

Open `tests/conftest.py` and complete the TODO items:

1. **`databases` fixture**: Bundle all database instances into a dictionary
2. **`bgp_session_with_neighbor` fixture**: Create a BGP session with a pre-configured neighbor
3. **`established_bgp_neighbor` fixture**: Create a BGP neighbor in ESTABLISHED state
4. **`ospf_instance` fixture**: Create an OSPF instance with area 0
5. **`swss_container` fixture**: Create and manage a SWSS container
6. **`port_manager_with_ports` fixture**: Create a port manager with 4 ports
7. **`small_topology` fixture**: Create a 1-spine, 2-leaf topology
8. **`wait_for_bgp_convergence` fixture**: Create a utility function to wait for BGP convergence

### Task 2: Implement Test Cases (60-90 minutes)

Open `tests/test_starter.py` and complete the TODO items:

**BGP Tests:**
- `test_bgp_state_machine_transitions`: Test BGP FSM from IDLE to ESTABLISHED
- `test_ibgp_vs_ebgp_detection`: Verify iBGP/eBGP classification
- `test_bgp_route_advertisement`: Test route advertising to RIB
- `test_bgp_asn_range`: Parameterized test for AS numbers
- `test_bgp_timers`: Parameterized test for hold/keepalive timers

**OSPF Tests:**
- `test_ospf_instance_creation`: Verify OSPF instance setup
- `test_ospf_neighbor_initial_state`: Test neighbor starts in DOWN state
- `test_ospf_hello_processing`: Test Hello packet processing

**Database Tests:**
- `test_config_db_vlan_config`: Test VLAN configuration
- `test_config_db_bgp_neighbor`: Test BGP neighbor config storage

**Container Tests:**
- `test_swss_container_starts`: Verify SWSS container starts correctly
- `test_container_restart`: Test container restart behavior

**HAL Tests:**
- `test_port_counters`: Test port counter operations
- `test_port_state_transitions`: Test port state management
- `test_longest_prefix_match`: Test route lookup algorithm
- `test_route_prefix_validation`: Test prefix validation

**Topology Tests:**
- `test_spine_leaf_connectivity`: Verify topology connections
- `test_custom_topology_creation`: Build a custom topology

**Integration Tests:**
- `test_bgp_end_to_end`: Complete BGP workflow test

### Task 3: Find Bugs (30-45 minutes)

The `mock_nos` module contains intentional bugs. Your task is to:

1. Find at least **2 bugs** through testing
2. Create a file `BUGS_FOUND.md` documenting each bug with:
   - Bug location (file and line number if possible)
   - Description of the bug
   - How you discovered it
   - Expected vs actual behavior

**Hints:**
- Test boundary conditions carefully
- Pay attention to validation logic
- Test with edge case values

## Deliverables

1. Completed `tests/conftest.py` with all fixtures implemented
2. Completed `tests/test_starter.py` with all tests implemented
3. `BUGS_FOUND.md` documenting at least 2 bugs
4. All tests should pass (except those intentionally testing buggy behavior)

## Evaluation Criteria

| Category | Weight | Description |
|----------|--------|-------------|
| **Correctness** | 30% | Tests work and validate expected behavior |
| **pytest Skills** | 25% | Proper fixture design, parametrization, markers |
| **Bug Detection** | 25% | Found and documented bugs |
| **Protocol Knowledge** | 10% | Understanding of BGP/OSPF concepts |
| **Code Quality** | 10% | Clean, readable, well-documented code |

## Getting Started

```bash
# Verify setup
pytest tests/examples/ -v

# Run your tests
pytest tests/test_starter.py -v

# Run with coverage
pytest tests/test_starter.py -v --cov=mock_nos
```

## Resources

- `docs/ARCHITECTURE.md` - System architecture overview
- `docs/PROTOCOL_REFERENCE.md` - BGP/OSPF concepts
- `tests/examples/test_patterns.py` - pytest pattern examples

Good luck!
