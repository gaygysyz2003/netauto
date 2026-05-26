"""
mapper.py
---------
Pulls LLDP neighbor data from routers via docker exec/vtysh,
builds a network topology graph using networkx,
and renders an interactive HTML map using pyvis.

Run: python3 topology/mapper.py
Then open: topology/network_map.html
"""

import subprocess
import re
import networkx as nx
from pyvis.network import Network
import datetime
import os

ROUTERS = [
    {"name": "router1", "asn": 65001, "network": "192.168.1.0/24"},
    {"name": "router2", "asn": 65002, "network": "192.168.2.0/24"},
    {"name": "router3", "asn": 65003, "network": "192.168.3.0/24"},
]

OUTPUT_FILE = "topology/network_map.html"


def vtysh(router, command):
    result = subprocess.run(
        ["docker", "exec", router, "vtysh", "-c", command],
        capture_output=True, text=True, timeout=10
    )
    return result.stdout


def get_bgp_neighbors(router_name):
    """Pull BGP neighbor IPs from the router."""
    output = vtysh(router_name, "show bgp summary")
    neighbors = []
    in_table = False
    for line in output.split("\n"):
        if line.strip().startswith("Neighbor"):
            in_table = True
            continue
        if not in_table:
            continue
        line = line.strip()
        if not line or line.startswith("Total"):
            continue
        parts = line.split()
        if len(parts) >= 3:
            neighbors.append({
                "ip":         parts[0],
                "remote_asn": parts[2],
                "state":      "Established" if ":" in parts[8] else parts[8],
                "uptime":     parts[8] if ":" in parts[8] else "down",
            })
    return neighbors


def get_routes(router_name):
    """Pull BGP route count."""
    output = vtysh(router_name, "show ip bgp")
    count = 0
    for line in output.split("\n"):
        if line.strip().startswith("*>"):
            count += 1
    return count


def build_graph():
    """Build networkx graph from BGP neighbor relationships."""
    G  = nx.Graph()
    ip_to_router = {}

    # First pass — add all router nodes
    for router in ROUTERS:
        name = router["name"]
        G.add_node(name,
            label   = f"{name}\nAS{router['asn']}\n{router['network']}",
            asn     = router["asn"],
            network = router["network"],
            color   = "#22c55e",
            size    = 30,
        )

    # Build IP → router mapping
    for router in ROUTERS:
        neighbors = get_bgp_neighbors(router["name"])
        for n in neighbors:
            ip_to_router[n["ip"]] = None  # placeholder

    # Second pass — add edges from BGP sessions
    seen_edges = set()
    for router in ROUTERS:
        name      = router["name"]
        neighbors = get_bgp_neighbors(router["name"])
        routes    = get_routes(name)

        # Update node with route count
        G.nodes[name]["title"] = (
            f"Router: {name}\n"
            f"ASN: {router['asn']}\n"
            f"Network: {router['network']}\n"
            f"BGP Routes: {routes}\n"
            f"Neighbors: {len(neighbors)}"
        )

        for n in neighbors:
            # Find which router this neighbor IP belongs to
            target = None
            for r in ROUTERS:
                nbrs = get_bgp_neighbors(r["name"])
                for nb in nbrs:
                    pass
            # Match by ASN
            for r in ROUTERS:
                if str(r["asn"]) == str(n["remote_asn"]):
                    target = r["name"]
                    break

            if target and target != name:
                edge_key = tuple(sorted([name, target]))
                if edge_key not in seen_edges:
                    seen_edges.add(edge_key)
                    color = "#22c55e" if n["state"] == "Established" else "#ef4444"
                    G.add_edge(name, target,
                        label = f"eBGP\nAS{router['asn']}↔AS{n['remote_asn']}",
                        color = color,
                        width = 3,
                        title = (
                            f"Session: {n['state']}\n"
                            f"Uptime: {n['uptime']}\n"
                            f"AS{router['asn']} ↔ AS{n['remote_asn']}"
                        )
                    )
    return G


def render_map(G):
    """Render the networkx graph as an interactive HTML file."""
    net = Network(
        height        = "700px",
        width         = "100%",
        bgcolor       = "#0f1117",
        font_color    = "#e2e8f0",
        notebook      = False,
        directed      = False,
    )

    net.from_nx(G)

    # Style nodes
    for node in net.nodes:
        node["shape"]       = "dot"
        node["size"]        = 35
        node["color"]       = "#22c55e"
        node["font"]        = {"color": "#ffffff", "size": 14}
        node["borderWidth"] = 2

    # Style edges
    for edge in net.edges:
        edge["color"] = "#22c55e"
        edge["width"] = 3

    net.set_options("""
    var options = {
      "physics": {
        "enabled": true,
        "barnesHut": {
          "gravitationalConstant": -8000,
          "springLength": 200
        }
      },
      "interaction": {
        "hover": true,
        "tooltipDelay": 100
      }
    }
    """)

    os.makedirs("topology", exist_ok=True)
    net.save_graph(OUTPUT_FILE)
    print(f"\n  Topology map saved to {OUTPUT_FILE}")
    print(f"  Open it in your browser to see the interactive map\n")


def main():
    print("\nBuilding network topology from BGP sessions...")
    print(f"Collecting data from {len(ROUTERS)} routers...\n")

    G = build_graph()

    print(f"  Nodes (routers): {G.number_of_nodes()}")
    print(f"  Edges (BGP sessions): {G.number_of_edges()}")
    print()

    for u, v, data in G.edges(data=True):
        print(f"  {u} ↔ {v}  [{data.get('title', '').split(chr(10))[0]}]")

    render_map(G)

    # Open automatically in browser
    import webbrowser
    webbrowser.open(f"file://{os.path.abspath(OUTPUT_FILE)}")


if __name__ == "__main__":
    main()
