import requests
import shutil
import time
import sys

RYU_API_HOST = "127.0.0.1"
RYU_API_PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8080
RYU_API_BASE_URL = f"http://{RYU_API_HOST}:{RYU_API_PORT}"
POLL_INTERVAL = 2

# Memoria Download statistics for each switch and calculate the speedper calcolare la velocità (Bytes attuali - Bytes precedenti)
# Struttura: { "dpid:port_no": { "rx": 12345, "tx": 67890, "time": 1700000.0 } }
prev_stats = {}

def fetch_api_data(endpoint: str):
    url = f"{RYU_API_BASE_URL}{endpoint}"
    try:
        response = requests.get(url, timeout=2)
        response.raise_for_status()
        return response.json()
    except Exception:
        return None

def pretty_print_traffic(switches_data):
    """
    Download statistics for each switch and calculate the speed
    """
    global prev_stats
    current_time = time.time()
    
    print(f"\n--- TRAFFIC MONITOR (Twin Network) ---")
    
    has_traffic = False

    for sw in switches_data:
        dpid = sw.get('dpid')
        # L'API di Ryu per le stats è /stats/port/<dpid_in_int>
        dpid_int = int(dpid, 16)
        stats = fetch_api_data(f"/stats/port/{dpid_int}")
        
        if not stats:
            continue

        # La risposta è un dict: { "dpid_int": [ {port_stats}, ... ] }
        key_str = str(dpid_int)
        if key_str not in stats:
            continue

        port_list = stats[key_str]
        
        for p in port_list:
            port_no = p['port_no']
            if port_no == 'LOCAL': continue # Ignora porta interna
            
            # Chiave unica per questo dato
            uid = f"{dpid}:{port_no}"
            
            rx_bytes = p['rx_bytes']
            tx_bytes = p['tx_bytes']
            
            # Calcolo velocità se abbiamo dati precedenti
            if uid in prev_stats:
                last_data = prev_stats[uid]
                time_diff = current_time - last_data['time']
                
                # Evita divisione per zero
                if time_diff > 0:
                    # Calcolo Delta
                    rx_speed = (rx_bytes - last_data['rx']) / time_diff
                    tx_speed = (tx_bytes - last_data['tx']) / time_diff
                    
                    # Converti in KB/s per leggibilità
                    rx_kbps = rx_speed / 1024
                    tx_kbps = tx_speed / 1024
                    
                    # Stampiamo solo se c'è traffico significativo (> 0.1 KB/s)
                    if rx_kbps >= 0.0:
                        has_traffic = True
                        print(f"  Switch {dpid} - Port {port_no}: RX {rx_kbps:.2f} KB/s | TX {tx_kbps:.2f} KB/s")

            # Aggiorna lo stato precedente
            prev_stats[uid] = {
                "rx": rx_bytes, 
                "tx": tx_bytes, 
                "time": current_time
            }

    if not has_traffic:
        print("  (No active traffic flow detected > 0.1 KB/s)")

def pretty_print_topology(switches_data: list, links_data: list, hosts_data: list):
    size = shutil.get_terminal_size().columns
    print("\n" + "="*size)
    print(" "*((size-30)//2), "TWIN NETWORK STATUS")
    print("="*size)

    # 1. Switches
    print(f"\n--- TOPOLOGY: {len(switches_data)} Switches, {len(links_data)} Links, {len(hosts_data)} Hosts ---")
    
    # 2. Traffic (Chiamata alla nuova funzione)
    pretty_print_traffic(switches_data)
        
    print("\n" + "="*size)

def main():
    print(f"Starting Twin Checker (Polling every {POLL_INTERVAL}s)...")
    
    while True:
        try:
            # Fetch base topology
            switches = fetch_api_data('/v1.0/topology/switches')
            links = fetch_api_data('/v1.0/topology/links')
            hosts = fetch_api_data('/v1.0/topology/hosts')
            
            if switches is not None and links is not None and hosts is not None:
                # Pulisce lo schermo per effetto "dashboard"
                print("\033[H\033[J", end="") 
                pretty_print_topology(switches, links, hosts)
            else:
                print(f"Connection failed/incomplete. Retrying...")

            time.sleep(POLL_INTERVAL)
            
        except KeyboardInterrupt:
            print("\nExiting.")
            break
        except Exception as e:
            print(f"Error: {e}")
            time.sleep(POLL_INTERVAL)

if __name__ == "__main__":
    main()
