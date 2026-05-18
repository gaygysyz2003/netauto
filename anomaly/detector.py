"""
detector.py
-----------
Reads interface state history from netauto.db and flags anomalies.
An anomaly is any interface that has CHANGED state between collections.
Also flags any interface that is admin-up but oper-down.

Run: python3 anomaly/detector.py
"""

import sqlite3
import datetime

DB_PATH = "netauto.db"

def load_data(db):
    rows = db.execute("""
        SELECT collected_at, hostname, name, admin_status, oper_status
        FROM interface_state
        ORDER BY collected_at ASC
    """).fetchall()
    return rows

def detect_flaps(rows):
    history = {}

    for collected_at, hostname, name, admin_status, oper_status in rows:
        key = (hostname, name)

        if key not in history:
            history[key] = []

        history[key].append((collected_at, oper_status))

    flaps = []

    for (hostname, name), timeline in history.items():
        for i in range(1, len(timeline)):
            prev_time, prev_status = timeline[i - 1]
            curr_time, curr_status = timeline[i]

            if prev_status != curr_status:
                flaps.append({
                    "hostname": hostname,
                    "interface": name,
                    "from_status": prev_status,
                    "to_status": curr_status,
                    "at": curr_time,
                })

    return flaps

def detect_mismatches(rows):
    latest_time = rows[-1][0]
    latest = [r for r in rows if r[0] == latest_time]

    mismatches = []

    for collected_at, hostname, name, admin_status, oper_status in latest:
        if admin_status == "up" and oper_status == "down":
            mismatches.append({
                "hostname": hostname,
                "interface": name,
                "issue": "admin-up but oper-down",
                "at": collected_at,
            })

    return mismatches

def print_anomalies(flaps, mismatches):
    print()
    print("=" * 56)
    print("  ANOMALY DETECTION REPORT")
    print(f"  Generated: {datetime.datetime.now(datetime.UTC).isoformat()}")
    print("=" * 56)

    print(f"\n  [1] State Changes: {len(flaps)} found")

    if flaps:
        for f in flaps:
            print(f"      WARNING: {f['hostname']} / {f['interface']}")
            print(f"      {f['from_status']} -> {f['to_status']} at {f['at']}")
    else:
        print("      No state changes detected across collections")

    print(f"\n  [2] Admin-up / Oper-down mismatches: {len(mismatches)} found")

    if mismatches:
        for m in mismatches:
            print(f"      WARNING: {m['hostname']} / {m['interface']}")
            print(f"      Issue: {m['issue']}")
            print(f"      At   : {m['at']}")
    else:
        print("      No mismatches detected")

    print()
    print("=" * 56)

    total = len(flaps) + len(mismatches)

    if total == 0:
        print("  STATUS: ALL CLEAR — network looks healthy")
    else:
        print(f"  STATUS: {total} ANOMALY(S) DETECTED — review above")

    print("=" * 56)
    print()

def main():
    db = sqlite3.connect(DB_PATH)
    rows = load_data(db)
    db.close()

    if len(rows) < 2:
        print("Not enough data yet. Run collector/poller.py a few more times first.")
        return

    print(f"\nAnalyzing {len(rows)} rows from {DB_PATH}...")

    flaps = detect_flaps(rows)
    mismatches = detect_mismatches(rows)

    print_anomalies(flaps, mismatches)

if __name__ == "__main__":
    main()
