from ncclient import manager
import xml.etree.ElementTree as ET
import datetime
import sqlite3

HOST     = "10.10.20.48"
PORT     = 830
USERNAME = "developer"
PASSWORD = "C1sco12345"

DB_PATH  = "netauto.db"

HOSTNAME_FILTER = """
<native xmlns="http://cisco.com/ns/yang/Cisco-IOS-XE-native">
  <hostname/>
</native>
"""

INTERFACES_FILTER = """
<interfaces-state xmlns="urn:ietf:params:xml:ns:yang:ietf-interfaces">
  <interface>
    <name/>
    <type/>
    <admin-status/>
    <oper-status/>
  </interface>
</interfaces-state>
"""

NS = {
    "native": "http://cisco.com/ns/yang/Cisco-IOS-XE-native",
    "if":     "urn:ietf:params:xml:ns:yang:ietf-interfaces",
}

def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS interface_state (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            collected_at TEXT NOT NULL,
            hostname     TEXT NOT NULL,
            host         TEXT NOT NULL,
            name         TEXT NOT NULL,
            admin_status TEXT NOT NULL,
            oper_status  TEXT NOT NULL
        )
    """)
    conn.commit()
    return conn

def save_to_db(db, hostname, interfaces):
    now = datetime.datetime.now(datetime.UTC).isoformat()
    rows = [
        (now, hostname, HOST, i["name"], i["admin_status"], i["oper_status"])
        for i in interfaces
    ]
    db.executemany(
        "INSERT INTO interface_state (collected_at, hostname, host, name, admin_status, oper_status) VALUES (?,?,?,?,?,?)",
        rows
    )
    db.commit()
    return now

def get_hostname(conn):
    response = conn.get_config(source="running", filter=("subtree", HOSTNAME_FILTER))
    root = ET.fromstring(response.xml)
    node = root.find(".//native:hostname", NS)
    return node.text if node is not None else "unknown"

def get_interfaces(conn):
    response = conn.get(filter=("subtree", INTERFACES_FILTER))
    root = ET.fromstring(response.xml)
    interfaces = []
    for iface in root.findall(".//if:interface", NS):
        interfaces.append({
            "name":         iface.findtext("if:name",         default="—", namespaces=NS),
            "admin_status": iface.findtext("if:admin-status", default="—", namespaces=NS),
            "oper_status":  iface.findtext("if:oper-status",  default="—", namespaces=NS),
        })
    return interfaces

def print_results(hostname, interfaces, collected_at):
    print()
    print("=" * 56)
    print(f"  Hostname   : {hostname}")
    print(f"  Collected  : {collected_at}")
    print(f"  Interfaces : {len(interfaces)}")
    print("=" * 56)
    print(f"  {'Name':<28} {'Admin':<10} Oper")
    print(f"  {'-'*28} {'-'*10} {'-'*8}")
    for i in interfaces:
        oper = i["oper_status"]
        c = "\033[92m" if oper == "up" else "\033[91m"
        print(f"  {i['name']:<28} {i['admin_status']:<10} {c}{oper}\033[0m")
    print("=" * 56)

def show_db_stats(db):
    count = db.execute("SELECT COUNT(*) FROM interface_state").fetchone()[0]
    latest = db.execute("SELECT collected_at FROM interface_state ORDER BY id DESC LIMIT 1").fetchone()
    print(f"\n  Database: {DB_PATH}")
    print(f"  Total rows stored : {count}")
    print(f"  Latest collection : {latest[0] if latest else 'none'}\n")

def main():
    print(f"\nConnecting to {HOST}:{PORT}...")
    db = init_db()

    with manager.connect(
        host=HOST, port=PORT, username=USERNAME, password=PASSWORD,
        hostkey_verify=False, device_params={"name": "iosxe"},
        look_for_keys=False, allow_agent=False, timeout=30,
    ) as conn:
        print("Connected.\n")
        hostname   = get_hostname(conn)
        interfaces = get_interfaces(conn)
        collected_at = save_to_db(db, hostname, interfaces)
        print_results(hostname, interfaces, collected_at)
        show_db_stats(db)

    db.close()

if __name__ == "__main__":
    main()
