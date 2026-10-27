# Senior SDET Track - Task Description

**Position**: Senior Software Developer in Test (Networking)
**Time Estimate**: 3-4 hours
**Difficulty**: Advanced

## Overview

This assessment evaluates your ability to design and implement test frameworks, handle complex testing scenarios, and mentor others through code quality.

## Your Tasks

### Task 1: Complete All SDET Track Requirements

First, complete all tasks from the SDET track:
- Complete fixtures in `tests/conftest.py`
- Implement tests in `tests/test_starter.py`
- Find and document at least 2 bugs

See `docs/TASK_SDET.md` for details.

### Task 2: Implement Bonus Challenges (45-60 minutes)

Complete the BONUS test cases in `tests/test_starter.py`:

1. **`test_concurrent_route_updates`**: Test thread-safe route operations
   - Use threading to add 100 routes concurrently
   - Verify data consistency
   - Identify any race conditions

2. **`test_route_lookup_performance`**: Performance test
   - Add 10,000 routes
   - Measure lookup time for 1,000 queries
   - Assert performance requirements

3. **`test_bgp_flap_detection`**: Test session stability monitoring
   - Simulate rapid state changes
   - Verify flap counting

### Task 3: Framework Extension (60-90 minutes)

Design and implement ONE of the following framework extensions:

#### Option A: Custom pytest Plugin
Create a pytest plugin for topology management:
- Auto-cleanup of topology resources
- Topology validation hooks
- Custom markers for topology-dependent tests

#### Option B: Parallel Test Execution Strategy
Design a test parallelization approach:
- Identify tests that can run in parallel
- Handle shared resource conflicts
- Implement pytest-xdist configuration

#### Option C: Test Data Generation Framework
Create a framework for generating test data:
- Random but valid BGP/OSPF configurations
- Topology generators with constraints
- Reproducible test data (seeded randomness)

### Task 4: Design Document (30 minutes)

Write a 1-page design document (`DESIGN.md`) covering:

1. **Problem Statement**: What problem does your extension solve?
2. **Approach**: How does your solution work?
3. **Architecture**: Key components and their interactions
4. **Trade-offs**: Alternatives considered and why you chose this approach
5. **Future Improvements**: What would you add with more time?

## Deliverables

1. All SDET track deliverables
2. Completed BONUS tests in `test_starter.py`
3. Framework extension implementation (in `tests/` or new module)
4. `DESIGN.md` describing your framework extension
5. Find at least **4 bugs** total (document in `BUGS_FOUND.md`)

## Evaluation Criteria

| Category | Weight | Description |
|----------|--------|-------------|
| **Framework Design** | 25% | Quality and usability of extension |
| **Advanced Patterns** | 25% | Use of advanced pytest features |
| **Concurrency/Performance** | 20% | Handling of concurrent and performance tests |
| **Bug Detection** | 15% | Finding subtle bugs including race conditions |
| **Design Document** | 15% | Clarity and completeness of design doc |

## Example Framework Extension (Option A)

```python
# Example pytest plugin structure
# tests/plugins/topology_plugin.py

import pytest

class TopologyManager:
    def __init__(self):
        self._topologies = {}

    def register(self, name, topology):
        self._topologies[name] = topology

    def cleanup_all(self):
        for name, topo in self._topologies.items():
            topo.teardown()
        self._topologies.clear()


@pytest.fixture(scope="session")
def topology_manager():
    manager = TopologyManager()
    yield manager
    manager.cleanup_all()


def pytest_configure(config):
    config.addinivalue_line(
        "markers", "requires_topology(name): mark test as requiring specific topology"
    )


@pytest.hookimpl(tryfirst=True)
def pytest_runtest_setup(item):
    markers = list(item.iter_markers(name="requires_topology"))
    if markers:
        # Validate topology exists and is ready
        pass
```

## Resources

- pytest plugin documentation: https://docs.pytest.org/en/stable/how-to/writing_plugins.html
- pytest-xdist: https://pytest-xdist.readthedocs.io/
- `tests/examples/test_patterns.py` - Advanced patterns

Good luck!
