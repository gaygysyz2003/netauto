"""
Shared BGP output parsing.

Both the monitor and the gRPC telemetry client need to turn FRR output
into structured session data. This lived in two places and diverged: a
bug fixed in one copy stayed live in the other. One implementation now.
"""

import json


def parse_bgp_summary(output, router_name, local_asn=None):
    """Parse `show bgp summary json` into a list of session dicts.

    The text output is not safe to parse positionally: the Up/Down column
    is HH:MM:SS in every FSM state, so inferring Established from a colon
    is always true. JSON carries an explicit per-peer state.
    """
    data = json.loads(output)
    peers = data.get("ipv4Unicast", {}).get("peers", {})

    return [
        {
            "router":      router_name,
            "local_asn":   local_asn,
            "neighbor":    neighbor,
            "remote_asn":  str(peer.get("remoteAs", "")),
            "state":       peer.get("state", "Unknown"),
            "uptime":      peer.get("peerUptime", "never"),
            "prefixes_rx": str(peer.get("pfxRcd", 0)),
        }
        for neighbor, peer in peers.items()
    ]
