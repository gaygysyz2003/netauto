#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

echo "Starting 3-node eBGP lab..."
docker compose up -d

echo "Waiting for BGP convergence..."
for i in $(seq 1 30); do
    established=$(docker exec router1 vtysh -c "show bgp summary" 2>/dev/null \
        | grep -c ":" || true)
    if [ "$established" -ge 2 ]; then
        echo "BGP converged after ${i} attempts"
        docker ps --format "table {{.Names}}\t{{.Status}}"
        exit 0
    fi
    sleep 5
done

echo "BGP did not converge within 150s" >&2
docker exec router1 vtysh -c "show bgp summary" || true
exit 1
