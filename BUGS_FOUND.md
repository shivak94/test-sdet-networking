# Bugs found

Every bug below has a test tagged `@known_bug("BUG-xxx")` (defined in `tests/bugs.py`).
The tests assert what *should* happen, so they show up as xfail. They're strict xfails,
which means if someone fixes the bug the test fails, as a reminder to remove the marker.
BUG-003 and BUG-012 depend on timing, so I made those two non-strict.

To see the real failures: `pytest -m known_bug --runxfail`

---

## BUG-001: VLAN 4094 is rejected

File: `mock_nos/database/config_db.py:215` (`add_vlan`)

The 1-4094 range check is fine, but right after it there's `if vlan_id == 4094: raise
ValidationError("... reserved")`. 802.1Q only reserves 0 and 4095, so 4094 should be
accepted. Found it with the 1/100/4094 boundary cases in `test_config_db_vlan_config`.

Expected: VLAN 4094 is added. Actual: `ValidationError: VLAN ID 4094 is reserved`.

## BUG-002: Keepalive doesn't reset the hold timer

File: `mock_nos/protocols/bgp.py:341-347` (`receive_keepalive`)

When the session is Established, a keepalive updates `_last_keepalive_received` but not
`_hold_timer_expiry`. So the session times out 180s after coming up, no matter how many
keepalives it gets. In practice every session would flap every 3 minutes.

I tested it with a fake clock (see the `fake_clock` fixture) so I didn't have to sleep:
bring the session up, keepalive at t=120, check the hold timer at t=240.
`test_hold_timer_expires` checks that the timer does expire when there are no keepalives,
so the test setup itself is fine.

Expected: still Established. Actual: `check_hold_timer()` returns True and the session
drops to Idle. Fix is to call `_reset_hold_timer()` in that branch.

## BUG-003: SWSS route table isn't locked

File: `mock_nos/containers/swss_container.py:194-209` (`_sync_route_to_asic`), and
`get_route` / `get_all_routes` / `delete_route` don't lock either.

I started with 10 threads adding routes, and all 1000 routes made it in (single dict writes
are atomic under the GIL), so writes alone don't show the problem. Adding a thread that
calls `get_all_routes()` in a loop at the same time does: it gets a few hundred
`RuntimeError: dictionary changed size during iteration` per run.

Expected: no errors while reading. Actual: RuntimeError from the reader.

## BUG-004: Port counters don't wrap

File: `mock_nos/hal/port_manager.py:363` (`increment_counter`)

Set `rx_bytes` to `MAX_COUNTER_VALUE` and add 5.

Expected: 4 (wraps at 2^64). Actual: 18446744073709551620.

## BUG-005: Prefix length isn't range checked

File: `mock_nos/hal/route_manager.py:286-305` (`_validate_prefix`)

It only checks that the part after `/` is an int, so `10.0.0.0/33`, `10.0.0.0/-1` and
`2001:db8::/129` all get installed. `lookup()` silently skips them later because
`ip_network()` throws on them.

Expected: `add_route()` returns False. Actual: returns True. Using
`ipaddress.ip_network(prefix, strict=False)` for validation would cover v4 and v6.

## BUG-006: Priority 0 routers can become DR/BDR

File: `mock_nos/protocols/ospf.py:536-553` (`elect_dr_bdr`)

Per RFC 2328, priority 0 means the router isn't eligible. Neither the local router nor
the neighbors get filtered out. Tested both cases.

Expected: a priority 0 router is never DR or BDR. Actual: it gets elected BDR (or DR if
it's the only one).

## BUG-007: DR tie-break compares router IDs as strings

File: `mock_nos/protocols/ospf.py:560`

The candidates are sorted on `(priority, router_id)` with router_id as a string, so
"10.0.0.9" sorts above "10.0.0.10". I picked those two IDs on purpose.

Expected: DR 10.0.0.10, BDR 10.0.0.9. Actual: the other way round.

## BUG-008: OPEN from the wrong AS is accepted

File: `mock_nos/protocols/bgp.py:298-323` (`receive_open`)

Only the version is checked. `my_as` from the OPEN is never compared with the
configured `remote_as`, so a peer configured for 65002 that sends AS 65999 still moves
to OpenConfirm. It should be rejected (Bad Peer AS).

Expected: `receive_open()` returns False. Actual: True.

## BUG-009: remove_neighbor leaves its routes in loc_rib

File: `mock_nos/protocols/bgp.py:525-542`

The neighbor's routes are removed from `rib_in`, but best path selection isn't re-run,
so `loc_rib` still has a best path pointing at a neighbor that no longer exists.

Expected: prefix removed from `loc_rib`. Actual: still there.

## BUG-010: data/topologies/spine_leaf.yaml loads as an empty topology

File: `mock_nos/topology/topology_builder.py:428` (`from_yaml`) and the yaml file

In the yaml, `devices:` and `links:` are top level keys next to `topology:`, but
`from_yaml` looks for them inside `topology:`. You get a topology with 0 devices and no
error. A file written by `to_yaml()` loads fine (`test_yaml_round_trip`), so the loader
and the sample file just disagree on the format.

Expected: 2 spines, 4 leaves. Actual: 0 devices.

## BUG-011: 3-tier Clos links go to ports that don't exist

File: `mock_nos/topology/topology_builder.py:399-405` (`create_clos`)

Spines get `width*2` ports, but the spine-to-leaf links use port numbers up to
`width+4`. With width=2 that's 8 links on Ethernet5/Ethernet6, which don't exist, so
those ends don't get IPs either. `Topology.validate()` doesn't notice, because it only
looks for exact duplicate links. I found this when my topology plugin refused to build
`clos`.

Expected: every link uses an existing port. Actual: 8 links don't.

## BUG-012: Route lookup is too slow

File: `mock_nos/hal/route_manager.py:314-352` (`lookup`)

`lookup()` loops over every prefix and parses each one with `ip_network()` on every call.
With 10k routes it averages about 15 ms per lookup, against the 1 ms target in the bonus
task. The test stops after spending 1 s, since by then it can't pass anyway. Bucketing
prefixes by length (or using a trie) would fix it.

---

Other things I noticed but didn't write tests for:
- `withdraw_route` has the same issue as BUG-009. If the local route was best and gets
  withdrawn, a route learned from a peer for the same prefix isn't promoted.
- `BGPContainer.restart()` drops neighbors added with `add_neighbor()` because they're
  never written to CONFIG_DB.
- `Device(router_id="1.1.1.1")` with no loopback ends up with `router_id == ""`
  (operator precedence on device.py:103).
