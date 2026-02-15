import time, asyncio, requests, aiohttp
import subprocess, traceback

STATS_URL = "http://localhost:6060/stats/flow"
STATS_INTERVAL = 2

OVERHEAD = 28
MAX_PKT = 1500
MIN_PKT = 64

async def traffic_reproduce(self, batch):
    """
    Riproduce il traffico nel Digital Twin usando hping3 via UDP.
    Sottrae l'overhead degli header (L3+L4) per una precisione al singolo byte.
    """

    per_node_flows = {}

    print (f"Batch: {batch}")
    
    for item in batch:

        src_host_name = item['src']
        dst_ip = item['dst']
        delta_bytes = int(item['bytes'])
        delta_packets = int(item['packets'])

        if src_host_name not in per_node_flows:
            per_node_flows[src] = []
        per_node_flows[src].append(item)

        #calculating avg packet size
        if delta_packets <= 0 or delta_bytes <= 0:
            continue

        #calculating time distribution of bytes
        bps = delta_bytes/STATS_INTERVAL
        mbps = (bps * 8) / 1_000_000

        MAX_MBPS = 50
        mbps = min(mbps, MAX_MBPS)

        interval_reproduce = delta_bytes / (mbps * (1_000_000 / 8)) 

        if bps <= 0:
           continue

        # Recupera il nodo Mininet
        node = self.get(src_host_name)
        if not node:
            continue

        node.sendCmd('pkill -9 -f "iperf -c"')

        duration = STATS_INTERVAL - 0.2
        iperf_cmd = f"iperf -c {dst_ip} -u -b {mbps:.2f}M -t {duration:.1f} > /dev/null 2>&1 &"

        print("DEBUG: Esecuzione iperf su", src_host_name)
        node.cmd(iperf_cmd)

async def traffic_monitor(self):
    print("[+] Traffic Monitor Task Started")
    # Inizializza il dizionario se non esiste

    async with aiohttp.ClientSession() as session:
        while True:
            await asyncio.sleep(STATS_INTERVAL)
            data_to_reproduce = []

            if not self.dpid_to_name:
                continue
        
            # Cicla sugli switch conosciuti
            for dpid in list(self.dpid_to_name.keys()):
                dpid_int = int(dpid, 16)
                url = f"{STATS_URL}/{dpid_int}"
                
                try:
                    async with session.get(url, timeout=1.5) as response:
                        if response.status == 200:
                            data = await response.json()

                            flow_stats = data.get(str(dpid_int), [])
                    
                            for flow in flow_stats:
                                match = flow.get('match', {})

                                if not match:
                                    continue

                                if 'dl_src' in match and 'nw_dst' in match and 'nw_src' in match:
                                    src_mac = match ['dl_src']
                                    src_ip = match['nw_src']
                                    dst_ip = match['nw_dst']
                                    byte_count = flow.get('byte_count', 0)
                                    packet_count = flow.get('packet_count', 0)

                                    flow_key = f"{dpid}:{src_ip}->{dst_ip}"

                                    # --- DEDUPLICAZIONE ---
                                    # Riproduce il traffico solo se l'host sorgente è collegato a QUESTO switch
                                    src_host_node = None

                                    for host in self.hosts:

                                        if src_mac and src_mac == host.MAC():
                                            src_host_node = host
                                            if src_ip and (not host.IP() or host.IP() == '0.0.0.0'):
                                                host.setIP(src_ip)

                                        if host.IP() == src_ip:
                                            # Verifica se il link dell'host porta a questo switch
                                            for link in self.links:
                                                if (link.intf1.node == host and link.intf2.node.dpid == dpid) or \
                                                    (link.intf2.node == host and link.intf1.node.dpid == dpid):
                                                    src_host_node = host
                                                    break
                                

                                    if not src_host_node:
                                        continue

                                    prev_bytes, prev_packets = self.previous_stats.get(flow_key, (0,0))
                                    delta_bytes = byte_count - prev_bytes
                                    delta_packets = packet_count - prev_packets

                                    if delta_bytes > 0 and delta_packets > 0:
                                        data_to_reproduce.append({
                                            "src": src_host_node.name,
                                            "dst": dst_ip,
                                            "bytes": delta_bytes,
                                            "packets": delta_packets
                                        })

                                    self.previous_stats[flow_key] = (
                                        byte_count,
                                        packet_count
                                    )

                except Exception as e:
                    print(f"[ERRORE CRITICO MONITOR]: {e}")
                    traceback.print_exc()
                    pass

            if data_to_reproduce:
                        asyncio.create_task(traffic_reproduce(self, data_to_reproduce))

def register_functions(obj):
    obj.tasks.append(traffic_monitor)
