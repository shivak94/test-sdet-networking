# Design: topology plugin (Task 3, option A)

Code is in `tests/plugins/topology_plugin.py`, examples in `tests/test_topology_plugin_usage.py`.

## 1. Problem

Every topology a test needs is a hand-written fixture right now (`spine_leaf_topology`,
`small_topology`). Each new shape or size means another fixture with the same
build/teardown code. Nothing checks the built topology either. While working on this I hit
two broken builders: the 3-tier Clos uses ports that don't exist, and the sample yaml
loads empty. Neither raises anything; you only find out when some unrelated assert fails.
On top of that, sharing a topology across tests is fast, but if one test changes it,
every later test is working with a modified object.

## 2. Approach

Tests ask for a topology with a marker and get it from a `topology` fixture:

```python
@pytest.mark.requires_topology("spine_leaf", spines=2, leaves=4)
def test_ecmp(topology): ...

@pytest.mark.requires_topology("p2p", scope="function")  # own copy, ok to modify
def test_link_down(topology): ...
```

The plugin builds the topology, runs some checks on it, caches it for the requested scope
(session if not given), and tears it down when the scope ends.

## 3. Architecture

`TopologyManager` does the work. There's one per pytest process, kept in `config.stash`.
It holds:

- the factories (`spine_leaf`, `clos`, `p2p`, `yaml`), with more registrable through a
  `pytest_topology_register` hook
- the checks: `Topology.validate()` plus my own (not empty, links use real ports, no port
  used twice, valid/unique loopbacks, every spine connected to every leaf). More can be
  added through `pytest_topology_validate`.
- a cache keyed on `(name, params)`

The `topology` fixture reads the marker and calls `manager.get()`. After the test it calls
`manager.release()`. A function-scoped topology is torn down right there. For a shared one,
I compare a hash of `topology.to_dict()` taken at build time against a fresh one. If they
differ, the test errors and the cached copy is thrown away. Module-scoped topologies are
released in `pytest_runtest_teardown` when `nextitem` is in a different module, and
anything left over is torn down in `pytest_sessionfinish`.

Options: `--topology-validation=strict|warn|off` (strict errors the test) and
`--topology NAME`, which runs only the tests that use that topology. The run header lists
the registered topologies, and the summary at the end prints how many were built, reused
and torn down.

## 4. Trade-offs

I went with one generic fixture plus a marker instead of a fixture per topology. New sizes
don't need code, and you can select tests by topology. The cost is that a typo in a param
only shows up at setup, not at collection.

I wrote my own small cache instead of using fixture scopes, because a fixture's scope is
fixed and can't depend on marker args. Having my own cache also made the mutation check
straightforward.

For catching mutations I considered deep-copying the topology for every test, and wrapping
it read-only. Copying throws away the point of sharing. The wrapper is awkward because
devices are full of plain dicts and lists. Hashing is cheap, and it tells you which test
did it.

The cache is per process, so it works with xdist without any locking. Each worker might
build its own copy, which is fine for in-memory objects but not for real lab gear.

## 5. Future improvements

- Reservations/locking across xdist workers for real testbeds
- Validate factory params at collection time
- Ask for capabilities instead of names (e.g. `min_spines=2`)
- Push config into the containers once the topology is up and wait for convergence
- Dump the topology into the report when a test fails
- Tests for the plugin itself with `pytester`
