"""
Prometheus metrics for BGP telemetry.

SQLite keeps the durable record of session state over time. Prometheus
keeps the time series used for alerting. Different questions: SQLite is
queried relationally after the fact, Prometheus is scraped continuously
and evaluated against alert rules.
"""

from prometheus_client import Counter, Gauge, start_http_server

FSM_STATES = {
    "Idle": 1, "Connect": 2, "Active": 3,
    "OpenSent": 4, "OpenConfirm": 5, "Established": 6,
}

# Gauge: moves both directions as sessions come up and go down.
bgp_session_state = Gauge(
    "bgp_session_state",
    "BGP FSM state (6=Established)",
    ["router", "neighbor", "remote_asn"],
)

bgp_prefixes_received = Gauge(
    "bgp_prefixes_received", "Prefixes received from peer",
    ["router", "neighbor"],
)

# Counter: only increases, so rate() gives transitions/sec. Flap alerting
# is built on this.
bgp_session_transitions = Counter(
    "bgp_session_transitions_total", "FSM state changes",
    ["router", "neighbor"],
)

telemetry_updates = Counter(
    "netauto_telemetry_updates_total", "Updates received over gRPC",
    ["router"],
)

_last_state = {}


def record_update(router, neighbor, remote_asn, state, prefixes_rx):
    """Update all metrics for one BGP session observation."""
    value = FSM_STATES.get(state, 0)
    key = (router, neighbor)

    if key in _last_state and _last_state[key] != value:
        bgp_session_transitions.labels(router=router, neighbor=neighbor).inc()
    _last_state[key] = value

    bgp_session_state.labels(
        router=router, neighbor=neighbor, remote_asn=remote_asn
    ).set(value)

    try:
        bgp_prefixes_received.labels(
            router=router, neighbor=neighbor
        ).set(int(prefixes_rx))
    except (TypeError, ValueError):
        pass

    telemetry_updates.labels(router=router).inc()


def serve_metrics(port=9101):
    start_http_server(port)
    return port
