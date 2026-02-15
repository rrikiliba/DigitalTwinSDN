import requests
import shutil
import time
import sys

RYU_API_HOST = "127.0.0.1"
RYU_API_PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8080
RYU_API_BASE_URL = f"http://{RYU_API_HOST}:{RYU_API_PORT}"
POLL_INTERVAL = 2

# Need to keep previous stats to calculate speed/throughput
prev_stats = {}

def fetch_api_data(endpoint: str):
    url = f"{RYU_API_BASE_URL}{endpoint}"
    try:
        response = requests.get(url, timeout=2)
        response.raise_for_status()
        return response.json()
    except Exception:
        return None

def get_traffic_stats(switches_data):
    """Retrieves traffic statistics for every port on every switch."""
    global prev_stats
    current_time = time.time()
    results = []

    for sw in switches_data:
        dpid = sw.get('dpid')
        dpid_int = int(dpid, 16)
        stats = fetch_api_data(f"/stats/port/{dpid_int}")
        
        if not stats: continue
        key_str = str(dpid_int)
        if key_str not in stats: continue

        for p in stats[key_str]:
            port_no = p['port_no']
            if port_no == 'LOCAL': continue
            
            uid = f"{dpid}:{port_no}"
            rx_bytes = p['rx_bytes']
            tx_bytes = p['tx_bytes']
            
            if uid in prev_stats:
                last_data = prev_stats[uid]
                time_diff = current_time - last_data['time']
                if time_diff > 0:
                    rx_speed = (rx_bytes - last_data['rx']) / time_diff
                    tx_speed = (tx_bytes - last_data['tx']) / time_diff
                    results.append({
                        'dpid': dpid,
                        'port': port_no,
                        'rx_kbps': rx_speed / 1024,
                        'tx_kbps': tx_speed / 1024
                    })

            prev_stats[uid] = {"rx": rx_bytes, "tx": tx_bytes, "time": current_time}
    return results

def get_active_flows(switches_data):
    """Retrieves active flows to see if Ryu is learning IP routes."""
    flows_info = []
    ip_discovery_map = {} # MAC -> IP found in flows
    
    for sw in switches_data:
        dpid_int = int(sw['dpid'], 16)
        stats = fetch_api_data(f"/stats/flow/{dpid_int}")
        if stats and str(dpid_int) in stats:
            for flow in stats[str(dpid_int)]:
                match = flow.get('match', {})
                src_ip = match.get('nw_src') or match.get('ipv4_src')
                dst_ip = match.get('nw_dst') or match.get('ipv4_dst')
                src_mac = match.get('eth_src')
                
                if src_ip and dst_ip:
                    flows_info.append(f"SW {sw['dpid']}: {src_ip} -> {dst_ip}")
                
                if src_mac and src_ip:
                    ip_discovery_map[src_mac] = src_ip
                    
    return flows_info, ip_discovery_map

def pretty_print_topology(switches, links, hosts):
    size = shutil.get_terminal_size().columns
    print("\033[H\033[J", end="") # Clear screen
    print("="*size)
    print(f"{'TWIN NETWORK CHECKER':^{size}}")
    print("="*size)

    # Pre-fetch flows to enrich host data
    flows, discovered_ips = get_active_flows(switches)

    # 1. SWITCHES
    print(f"\n[1] SWITCHES ({len(switches)})")
    for sw in switches:
        ports = [p['port_no'] for p in sw.get('ports', []) if p['port_no'] != 'LOCAL']
        print(f"  DPID: {sw['dpid']} | Active Ports: {ports}")

    # 2. HOSTS
    print(f"\n[2] HOSTS ({len(hosts)})")
    if not hosts:
        print("  (No hosts discovered yet)")
    for h in hosts:
        mac = h.get('mac', 'N/A')
        ips = h.get('ipv4', [])
        
        # Fallback logic: if Ryu topology doesn't have the IP, check if it was found in flows
        ip_str = ips[0] if ips else discovered_ips.get(mac, "No IP Assigned")
        
        # Indicator if the IP was found through flow discovery
        
        port_info = h.get('port', {})
        connected_to = f"SW {port_info.get('dpid', '?')} Port {port_info.get('port_no', '?')}"
        print(f"  MAC: {mac} | IP: {ip_str:15}\n  -> Connected To: {connected_to}")

    # 3. LINKS
    print(f"\n[3] INFRASTRUCTURE LINKS ({len(links)})")
    for l in links:
        src = f"SW {l['src']['dpid']} (P{l['src']['port_no']})"
        dst = f"SW {l['dst']['dpid']} (P{l['dst']['port_no']})"
        print(f"  {src} <---> {dst}")

    # 4. ACTIVE IP FLOWS
    print(f"\n[4] ACTIVE IP FLOWS")
    if not flows:
        print("  (No IP flows recognized. Will appear as traffic is generated)")
    else:
        for f in set(flows[:10]): # Use set to remove visual duplicates
            print(f"  {f}")

    # 5. TRAFFIC
    print(f"\n[5] PORT TRAFFIC (Live)")
    traffic = get_traffic_stats(switches)
    active_traffic = [t for t in traffic if t['rx_kbps'] > 0.01 or t['tx_kbps'] > 0.01]
    
    if not active_traffic:
        print("  (No significant traffic detected)")
    for t in active_traffic:
        print(f"  SW {t['dpid']} P{t['port']:<2} | RX: {t['rx_kbps']:6.2f} KB/s | TX: {t['tx_kbps']:6.2f} KB/s")

    print("\n" + "="*size)
    print(f"Last Update: {time.strftime('%H:%M:%S')} | Polling: {POLL_INTERVAL}s")

def main():
    while True:
        try:
            switches = fetch_api_data('/v1.0/topology/switches') or []
            links = fetch_api_data('/v1.0/topology/links') or []
            hosts = fetch_api_data('/v1.0/topology/hosts') or []
            
            pretty_print_topology(switches, links, hosts)
            time.sleep(POLL_INTERVAL)
            
        except KeyboardInterrupt:
            print("\nExiting.")
            break
        except Exception as e:
            print(f"Error: {e}")
            time.sleep(POLL_INTERVAL)

if __name__ == "__main__":
    main()