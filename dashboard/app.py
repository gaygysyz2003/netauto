"""
app.py
------
Flask dashboard for netauto.
Shows live device status, interface states, and anomaly history.

Run: python3 dashboard/app.py
Then open: http://localhost:5000
"""

import sqlite3
import json
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
    .subtitle { font-size: 13px; color: #64748b; margin-bottom: 28px; }
    .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 16px; margin-bottom: 28px; }
    .card { background: #1e2130; border: 1px solid #2d3348; border-radius: 12px; padding: 20px; }
    .card-title { font-size: 11px; font-weight: 500; color: #64748b; text-transform: uppercase;
                  letter-spacing: .06em; margin-bottom: 8px; }
    .card-value { font-size: 32px; font-weight: 700; color: #fff; }
    .card-value.green { color: #22c55e; }
    .card-value.red   { color: #ef4444; }
    .card-value.yellow{ color: #f59e0b; }
    .section-title { font-size: 15px; font-weight: 600; color: #fff; margin-bottom: 12px; }
    table { width: 100%; border-collapse: collapse; font-size: 13px; }
    th { text-align: left; padding: 8px 12px; color: #64748b; font-weight: 500;
         font-size: 11px; text-transform: uppercase; border-bottom: 1px solid #2d3348; }
    td { padding: 10px 12px; border-bottom: 1px solid #1a1f2e; }
    tr:last-child td { border-bottom: none; }
    tr:hover td { background: #252a3d; }
    .badge { display: inline-block; padding: 2px 8px; border-radius: 99px; font-size: 11px; font-weight: 500; }
    .badge.up      { background: #14532d; color: #22c55e; }
    .badge.down    { background: #450a0a; color: #ef4444; }
    .badge.warning { background: #451a03; color: #f59e0b; }
    .anomaly-card { background: #1e2130; border: 1px solid #2d3348; border-radius: 12px;
                    padding: 16px 20px; margin-bottom: 10px; }
    .anomaly-card.flap     { border-left: 3px solid #f59e0b; }
    .anomaly-card.mismatch { border-left: 3px solid #ef4444; }
    .anomaly-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px; }
    .anomaly-name { font-size: 14px; font-weight: 500; color: #fff; }
    .anomaly-time { font-size: 11px; color: #64748b; }
    .anomaly-detail { font-size: 12px; color: #94a3b8; }
    .all-clear { background: #14532d; border: 1px solid #166534; border-radius: 12px;
                 padding: 20px; text-align: center; color: #22c55e; font-weight: 500; }
    .refresh-note { font-size: 11px; color: #475569; text-align: right; margin-top: 20px; }
    .table-wrap { background: #1e2130; border: 1px solid #2d3348; border-radius: 12px;
                  padding: 20px; margin-bottom: 28px; overflow-x: auto; }
  </style>
</head>
<body>

<h1>⚡ NetAuto Dashboard</h1>
<p class="subtitle">Auto-refreshes every 30 seconds &nbsp;·&nbsp; Database: netauto.db</p>

<!-- Stat cards -->
<div class="grid">
  <div class="card">
    <div class="card-title">Device</div>
    <div class="card-value">{{ hostname }}</div>
  </div>
  <div class="card">
    <div class="card-title">Interfaces</div>
    <div class="card-value">{{ total_interfaces }}</div>
  </div>
  <div class="card">
    <div class="card-title">Up</div>
    <div class="card-value green">{{ up_count }}</div>
  </div>
  <div class="card">
    <div class="card-title">Down</div>
    <div class="card-value {% if down_count > 0 %}red{% else %}green{% endif %}">{{ down_count }}</div>
  </div>
  <div class="card">
    <div class="card-title">Anomalies Detected</div>
    <div class="card-value {% if anomaly_count > 0 %}red{% else %}green{% endif %}">{{ anomaly_count }}</div>
  </div>
  <div class="card">
    <div class="card-title">Total Collections</div>
    <div class="card-value">{{ total_rows }}</div>
  </div>
</div>

<!-- Interface table -->
<div class="table-wrap">
  <div class="section-title">Interface State (latest collection)</div>
  <table>
    <thead>
      <tr>
        <th>Interface</th>
        <th>Admin</th>
        <th>Oper</th>
        <th>Status</th>
      </tr>
    </thead>
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

<!-- Anomalies -->
<div class="section-title">Anomaly Feed</div>
{% if anomaly_count == 0 %}
  <div class="all-clear">✓ All clear — no anomalies detected across {{ total_rows }} data points</div>
{% else %}
  {% for f in flaps %}
  <div class="anomaly-card flap">
    <div class="anomaly-header">
      <div class="anomaly-name">⚠ {{ f.hostname }} / {{ f.interface }}</div>
      <div class="anomaly-time">{{ f.at }}</div>
    </div>
    <div class="anomaly-detail">State change: {{ f.from_status }} → {{ f.to_status }}</div>
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
{% endif %}

<p class="refresh-note">Last rendered: {{ generated_at }}</p>

</body>
</html>
"""

def get_dashboard_data():
    db = sqlite3.connect(DB_PATH)
    rows = load_data(db)
    total_rows = db.execute("SELECT COUNT(*) FROM interface_state").fetchone()[0]
    db.close()

    if not rows:
        return {}

    # Latest collection only
    latest_time = rows[-1][0]
    latest = [r for r in rows if r[0] == latest_time]

    interfaces = [
        {"name": r[2], "admin_status": r[3], "oper_status": r[4]}
        for r in latest
    ]

    hostname   = latest[0][1]
    up_count   = sum(1 for i in interfaces if i["oper_status"] == "up")
    down_count = sum(1 for i in interfaces if i["oper_status"] == "down")

    flaps      = detect_flaps(rows)
    mismatches = detect_mismatches(rows)

    return {
        "hostname":         hostname,
        "total_interfaces": len(interfaces),
        "up_count":         up_count,
        "down_count":       down_count,
        "interfaces":       interfaces,
        "flaps":            flaps,
        "mismatches":       mismatches,
        "anomaly_count":    len(flaps) + len(mismatches),
        "total_rows":       total_rows,
        "generated_at":     datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }


@app.route("/")
def index():
    data = get_dashboard_data()
    return render_template_string(HTML, **data)


@app.route("/api/status")
def api_status():
    """JSON endpoint — useful for future integrations."""
    return jsonify(get_dashboard_data())


if __name__ == "__main__":
    print("\n  NetAuto Dashboard running at http://localhost:5000")
    print("  Press Ctrl+C to stop\n")
    app.run(debug=True, port=5000)
