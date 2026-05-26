"""
client.py
---------
gRPC telemetry client that polls BGP state from all routers
and streams it to the gRPC server in real time.

Run after server: python3 collector/grpc/client.py
"""

import grpc
import subprocess
import datetime
import time
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from collector.grpc import telemetry_pb2, telemetry_pb2_grpc

SERVER  = "localhost:50051"
ROUTERS = ["router1", "router2", "router3"]

def vtysh(router, command):
    result = subprocess.run(
        ["docker", "exec", router, "vtysh", "-c", command],
        capture_output=True, text=True, timeout=10
    )
    return result.stdout

def parse_bgp_summary(output, router):
    updates = []
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
        if len(parts) < 10:
            continue
        neighbor   = parts[0]
        remote_asn = parts[2]
        uptime     = parts[8]
        pfx_rcvd   = parts[9]
        state      = "Established" if ":" in uptime else uptime
        if state != "Established":
            uptime   = "down"
            pfx_rcvd = "0"

        updates.append(telemetry_pb2.BGPUpdate(
            router      = router,
            neighbor    = neighbor,
            remote_asn  = remote_asn,
            state       = state,
            uptime      = uptime,
            prefixes_rx = pfx_rcvd,
            timestamp   = datetime.datetime.now(datetime.UTC).isoformat(),
        ))
    return updates

def generate_updates():
    """Generator that yields BGP updates as a stream."""
    print("\n  Collecting BGP state from all routers...")
    for router in ROUTERS:
        try:
            output  = vtysh(router, "show bgp summary")
            updates = parse_bgp_summary(output, router)
            for update in updates:
                print(f"  [CLIENT] Streaming: {update.router} → "
                      f"{update.neighbor} ({update.state})")
                yield update
        except Exception as e:
            print(f"  [ERROR] {router}: {e}")

def main():
    print(f"\n  Connecting to gRPC server at {SERVER}...")
    channel = grpc.insecure_channel(SERVER)
    stub    = telemetry_pb2_grpc.TelemetryServiceStub(channel)

    # Stream BGP state to server
    response = stub.StreamBGPState(generate_updates())
    print(f"\n  Server response: {response.message}")

    # Query latest state back from server
    print("\n  Querying latest state from server...")
    snapshot = stub.GetLatestState(telemetry_pb2.Empty())
    print(f"\n  Latest snapshot from server ({len(snapshot.updates)} entries):")
    print(f"  {'Router':<10} {'Neighbor':<16} {'State':<14} Uptime")
    print(f"  {'-'*10} {'-'*16} {'-'*14} {'-'*10}")
    for u in snapshot.updates:
        c = "\033[92m" if u.state == "Established" else "\033[91m"
        print(f"  {u.router:<10} {u.neighbor:<16} {c}{u.state:<14}\033[0m {u.uptime}")
    print()

if __name__ == "__main__":
    main()
