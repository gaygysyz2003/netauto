"""
explainer.py
------------
Uses the Gemini API to generate plain-English explanations
of network anomalies detected by detector.py.

Run: python3 anomaly/explainer.py
"""

from google import genai
import os
import json

client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])

MODEL = "gemini-2.5-flash"

def explain_anomaly(anomaly: dict) -> str:
    prompt = f"""You are a senior network engineer at a large ISP.
A monitoring system detected this network anomaly:

{json.dumps(anomaly, indent=2)}

In exactly 3 sentences:
1. What most likely caused this.
2. What the on-call engineer should check first.
3. What the risk is if unresolved.

Be specific and technical. No bullet points. Just 3 sentences."""

    response = client.models.generate_content(
        model=MODEL,
        contents=prompt,
    )

    return response.text

def main():
    flap_anomaly = {
        "type": "state_change",
        "hostname": "cat8000v",
        "interface": "GigabitEthernet1",
        "from_status": "up",
        "to_status": "down",
        "at": "2026-05-18T23:14:37+00:00",
    }

    mismatch_anomaly = {
        "type": "admin_oper_mismatch",
        "hostname": "cat8000v",
        "interface": "GigabitEthernet2",
        "issue": "admin-up but oper-down",
        "at": "2026-05-18T23:14:37+00:00",
    }

    for anomaly in [flap_anomaly, mismatch_anomaly]:
        print("\n" + "=" * 60)
        print(f"  ANOMALY: {anomaly['type']}")
        print(f"  Device : {anomaly['hostname']} / {anomaly.get('interface')}")
        print("=" * 60)
        print("\n  AI Explanation:\n")

        explanation = explain_anomaly(anomaly)
        print("  " + explanation.strip().replace("\n", "\n  "))
        print()

if __name__ == "__main__":
    main()
