"""Tests for bgp_lab/monitor_bgp.py

Tests marked REGRESSION correspond to bugs that shipped and were found by
inspecting live output. They exist to keep those bugs fixed.
"""

import pytest

from monitor_bgp import detect_anomalies, parse_bgp_summary
from conftest import add_routes, add_session


def test_established_peers_are_parsed(bgp_summary_established):
    sessions = parse_bgp_summary(bgp_summary_established, "router1", 65001)
    assert len(sessions) == 2
    assert all(s["state"] == "Established" for s in sessions)


def test_peer_fields_are_extracted(bgp_summary_established):
    sessions = parse_bgp_summary(bgp_summary_established, "router1", 65001)
    peer = next(s for s in sessions if s["neighbor"] == "172.20.0.2")
    assert peer["remote_asn"] == "65002"
    assert peer["local_asn"] == 65001


def test_down_peer_is_not_established(bgp_summary_peer_down):
    """REGRESSION: parse_bgp_summary read parts[8] as uptime and inferred
    Established from a colon. parts[8] is the Up/Down timer, HH:MM:SS in
    every FSM state, so the check was always true and the down branch was
    unreachable. A stopped peer reported Established."""
    sessions = parse_bgp_summary(bgp_summary_peer_down, "router1", 65001)
    down = next(s for s in sessions if s["neighbor"] == "172.20.0.2")
    assert down["state"] == "Connect"


def test_healthy_peer_unaffected_by_neighbor_outage(bgp_summary_peer_down):
    sessions = parse_bgp_summary(bgp_summary_peer_down, "router1", 65001)
    up = next(s for s in sessions if s["neighbor"] == "172.20.0.3")
    assert up["state"] == "Established"


def test_no_peers_returns_empty_list():
    assert parse_bgp_summary('{"ipv4Unicast":{"peers":{}}}', "router1", 65001) == []


def test_missing_address_family_does_not_raise():
    assert parse_bgp_summary("{}", "router1", 65001) == []


def test_empty_output_raises():
    """docker exec on a stopped container returns empty stdout."""
    with pytest.raises(ValueError):
        parse_bgp_summary("", "router1", 65001)


def test_established_sessions_produce_no_alert(db):
    add_session(db, "T1", "router1", "172.20.0.2", "Established")
    assert detect_anomalies(db) == []


@pytest.mark.parametrize("state", ["Connect", "Active", "Idle", "OpenSent"])
def test_any_non_established_state_alerts(db, state):
    add_session(db, "T1", "router1", "172.20.0.2", state)
    alerts = detect_anomalies(db)
    assert len(alerts) == 1
    assert alerts[0]["type"] == "session_down"


def test_only_latest_collection_is_evaluated(db):
    add_session(db, "T1", "router1", "172.20.0.2", "Connect")
    add_session(db, "T2", "router1", "172.20.0.2", "Established")
    assert detect_anomalies(db) == []


def test_route_loss_is_detected(db):
    add_routes(db, "T1", "router1", 3)
    add_routes(db, "T2", "router1", 2)
    alerts = [a for a in detect_anomalies(db) if a["type"] == "route_loss"]
    assert len(alerts) == 1
    assert "3 to 2" in alerts[0]["detail"]


def test_route_gain_is_not_an_alert(db):
    add_routes(db, "T1", "router1", 2)
    add_routes(db, "T2", "router1", 3)
    assert [a for a in detect_anomalies(db) if a["type"] == "route_loss"] == []


def test_route_loss_across_three_routers(db):
    """REGRESSION: detect_anomalies sliced results by fixed index
    (counts[:2], counts[2:4]), assuming two routers per collection. With
    three routers, counts[2] was still from the latest collection, so
    router3 was compared against itself and one router was dropped."""
    for r, n in [("router1", 3), ("router2", 3), ("router3", 3)]:
        add_routes(db, "T1", r, n)
    for r, n in [("router1", 2), ("router2", 3), ("router3", 2)]:
        add_routes(db, "T2", r, n)
    alerts = [a for a in detect_anomalies(db) if a["type"] == "route_loss"]
    assert {a["router"] for a in alerts} == {"router1", "router3"}


def test_scales_past_three_routers(db):
    """The comparison must not encode fleet size."""
    for r in ["r1", "r2", "r3", "r4", "r5"]:
        add_routes(db, "T1", r, 5)
    for r in ["r1", "r2", "r3", "r4"]:
        add_routes(db, "T2", r, 5)
    add_routes(db, "T2", "r5", 1)
    alerts = [a for a in detect_anomalies(db) if a["type"] == "route_loss"]
    assert len(alerts) == 1


def test_new_router_is_not_reported_as_loss(db):
    add_routes(db, "T1", "router1", 3)
    add_routes(db, "T2", "router1", 3)
    add_routes(db, "T2", "router2", 1)
    assert [a for a in detect_anomalies(db) if a["type"] == "route_loss"] == []


def test_empty_database_does_not_raise(db):
    assert detect_anomalies(db) == []
