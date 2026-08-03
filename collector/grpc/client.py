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
from collector.bgp_parser import parse_bgp_summary

SERVER  = "localhost:50051"
ROUTERS = ["router1", "router2", "router3"]

def vtysh(router, command):
    result = subprocess.run(
        ["docker", "exec", router, "vtysh", "-c", command],
        capture_output=True, text=True, timeout=10
    )
    return result.stdout

def generate_updates():
    """Generator that yields BGP updates as a stream."""
    print("\n  Collecting BGP state from all routers...")
    for router in ROUTERS:
        try:
            output   = vtysh(router, "show bgp summary json")
            sessions = parse_bgp_summary(output, router)
            now      = datetime.datetime.now(datetime.UTC).isoformat()
            for s in sessions:
                print(f"  [CLIENT] Streaming: {s['router']} \u2192 "
                      f"{s['neighbor']} ({s['state']})")
                yield telemetry_pb2.BGPUpdate(
                    router=s["router"],
                    neighbor=s["neighbor"],
                    remote_asn=s["remote_asn"],
                    state=s["state"],
                    uptime=s["uptime"],
                    prefixes_rx=s["prefixes_rx"],
                    timestamp=now,
                )
        except Exception as e:
            print(f"  [ERROR] {router}: {e}")

def main():
    print(f"\n  Connecting to gRPC server at {SERVER}...")
    channel = grpc.insecure_channel(SERVER)
    stub    = telemetry_pb2_grpc.TelemetryServiceStub(channel)

    # Stream BGP state to server
    try:
        grpc.channel_ready_future(channel).result(timeout=5)
    except grpc.FutureTimeoutError:
        print(f"  [ERROR] No gRPC server at {SERVER}. Start it with:")
        print("          python3 collector/grpc/server.py")
        return

    response = stub.StreamBGPState(generate_updates(), timeout=30)
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
