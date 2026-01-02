import requests
import shutil
import time

RYU_API_HOST = "127.0.0.1"
RYU_API_PORT = 8080
RYU_API_BASE_URL = f"http://{RYU_API_HOST}:{RYU_API_PORT}"
RETRY_DELAY = 5 
POLL_INTERVAL = 2

# TODO: report network data as well

def fetch_api_data(endpoint: str):
    """
    Fetches data from a specific Ryu REST API endpoint.

    Args:
        endpoint: The path to the API endpoint (e.g., '/v1.0/topology/switches').

    Returns:
        A list of data objects (switches, links, or hosts) on success, 
        or None on a connection error.
    """
    url = f"{RYU_API_BASE_URL}{endpoint}"
    
    print(f"\n-> Polling {url}...")
    
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        
        # Ryu's API returns a list of dictionaries/objects
        data = response.json()
        print(f"   Success. Found {len(data)} items.")
        return data
        
    except requests.exceptions.ConnectionError:
        # Return None on connection failure
        print(f"   [ERROR] Failed to connect to Ryu at {RYU_API_BASE_URL}. Ensure the controller is running and the TopologyAPI is loaded.")
        return None
    except requests.exceptions.RequestException as e:
        # Return None on other request errors
        print(f"   [ERROR] An API request error occurred: {e}")
        return None


def pretty_print_topology(switches_data: list, links_data: list, hosts_data: list):
    """
    Prints the fetched topology data in a structured, readable format.
    """
    size = shutil.get_terminal_size().columns
    padding = (size - 37) // 2
    print("\n" + "="*size)
    print(" "*padding, "R Y U   T O P O L O G Y   R E P O R T")
    print("="*size)

    # 1. Switches
    print(f"\n--- SWITCHES ({len(switches_data)}) ---")
    if not switches_data:
        print("No switches found or controller is not running.")
    for sw in switches_data:
        dpid = sw.get('dpid', 'N/A')
        dpid_str = str(dpid).zfill(16)
        ports = sw.get('ports', [])
        
        port_details = [f"Port {p.get('port_no')}" for p in ports]
        
        print(f"  [DPID: {dpid_str}]")
        print(f"    - Ports ({len(ports)} total): {', '.join(port_details)}")


    # 2. Links
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
        
        link_str = (
            f"  {src_dpid}:{src_port} "
            f"--> {dst_dpid}:{dst_port}"
        )
        print(link_str)

    # 3. Hosts
    print(f"\n--- HOSTS ({len(hosts_data)}) ---")
    if not hosts_data:
        print("No hosts found.")
    for host in hosts_data:
        mac = host.get('mac', 'N/A')
        ipv4 = host.get('ipv4', ['N/A'])
        port = host.get('port', {})
        dpid = str(port.get('dpid', 'N/A')).zfill(16)
        port_no = port.get('port_no', 'N/A')
        
        host_str = (
            f"  [MAC: {mac}] | [IP: {ipv4}] "
            f"connected to switch {dpid} on port {port_no}"
        )
        print(host_str)
        
    print("\n" + "="*size)


def main():
    """
    Main function to run the continuous topology poll and report.
    """
    print(f"Starting continuous polling of Ryu topology every {POLL_INTERVAL} seconds. Press Ctrl+C to stop.")
    
    while True:
        # Fetch data for all topology components
        switches = fetch_api_data('/v1.0/topology/switches')
        links = fetch_api_data('/v1.0/topology/links')
        hosts = fetch_api_data('/v1.0/topology/hosts')
        
        # Only print the topology report if all fetches succeeded (i.e., returned lists, not None)
        if switches is not None and links is not None and hosts is not None:
            pretty_print_topology(switches, links, hosts)
        else:
            # If any fetch failed (returned None), indicate a pause before retry.
            print(f"Connection failed. Retrying in {POLL_INTERVAL} seconds...")

        try:
            time.sleep(POLL_INTERVAL)
        except KeyboardInterrupt:
            print("\nPolling stopped by user (Ctrl+C). Exiting.")
            break

if __name__ == "__main__":
    main()
