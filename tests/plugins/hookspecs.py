import pluggy

hookspec = pluggy.HookspecMarker("pytest")


@hookspec
def pytest_topology_register(manager):
    """Called once at startup. Use manager.register(name, factory) to add topologies."""


@hookspec
def pytest_topology_validate(topology, name):
    """Return a list of error strings for a freshly built topology."""
