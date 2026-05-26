"""
bgp_policy.py
-------------
Reads a YAML BGP route policy file and pushes route-maps
and prefix-lists to all routers via docker exec/vtysh.

This is how hyperscalers manage BGP policy at scale —
policy as code, not manual CLI.

Run: python3 policy/bgp_policy.py --policy policy/policies/example.yaml
"""

import subprocess
import yaml
import argparse
import datetime
import re

def vtysh_commands(router, commands):
    cmd_str = " ".join([f'-c "{c}"' for c in commands])
    full_cmd = f'docker exec {router} vtysh {cmd_str}'
    result = subprocess.run(
        full_cmd, shell=True, capture_output=True, text=True, timeout=15
    )
    return result.stdout, result.stderr

def build_prefix_list(router_name, router_cfg):
    commands = ["configure terminal"]
    for i, prefix in enumerate(router_cfg.get("advertise", []), start=10):
        commands.append(f"ip prefix-list ADVERTISE-OUT seq {i} permit {prefix}")
    commands.extend(["end", "write memory"])
    return commands

def build_route_map(router_name, router_cfg):
    commands = [
        "configure terminal",
        "route-map EXPORT-POLICY permit 10",
        " match ip address prefix-list ADVERTISE-OUT",
    ]
    for community in router_cfg.get("communities", []):
        commands.append(f" set community {community}")
    commands.extend(["exit", "end", "write memory"])
    return commands

def apply_max_prefix(router_cfg, neighbor_ip, max_prefixes):
    return [
        "configure terminal",
        f"router bgp {router_cfg['asn']}",
        " address-family ipv4 unicast",
        f"  neighbor {neighbor_ip} maximum-prefix {max_prefixes}",
        " exit-address-family",
        "end",
        "write memory"
    ]

def get_neighbor_ips(router_name):
    result = subprocess.run(
        ["docker", "exec", router_name, "vtysh", "-c", "show bgp summary"],
        capture_output=True, text=True, timeout=10
    )
    neighbors = {}
    in_table = False
    for line in result.stdout.split("\n"):
        if line.strip().startswith("Neighbor"):
            in_table = True
            continue
        if not in_table:
            continue
        parts = line.strip().split()
        if len(parts) >= 3 and re.match(r'^\d+\.\d+\.\d+\.\d+$', parts[0]):
            neighbors[parts[2]] = parts[0]
    return neighbors

def verify_sessions(routers):
    all_good = True
    for router_name in routers:
        result = subprocess.run(
            ["docker", "exec", router_name, "vtysh", "-c", "show bgp summary"],
            capture_output=True, text=True, timeout=10
        )
        in_table = False
        for line in result.stdout.split("\n"):
            if line.strip().startswith("Neighbor"):
                in_table = True
                continue
            if not in_table:
                continue
            parts = line.strip().split()
            if len(parts) >= 9 and re.match(r'^\d+\.\d+\.\d+\.\d+$', parts[0]):
                neighbor = parts[0]
                uptime   = parts[8]
                state    = "Established" if ":" in uptime else uptime
                color    = "\033[92m" if state == "Established" else "\033[91m"
                print(f"    {router_name} → {neighbor}: {color}{state}\033[0m")
                if state != "Established":
                    all_good = False
    return all_good

def deploy_policy(policy_file):
    print(f"\n{'='*60}")
    print(f"  BGP Policy Automation Engine")
    print(f"  Policy file : {policy_file}")
    print(f"  Deployed at : {datetime.datetime.now().isoformat()}")
    print(f"{'='*60}\n")

    with open(policy_file) as f:
        policy = yaml.safe_load(f)

    routers = policy.get("routers", {})

    for router_name, router_cfg in routers.items():
        print(f"  Deploying policy to {router_name} (AS{router_cfg['asn']})...")

        out, err = vtysh_commands(router_name, build_prefix_list(router_name, router_cfg))
        print(f"    ✓ Prefix-list ADVERTISE-OUT configured")

        out, err = vtysh_commands(router_name, build_route_map(router_name, router_cfg))
        print(f"    ✓ Route-map EXPORT-POLICY configured")

        neighbor_ips = get_neighbor_ips(router_name)
        for accept in router_cfg.get("accept_from", []):
            remote_asn   = str(accept["asn"])
            max_prefixes = accept["max_prefixes"]
            if remote_asn in neighbor_ips:
                neighbor_ip = neighbor_ips[remote_asn]
                vtysh_commands(router_name, apply_max_prefix(router_cfg, neighbor_ip, max_prefixes))
                print(f"    ✓ Max-prefix {max_prefixes} set for AS{remote_asn} ({neighbor_ip})")
        print()

    print(f"  Verifying BGP sessions after policy deployment...\n")
    all_good = verify_sessions(routers)

    print()
    print(f"{'='*60}")
    if all_good:
        print(f"  \033[92m✓ Policy deployed to {len(routers)} routers — all BGP sessions healthy\033[0m")
    else:
        print(f"  \033[91m⚠ Some BGP sessions not Established — check router logs\033[0m")
    print(f"{'='*60}\n")

def main():
    parser = argparse.ArgumentParser(description="BGP Policy Automation Engine")
    parser.add_argument(
        "--policy",
        default="policy/policies/example.yaml",
        help="Path to YAML policy file"
    )
    args = parser.parse_args()
    deploy_policy(args.policy)

if __name__ == "__main__":
    main()
