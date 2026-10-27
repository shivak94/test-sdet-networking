"""
Bugs found in mock_nos (details in BUGS_FOUND.md).

Tests that hit one of these are marked xfail(strict=True), so once a bug
gets fixed the test starts failing and reminds us to drop the marker.
"""
import pytest

BUGS = {
    "BUG-001": "VLAN 4094 rejected",
    "BUG-002": "keepalive doesn't reset hold timer",
    "BUG-003": "SWSS route table not locked",
    "BUG-004": "port counters don't wrap at 2^64",
    "BUG-005": "prefix length not range checked",
    "BUG-006": "priority 0 router can become DR/BDR",
    "BUG-007": "DR tie-break compares router ids as strings",
    "BUG-008": "OPEN from wrong AS accepted",
    "BUG-009": "remove_neighbor leaves routes in loc_rib",
    "BUG-010": "spine_leaf.yaml loads empty",
    "BUG-011": "3-tier clos links to missing ports",
    "BUG-012": "route lookup is a linear scan (~15ms @ 10k)",
}


def _marks(bug_id, strict=True):
    return [
        pytest.mark.known_bug(bug_id),
        pytest.mark.xfail(reason=f"{bug_id}: {BUGS[bug_id]}", strict=strict),
    ]


def known_bug(bug_id, strict=True):
    def wrap(func):
        for mark in _marks(bug_id, strict):
            func = mark(func)
        return func
    return wrap


def bug(bug_id, *values):
    """Parametrize case that is expected to fail because of bug_id."""
    return pytest.param(*values, marks=_marks(bug_id))
