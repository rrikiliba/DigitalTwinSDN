import requests
import shutil
import time

RYU_API_HOST = "127.0.0.1"
RYU_API_PORT = 8080
RYU_API_BASE_URL = f"http://{RYU_API_HOST}:{RYU_API_PORT}"
RETRY_DELAY = 5
POLL_INTERVAL = 2

def fetch_api_data(endpoint: str):
    """
    Fetches data from a specific Ryu REST API endpoint.
    """
    url = f"{RYU_API_BASE_URL}{endpoint}"
    # print(f"\n-> Polling {url}...") # Commentato per pulire l'output a video

    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
        return data
    except requests.exceptions.ConnectionError:
        print(f"   [ERROR] Failed to connect to Ryu at {RYU_API_BASE_URL}.")
        return None
    except requests.exceptions.RequestException as e:
        print(f"   [ERROR] API request error: {e}")
        return None

def filter_stale_hosts(hosts_data, switches_data):
    """
    FILTRO HOST FANTASMA:
    Rimuove dalla lista degli host quelli che sono collegati a switch
    non più presenti nella lista switches_data.
    """
    if not switches_data:
        # Se non ci sono switch, non possono esserci host validi
        return []
    
    if not hosts_data:
        return []
    
    # Creiamo un set con tutti i DPID degli switch attualmente attivi per ricerca veloce
    active_switch_dpids = set(sw.get('dpid') for sw in switches_data)
    
    valid_hosts = []
    for host in hosts_data:
        # Recuperiamo i dati della porta a cui l'host dice di essere collegato
        port_info = host.get('port', {})
        host_dpid = port_info.get('dpid')
        
        # Se il DPID dello switch dell'host è nella lista degli switch attivi, l'host è valido
        if host_dpid in active_switch_dpids:
            valid_hosts.append(host)
            
    return valid_hosts

def pretty_print_topology(switches_data, links_data, hosts_data):
    """
    Stampa la topologia filtrata e pulita.
    """
    size = shutil.get_terminal_size().columns
    padding = (size - 37) // 2
    print("\n" + "="*size)
    print(" "*padding, "R Y U   T O P O L O G Y   R E P O R T")
    print("="*size)

    
    print(f"\n--- SWITCHES ({len(switches_data)}) ---")
    if not switches_data:
        print("No switches found or controller is not running.")
    for sw in switches_data:
        dpid = sw.get('dpid', 'N/A')
    
        dpid_str = str(dpid).zfill(16)
        ports = sw.get('ports', [])
        port_details = [f"Port {p.get('port_no')}" for p in ports]
        print(f"  [DPID: {dpid_str}]")
    

    
    print(f"\n--- LINKS ({len(links_data)}) ---")
    if not links_data:
        print("No links found.")
    for link in links_data:
        src = link.get('src', {})
        dst = link.get('dst', {})
        src_dpid = str(src.get('dpid', 'N/A')).zfill(16)
        src_port = src.get('port_no', 'N/A')
        dst_dpid = str(dst.get('dpid', 'N/A')).zfill(16)
        dst_port = dst.get('port_no', 'N/A')
        print(f"  {src_dpid}:{src_port} --> {dst_dpid}:{dst_port}")

    
    print(f"\n--- HOSTS ({len(hosts_data)}) ---")
    if not hosts_data:
        print("No hosts found.")
    for host in hosts_data:
        mac = host.get('mac', 'N/A')
        ipv4 = host.get('ipv4', ['N/A'])
        port = host.get('port', {})
        dpid = str(port.get('dpid', 'N/A')).zfill(16)
        port_no = port.get('port_no', 'N/A')
        
        print(f"  [MAC: {mac}] | [IP: {ipv4}] connected to switch {dpid} on port {port_no}")

    print("\n" + "="*size)

def main():
    print(f"Starting continuous polling of Ryu topology every {POLL_INTERVAL} seconds...")

    while True:
        
        switches = fetch_api_data('/v1.0/topology/switches')
        links = fetch_api_data('/v1.0/topology/links')
        hosts = fetch_api_data('/v1.0/topology/hosts')

        
        if switches is not None:
        
            links = links or []
            hosts = hosts or []

          
          
            clean_hosts = filter_stale_hosts(hosts, switches)
            
          
            pretty_print_topology(switches, links, clean_hosts)
        else:
            print(f"Connection failed or Controller offline. Retrying in {POLL_INTERVAL}s...")

        try:
            time.sleep(POLL_INTERVAL)
        except KeyboardInterrupt:
            print("\nPolling stopped by user.")
            break

if __name__ == "__main__":
    main()
