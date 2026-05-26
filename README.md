# NetAuto — Network Automation Platform

A full-stack network automation platform combining real device monitoring, BGP simulation, gRPC telemetry, Ansible config management, topology mapping, and policy-as-code. Built as a portfolio project targeting software-focused network engineering roles at hyperscalers (Meta, Google, AWS, Microsoft).

## What it does

- Connects to a real Cisco IOS-XE Cat8k router via NETCONF/YANG (RFC 6241)
- Collects interface admin/oper state and stores time-series data in SQLite
- Simulates a 3-node eBGP network (AS65001/AS65002/AS65003) using FRRouting in Docker
- Streams real-time BGP telemetry via gRPC between collector client and server
- Automates BGP config deployment across all routers using Ansible + Jinja2 templates
- Auto-generates interactive network topology maps from live BGP session data
- Deploys BGP route policies (prefix-lists, route-maps, max-prefix) from YAML files
- Detects interface flaps, admin/oper mismatches, BGP session drops, and route loss
- Generates AI-powered plain-English anomaly explanations using Google Gemini API
- Displays unified observability in an auto-refreshing Flask dashboard
- Fully containerized with Docker

## Tech stack

| Layer | Technology |
|---|---|
| Device communication | NETCONF/YANG via ncclient |
| BGP simulation | FRRouting (FRR) in Docker |
| Streaming telemetry | gRPC + Protocol Buffers |
| Config automation | Ansible + Jinja2 |
| Topology mapping | networkx + pyvis |
| Policy automation | Python + YAML |
| BGP monitoring | Python + docker exec/vtysh |
| Data storage | SQLite |
| Anomaly detection | Rule-based engine |
| AI explanations | Google Gemini API |
| Dashboard | Flask + HTML/CSS |
| Containerization | Docker + docker-compose |
| Language | Python 3.12 |

## Results

- 6/6 BGP sessions established across 3 autonomous systems
- 9 BGP best routes propagating with multipath
- gRPC streams 6 BGP updates in real time vs 30s polling intervals
- Ansible deploys full BGP config to 3 routers in under 30 seconds
- Route loss anomaly detection fires within one poll cycle of router failure
- Policy engine deploys prefix-lists, route-maps, and max-prefix limits from a single YAML file
- Interface state collected from real Cisco Cat8k via NETCONF

## Project structure

    netauto/
    collector/
        poller.py           # NETCONF interface state collection
        grpc/
            server.py       # gRPC telemetry server
            client.py       # gRPC telemetry client
            telemetry.proto # Protobuf schema
    anomaly/
        detector.py         # Anomaly detection engine
        explainer.py        # AI-powered explanations
    dashboard/
        app.py              # Unified Flask dashboard
    bgp_lab/
        docker-compose.yml  # 3-node FRR BGP lab
        monitor_bgp.py      # BGP session + route monitor
        ansible/
            deploy_bgp.yml  # Ansible playbook
            inventory.yml   # Router inventory
            frr.conf.j2     # Jinja2 config template
    topology/
        mapper.py           # Auto-generates topology map
    policy/
        bgp_policy.py       # Policy-as-code engine
        policies/
            example.yaml    # Sample BGP route policy

## Anomaly types detected

| Type | Trigger | Layer |
|---|---|---|
| Interface flap | oper_status changes between polls | NETCONF |
| Admin/oper mismatch | admin=up but oper=down | NETCONF |
| BGP session down | state != Established | BGP |
| Route loss | best route count drops | BGP |

## Quick start

    git clone https://github.com/gaygysyz2003/netauto.git
    cd netauto
    python3 -m venv venv && source venv/bin/activate
    pip install -r requirements.txt

    # Start BGP lab
    cd bgp_lab && docker compose up -d

    # Collect data
    python3 collector/poller.py
    python3 bgp_lab/monitor_bgp.py

    # Run automation
    cd bgp_lab/ansible && ansible-playbook -i inventory.yml deploy_bgp.yml
    cd ../.. && python3 policy/bgp_policy.py --policy policy/policies/example.yaml

    # Generate topology map
    python3 topology/mapper.py

    # Start gRPC telemetry
    python3 collector/grpc/server.py   # Terminal 1
    python3 collector/grpc/client.py   # Terminal 2

    # Start dashboard
    python3 dashboard/app.py
    # Open http://127.0.0.1:5000

## Skills demonstrated

NETCONF/YANG · eBGP · gRPC · Protocol Buffers · Ansible · Jinja2 · networkx · pyvis · policy-as-code · Python · Docker · SQLite · Flask · Gemini API · Linux · Git · Cisco IOS-XE · FRRouting
