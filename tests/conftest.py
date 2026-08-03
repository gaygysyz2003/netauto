import pathlib
import sqlite3
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "bgp_lab"))

FIXTURES = pathlib.Path(__file__).parent / "fixtures"


@pytest.fixture
def bgp_summary_established():
    """router1 with both peers up. Captured from FRR 8.4."""
    return (FIXTURES / "bgp_summary_established.json").read_text()


@pytest.fixture
def bgp_summary_peer_down():
    """router1 after router2 was stopped. 172.20.0.2 is in Connect."""
    return (FIXTURES / "bgp_summary_peer_down.json").read_text()


@pytest.fixture
def db():
    """Empty schema, in memory. No file, no cleanup."""
    conn = sqlite3.connect(":memory:")
    conn.execute("""
        CREATE TABLE bgp_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            collected_at TEXT NOT NULL, router TEXT NOT NULL,
            local_asn INTEGER NOT NULL, neighbor TEXT NOT NULL,
            remote_asn INTEGER NOT NULL, state TEXT NOT NULL,
            uptime TEXT NOT NULL, prefixes_rx TEXT NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE bgp_routes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            collected_at TEXT NOT NULL, router TEXT NOT NULL,
            network TEXT NOT NULL, next_hop TEXT NOT NULL,
            path TEXT NOT NULL, best INTEGER NOT NULL
        )
    """)
    yield conn
    conn.close()


def add_session(conn, at, router, neighbor, state, uptime="00:01:00"):
    conn.execute(
        "INSERT INTO bgp_sessions "
        "(collected_at,router,local_asn,neighbor,remote_asn,state,uptime,prefixes_rx) "
        "VALUES (?,?,?,?,?,?,?,?)",
        (at, router, 65001, neighbor, 65002, state, uptime, "1"),
    )


def add_routes(conn, at, router, count):
    """Insert `count` best routes for a router at a given collection time."""
    for i in range(count):
        conn.execute(
            "INSERT INTO bgp_routes "
            "(collected_at,router,network,next_hop,path,best) VALUES (?,?,?,?,?,?)",
            (at, router, f"192.168.{i + 1}.0/24", "0.0.0.0", "i", 1),
        )
