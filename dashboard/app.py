"""
app.py
------
Flask dashboard for netauto.
Shows live device status, interface states, BGP sessions, and anomaly history.

Run: python3 dashboard/app.py
Then open: http://localhost:5000
"""

import sqlite3
import datetime
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from flask import Flask, render_template_string, jsonify
from anomaly.detector import load_data, detect_flaps, detect_mismatches

app = Flask(__name__)
DB_PATH = "netauto.db"

HTML = """
<!DOCTYPE html>
<html>
<head>
  <title>NetAuto Dashboard</title>
  <meta http-equiv="refresh" content="30">
  <style>
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
           background: #0f1117; color: #e2e8f0; min-height: 100vh; padding: 24px; }
    h1 { font-size: 22px; font-weight: 600; color: #fff; margin-bottom: 4px; }
    h2 { font-size: 15px; font-weight: 600; color: #fff; margin-bottom: 12px; }
    .subtitle { font-size: 13px; color: #64748b; margin-bottom: 28px; }
    .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 16px; margin-bottom: 28px; }
    .card { background: #1e2130; border: 1px solid #2d3348; border-radius: 12px; padding: 20px; }
    .card-title { font-size: 11px; font-weight: 500; color: #64748b; text-transform: uppercase; letter-spacing: .06em; margin-bottom: 8px; }
    .card-value { font-size: 32px; font-weight: 700; color: #fff; }
    .card-value.green  { color: #22c55e; }
    .card-value.red    { color: #ef4444; }
    .card-value.yellow { color: #f59e0b; }
    .section { background: #1e2130; border: 1px solid #2d3348; border-radius: 12px; padding: 20px; margin-bottom: 20px; overflow-x: auto; }
    table { width: 100%; border-collapse: collapse; font-size: 13px; }
    th { text-align: left; padding: 8px 12px; color: #64748b; font-weight: 500; font-size: 11px; text-transform: uppercase; border-bottom: 1px solid #2d3348; }
    td { padding: 10px 12px; border-bottom: 1px solid #1a1f2e; }
    tr:last-child td { border-bottom: none; }
    tr:hover td { background: #252a3d; }
    .badge { display: inline-block; padding: 2px 8px; border-radius: 99px; font-size: 11px; font-weight: 500; }
    .badge.up          { background: #14532d; color: #22c55e; }
    .badge.down        { background: #450a0a; color: #ef4444; }
    .badge.established { background: #14532d; color: #22c55e; }
    .badge.active      { background: #451a03; color: #f59e0b; }
    .badge.warning     { background: #451a03; color: #f59e0b; }
    .anomaly-card { border-radius: 12px; padding: 16px 20px; margin-bottom: 10px; }
    .anomaly-card.flap     { background:#1e2130; border-left: 3px solid #f59e0b; }
    .anomaly-card.mismatch { background:#1e2130; border-left: 3px solid #ef4444; }
    .anomaly-card.bgp      { background:#1e2130; border-left: 3px solid #a855f7; }
    .anomaly-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px; }
    .anomaly-name   { font-size: 14px; font-weight: 500; color: #fff; }
    .anomaly-time   { font-size: 11px; color: #64748b; }
    .anomaly-detail { font-size: 12px; color: #94a3b8; }
    .all-clear { background: #14532d; border: 1px solid #166534; border-radius: 12px; padding: 20px; text-align: center; color: #22c55e; font-weight: 500; }
    .refresh-note { font-size: 11px; color: #475569; text-align: right; margin-top: 20px; }
    .divider { font-size: 13px; font-weight: 600; color: #94a3b8; margin: 24px 0 12px; text-transform: uppercase; letter-spacing: .06em; border-bottom: 1px solid #2d3348; padding-bottom: 8px; }
  </style>
</head>
<body>

<h1>⚡ NetAuto Dashboard</h1>
<p class="subtitle">Auto-refreshes every 30s &nbsp;·&nbsp; {{ generated_at }}</p>

<!-- Stat cards -->
<div class="grid">
  <div class="card">
    <div class="card-title">Device</div>
    <div class="card-value" style="font-size:20px;padding-top:6px">{{ hostname }}</div>
  </div>
  <div class="card">
    <div class="card-title">Interfaces Up</div>
    <div class="card-value green">{{ up_count }}</div>
  </div>
  <div class="card">
    <div class="card-title">Interfaces Down</div>
    <div class="card-value {% if down_count > 0 %}red{% else %}green{% endif %}">{{ down_count }}</div>
  </div>
  <div class="card">
    <div class="card-title">BGP Sessions</div>
    <div class="card-value {% if bgp_down > 0 %}red{% else %}green{% endif %}">{{ bgp_established }}/{{ bgp_total }}</div>
  </div>
  <div class="card">
    <div class="card-title">BGP Routes</div>
    <div class="card-value">{{ bgp_route_count }}</div>
  </div>
  <div class="card">
    <div class="card-title">Anomalies</div>
    <div class="card-value {% if anomaly_count > 0 %}red{% else %}green{% endif %}">{{ anomaly_count }}</div>
  </div>
</div>

<!-- Interface table -->
<div class="divider">Interface State — cat8000v</div>
<div class="section">
  <table>
    <thead><tr><th>Interface</th><th>Admin</th><th>Oper</th><th>Status</th></tr></thead>
    <tbody>
      {% for iface in interfaces %}
      <tr>
        <td>{{ iface.name }}</td>
        <td>{{ iface.admin_status }}</td>
        <td>{{ iface.oper_status }}</td>
        <td>
          {% if iface.admin_status == 'up' and iface.oper_status == 'up' %}
            <span class="badge up">Healthy</span>
          {% elif iface.admin_status == 'up' and iface.oper_status == 'down' %}
            <span class="badge down">Mismatch</span>
          {% else %}
            <span class="badge warning">Admin Down</span>
          {% endif %}
        </td>
      </tr>
      {% endfor %}
    </tbody>
  </table>
</div>

<!-- BGP Sessions table -->
<div class="divider">BGP Sessions — 3-Node Lab (AS65001 / AS65002 / AS65003)</div>
<div class="section">
  <table>
    <thead><tr><th>Router</th><th>Neighbor</th><th>Remote AS</th><th>State</th><th>Uptime</th><th>Prefixes Rx</th></tr></thead>
    <tbody>
      {% for s in bgp_sessions %}
      <tr>
        <td>{{ s.router }}</td>
        <td>{{ s.neighbor }}</td>
        <td>{{ s.remote_asn }}</td>
        <td>
          {% if s.state == 'Established' %}
            <span class="badge established">Established</span>
          {% else %}
            <span class="badge down">{{ s.state }}</span>
          {% endif %}
        </td>
        <td>{{ s.uptime }}</td>
        <td>{{ s.prefixes_rx }}</td>
      </tr>
      {% endfor %}
    </tbody>
  </table>
</div>

<!-- BGP Routes table -->
<div class="divider">BGP Route Table (best paths)</div>
<div class="section">
  <table>
    <thead><tr><th>Router</th><th>Network</th><th>Next Hop</th><th>AS Path</th></tr></thead>
    <tbody>
      {% for r in bgp_routes %}
      <tr>
        <td>{{ r.router }}</td>
        <td>{{ r.network }}</td>
        <td>{{ r.next_hop }}</td>
        <td>{{ r.path }}</td>
      </tr>
      {% endfor %}
    </tbody>
  </table>
</div>

<!-- Anomaly feed -->
<div class="divider">Anomaly Feed</div>
{% if anomaly_count == 0 %}
  <div class="all-clear">✓ All clear — no anomalies detected</div>
{% else %}
  {% for f in flaps %}
  <div class="anomaly-card flap">
    <div class="anomaly-header">
      <div class="anomaly-name">⚠ {{ f.hostname }} / {{ f.interface }}</div>
      <div class="anomaly-time">{{ f.at }}</div>
    </div>
    <div class="anomaly-detail">Interface flap: {{ f.from_status }} → {{ f.to_status }}</div>
  </div>
  {% endfor %}
  {% for m in mismatches %}
  <div class="anomaly-card mismatch">
    <div class="anomaly-header">
      <div class="anomaly-name">✖ {{ m.hostname }} / {{ m.interface }}</div>
      <div class="anomaly-time">{{ m.at }}</div>
    </div>
    <div class="anomaly-detail">{{ m.issue }}</div>
  </div>
  {% endfor %}
  {% for a in bgp_anomalies %}
  <div class="anomaly-card bgp">
    <div class="anomaly-header">
      <div class="anomaly-name">◈ BGP — {{ a.router }}</div>
      <div class="anomaly-time">{{ a.type }}</div>
    </div>
    <div class="anomaly-detail">{{ a.detail }}</div>
  </div>
  {% endfor %}
{% endif %}

<p class="refresh-note">Last rendered: {{ generated_at }}</p>
</body>
</html>
"""

def get_bgp_data(db):
    sessions = db.execute("""
        SELECT router, neighbor, remote_asn, state, uptime, prefixes_rx
        FROM bgp_sessions
        WHERE collected_at = (SELECT MAX(collected_at) FROM bgp_sessions)
        ORDER BY router, neighbor
    """).fetchall()

    routes = db.execute("""
        SELECT router, network, next_hop, path
        FROM bgp_routes
        WHERE best = 1
        AND collected_at = (SELECT MAX(collected_at) FROM bgp_routes)
        ORDER BY router, network
    """).fetchall()

    session_list = [
        {"router": r[0], "neighbor": r[1], "remote_asn": r[2],
         "state": r[3], "uptime": r[4], "prefixes_rx": r[5]}
        for r in sessions
    ]
    route_list = [
        {"router": r[0], "network": r[1], "next_hop": r[2], "path": r[3]}
        for r in routes
    ]
    established = sum(1 for s in session_list if s["state"] == "Established")
    return session_list, route_list, established

def get_bgp_anomalies(db):
    anomalies = []
    latest = db.execute("""
        SELECT router, neighbor, state
        FROM bgp_sessions
        WHERE collected_at = (SELECT MAX(collected_at) FROM bgp_sessions)
    """).fetchall()
    for router, neighbor, state in latest:
        if state != "Established":
            anomalies.append({
                "type": "session_down",
                "router": router,
                "detail": f"BGP session to {neighbor} is {state}"
            })
    return anomalies

def get_dashboard_data():
    db = sqlite3.connect(DB_PATH)
    rows = load_data(db)
    total_rows = db.execute("SELECT COUNT(*) FROM interface_state").fetchone()[0]

    if not rows:
        db.close()
        return {}

    latest_time = rows[-1][0]
    latest = [r for r in rows if r[0] == latest_time]
    interfaces = [{"name": r[2], "admin_status": r[3], "oper_status": r[4]} for r in latest]
    hostname   = latest[0][1]
    up_count   = sum(1 for i in interfaces if i["oper_status"] == "up")
    down_count = sum(1 for i in interfaces if i["oper_status"] == "down")

    flaps      = detect_flaps(rows)
    mismatches = detect_mismatches(rows)

    bgp_sessions, bgp_routes, bgp_established = get_bgp_data(db)
    bgp_anomalies = get_bgp_anomalies(db)
    db.close()

    total_anomalies = len(flaps) + len(mismatches) + len(bgp_anomalies)

    return {
        "hostname":        hostname,
        "total_interfaces": len(interfaces),
        "up_count":        up_count,
        "down_count":      down_count,
        "interfaces":      interfaces,
        "flaps":           flaps,
        "mismatches":      mismatches,
        "bgp_sessions":    bgp_sessions,
        "bgp_routes":      bgp_routes,
        "bgp_established": bgp_established,
        "bgp_total":       len(bgp_sessions),
        "bgp_down":        len(bgp_sessions) - bgp_established,
        "bgp_route_count": len(bgp_routes),
        "bgp_anomalies":   bgp_anomalies,
        "anomaly_count":   total_anomalies,
        "total_rows":      total_rows,
        "generated_at":    datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }

@app.route("/")
def index():
    data = get_dashboard_data()
    return render_template_string(HTML, **data)

@app.route("/api/status")
def api_status():
    return jsonify(get_dashboard_data())

if __name__ == "__main__":
    print("\n  NetAuto Dashboard running at http://localhost:5000")
    print("  Press Ctrl+C to stop\n")
    app.run(debug=True, port=5000)
