"""
monitor_bgp.py
--------------
Polls BGP session state and routes from all 3 FRR routers
using docker exec + vtysh, stores results in SQLite,
and detects BGP anomalies (session drops, route changes).

Run: python3 bgp_lab/monitor_bgp.py
"""

import subprocess
import sqlite3
import datetime
import re
import json

DB_PATH = "netauto.db"

ROUTERS = [
    {"name": "router1", "asn": 65001},
    {"name": "router2", "asn": 65002},
    {"name": "router3", "asn": 65003},
]

def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS bgp_sessions (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            collected_at TEXT NOT NULL,
            router       TEXT NOT NULL,
            local_asn    INTEGER NOT NULL,
            neighbor     TEXT NOT NULL,
            remote_asn   INTEGER NOT NULL,
            state        TEXT NOT NULL,
            uptime       TEXT NOT NULL,
            prefixes_rx  TEXT NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS bgp_routes (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            collected_at TEXT NOT NULL,
            router       TEXT NOT NULL,
            network      TEXT NOT NULL,
            next_hop     TEXT NOT NULL,
            path         TEXT NOT NULL,
            best         INTEGER NOT NULL
        )
    """)
    conn.commit()
    return conn

def vtysh(router_name, command):
    result = subprocess.run(
        ["docker", "exec", router_name, "vtysh", "-c", command],
        capture_output=True, text=True, timeout=10
    )
    return result.stdout

def parse_bgp_summary(output, router_name, local_asn):
    """
    Parse `show bgp summary json`.

    The text output puts the Up/Down timer and the State/PfxRcd field in
    fixed columns, and the timer is always HH:MM:SS regardless of state.
    Any colon-based state check is therefore always true. The JSON gives
    an explicit per-peer state key instead.
    """
    sessions = []
    data = json.loads(output)
    peers = data.get("ipv4Unicast", {}).get("peers", {})

    for neighbor, peer in peers.items():
        sessions.append({
            "router":      router_name,
            "local_asn":   local_asn,
            "neighbor":    neighbor,
            "remote_asn":  str(peer.get("remoteAs", "")),
            "state":       peer.get("state", "Unknown"),
            "uptime":      peer.get("peerUptime", "never"),
            "prefixes_rx": str(peer.get("pfxRcd", 0)),
        })
    return sessions

def parse_bgp_routes(output, router_name):
    """
    Parse lines like:
    *> 192.168.1.0/24   0.0.0.0   0   32768 i
    *  192.168.2.0/24   172.20.0.2   0   0 65002 i
    """
    routes = []
    last_network = None
    for line in output.split("\n"):
        if not line.strip().startswith("*"):
            continue
        best = 1 if len(line) > 1 and line[1] == ">" else 0
        # strip status chars
        clean = line[2:].strip()
        parts = clean.split()
        if not parts:
            continue
        # check if first token is a network
        if re.match(r'^\d+\.\d+\.\d+\.\d+/\d+$', parts[0]):
            last_network = parts[0]
            next_hop = parts[1] if len(parts) > 1 else "?"
            path     = " ".join(parts[4:]) if len(parts) > 4 else "local"
        else:
            # continuation line — same network, different path
            next_hop = parts[0] if parts else "?"
            path     = " ".join(parts[3:]) if len(parts) > 3 else "local"

        if last_network:
            routes.append({
                "router":   router_name,
                "network":  last_network,
                "next_hop": next_hop,
                "path":     path,
                "best":     best,
            })
    return routes

def collect_all(db):
    now = datetime.datetime.now(datetime.UTC).isoformat()
    all_sessions = []
    all_routes   = []

    for router in ROUTERS:
        name = router["name"]
        asn  = router["asn"]
        try:
            sessions = parse_bgp_summary(vtysh(name, "show bgp summary json"), name, asn)
            routes   = parse_bgp_routes(vtysh(name, "show ip bgp"), name)

            for s in sessions:
                db.execute("""
                    INSERT INTO bgp_sessions
                    (collected_at,router,local_asn,neighbor,remote_asn,state,uptime,prefixes_rx)
                    VALUES (?,?,?,?,?,?,?,?)
                """, (now, s["router"], s["local_asn"], s["neighbor"],
                      s["remote_asn"], s["state"], s["uptime"], s["prefixes_rx"]))

            for r in routes:
                db.execute("""
                    INSERT INTO bgp_routes
                    (collected_at,router,network,next_hop,path,best)
                    VALUES (?,?,?,?,?,?)
                """, (now, r["router"], r["network"],
                      r["next_hop"], r["path"], r["best"]))

            all_sessions.extend(sessions)
            all_routes.extend(routes)

        except Exception as e:
            print(f"  [ERROR] {name}: {e}")

    db.commit()
    return now, all_sessions, all_routes

def detect_anomalies(db):
    anomalies = []

    latest = db.execute("""
        SELECT router, neighbor, state, uptime
        FROM bgp_sessions
        WHERE collected_at = (SELECT MAX(collected_at) FROM bgp_sessions)
    """).fetchall()

    for router, neighbor, state, uptime in latest:
        if state != "Established":
            anomalies.append({
                "type":   "session_down",
                "router": router,
                "detail": f"BGP session to {neighbor} is {state}",
            })

    rows = db.execute("""
        SELECT collected_at, router, COUNT(*) as route_count
        FROM bgp_routes WHERE best = 1
        GROUP BY collected_at, router
        ORDER BY collected_at DESC
    """).fetchall()

    by_time = {}
    for ts, router, count in rows:
        by_time.setdefault(ts, {})[router] = count

    timestamps = sorted(by_time.keys(), reverse=True)
    if len(timestamps) >= 2:
        latest_counts = by_time[timestamps[0]]
        prev_counts   = by_time[timestamps[1]]
        for router, count in latest_counts.items():
            if router in prev_counts and count < prev_counts[router]:
                anomalies.append({
                    "type":   "route_loss",
                    "router": router,
                    "detail": f"Best routes dropped from {prev_counts[router]} to {count}",
                })

    return anomalies

def print_results(collected_at, sessions, routes, anomalies):
    print()
    print("=" * 62)
    print("  BGP MONITOR — NetAuto")
    print(f"  Collected: {collected_at}")
    print("=" * 62)

    print(f"\n  BGP Sessions ({len(sessions)} total)")
    print(f"  {'Router':<10} {'Neighbor':<16} {'RemoteAS':<10} {'State':<14} Uptime")
    print(f"  {'-'*10} {'-'*16} {'-'*10} {'-'*14} {'-'*10}")
    for s in sessions:
        c = "\033[92m" if s["state"] == "Established" else "\033[91m"
        print(f"  {s['router']:<10} {s['neighbor']:<16} {s['remote_asn']:<10} {c}{s['state']:<14}\033[0m {s['uptime']}")

    best_routes = [r for r in routes if r["best"]]
    print(f"\n  BGP Best Routes ({len(best_routes)} total)")
    print(f"  {'Router':<10} {'Network':<20} {'Next Hop':<16} Path")
    print(f"  {'-'*10} {'-'*20} {'-'*16} {'-'*15}")
    for r in best_routes:
        print(f"  {r['router']:<10} {r['network']:<20} {r['next_hop']:<16} {r['path']}")

    print(f"\n  Anomalies: {len(anomalies)}")
    if anomalies:
        for a in anomalies:
            print(f"  \033[91m⚠  [{a['type']}] {a['router']}: {a['detail']}\033[0m")
    else:
        print("  \033[92m✓  All BGP sessions Established, routes stable\033[0m")
    print("=" * 62)
    print()

def main():
    db = init_db()
    print("\nPolling BGP state from all routers...")
    collected_at, sessions, routes = collect_all(db)
    anomalies = detect_anomalies(db)
    print_results(collected_at, sessions, routes, anomalies)
    db.close()

if __name__ == "__main__":
    main()
