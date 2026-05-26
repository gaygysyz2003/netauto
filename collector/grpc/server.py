"""
server.py
---------
gRPC telemetry server that receives BGP state streams from the client
and stores them in SQLite.

Run first: python3 collector/grpc/server.py
Then run:  python3 collector/grpc/client.py
"""

import grpc
import sqlite3
import datetime
from concurrent import futures

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from collector.grpc import telemetry_pb2, telemetry_pb2_grpc

DB_PATH = "netauto.db"
PORT    = 50051

def init_db():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS grpc_telemetry (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            received_at  TEXT NOT NULL,
            router       TEXT NOT NULL,
            neighbor     TEXT NOT NULL,
            remote_asn   TEXT NOT NULL,
            state        TEXT NOT NULL,
            uptime       TEXT NOT NULL,
            prefixes_rx  TEXT NOT NULL,
            client_ts    TEXT NOT NULL
        )
    """)
    conn.commit()
    return conn


class TelemetryServicer(telemetry_pb2_grpc.TelemetryServiceServicer):

    def StreamBGPState(self, request_iterator, context):
        """Receive a stream of BGP updates from the client."""
        db    = sqlite3.connect(DB_PATH, check_same_thread=False)
        count = 0
        now   = datetime.datetime.now(datetime.UTC).isoformat()

        for update in request_iterator:
            db.execute("""
                INSERT INTO grpc_telemetry
                (received_at, router, neighbor, remote_asn, state, uptime, prefixes_rx, client_ts)
                VALUES (?,?,?,?,?,?,?,?)
            """, (now, update.router, update.neighbor, update.remote_asn,
                  update.state, update.uptime, update.prefixes_rx, update.timestamp))

            count += 1
            color = "\033[92m" if update.state == "Established" else "\033[91m"
            print(f"  [STREAM] {update.router} → {update.neighbor} "
                  f"(AS{update.remote_asn}) {color}{update.state}\033[0m")

        db.commit()
        db.close()
        print(f"\n  [SERVER] Received and stored {count} BGP updates via gRPC stream\n")
        return telemetry_pb2.Acknowledgement(success=True, message=f"Stored {count} updates")

    def GetLatestState(self, request, context):
        """Return the latest BGP snapshot."""
        db   = sqlite3.connect(DB_PATH, check_same_thread=False)
        rows = db.execute("""
            SELECT router, neighbor, remote_asn, state, uptime, prefixes_rx, received_at
            FROM grpc_telemetry
            WHERE received_at = (SELECT MAX(received_at) FROM grpc_telemetry)
        """).fetchall()
        db.close()

        updates = [
            telemetry_pb2.BGPUpdate(
                router=r[0], neighbor=r[1], remote_asn=r[2],
                state=r[3], uptime=r[4], prefixes_rx=r[5], timestamp=r[6]
            )
            for r in rows
        ]
        return telemetry_pb2.BGPSnapshot(updates=updates)


def serve():
    db = init_db()
    db.close()

    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    telemetry_pb2_grpc.add_TelemetryServiceServicer_to_server(
        TelemetryServicer(), server
    )
    server.add_insecure_port(f"[::]:{PORT}")
    server.start()
    print(f"\n  gRPC Telemetry Server listening on port {PORT}")
    print(f"  Waiting for BGP state streams...")
    print(f"  Press Ctrl+C to stop\n")
    try:
        server.wait_for_termination()
    except KeyboardInterrupt:
        print("\n  Server stopped.")
        server.stop(0)


if __name__ == "__main__":
    serve()
