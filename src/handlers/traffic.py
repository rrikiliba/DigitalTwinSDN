import time, asyncio, requests

STATS_URL = "http://localhost:6060/stats/flow"
STATS_INTERVAL = 0.5

OVERHEAD = 28
MAX_PKT = 1500
MIN_PKT = 64

async def traffic_reproduce(self, batch):
    """
    Riproduce il traffico nel Digital Twin usando hping3 via UDP.
    Sottrae l'overhead degli header (L3+L4) per una precisione al singolo byte.
    """
    for item in batch:
        src_host_name = item['src']
        dst_ip = item['dst']
        delta_bytes = int(item['bytes'])
        delta_packets = int(item['packets'])

        #calculating avg packet size
        if delta_packets <= 0 or delta_bytes <= 0:
            continue

        base_pkt = delta_bytes // delta_packets
        normal_packets = max(0, delta_packets - 1)

        pkt_size = int(max(MIN_PKT, min(MAX_PKT, base_pkt)))

        generated = pkt_size * normal_packets
        remaining = delta_bytes - generated

        if remaining <= 0 and normal_packets > 0:
            normal_packets -= 1
            remaining = delta_bytes - (pkt_size * normal_packets)

        remaining = int(max(MIN_PKT, min(MAX_PKT, remaining)))

        payload_size = max(0, pkt_size - OVERHEAD)
        last_pkt_size = max(0, remaining - OVERHEAD)

        #calculating time distribution of packets
        pps = delta_packets/STATS_INTERVAL
        if pps <= 0:
           continue

        interval_us = int(1_000_000/pps)
        #avoid too small intervals
        interval_us = max (interval_us, 50) 

        # Recupera il nodo Mininet
        node = self.get(src_host_name)
        if not node:
            continue

        # Packet reproduction
        node.cmd(
            f"hping3 -2 -c {normal_packets} "
            f"-d {payload_size} "
            f"-i u{interval_us} "
            f"{dst_ip} &"
        )

        #last packet to avoid byte discrepancies 
        node.cmd(
            f"hping3 -2 -c 1 "
            f"-d {last_pkt_size} "
            f"-i u{interval_us} "
            f"{dst_ip} &"
        )

async def traffic_monitor(self):
    self.log.info("[+] Traffic Monitor Task Started")
    # Inizializza il dizionario se non esiste

    while True:
        await asyncio.sleep(STATS_INTERVAL)
        data_to_reproduce = []
        
        try:
            # Cicla sugli switch conosciuti
            for dpid in list(self.dpid_to_name.keys()):
                dpid_int = int(dpid, 16)
                response = requests.get(f"{STATS_URL}/{dpid_int}", timeout=1)
                
                if response.status_code == 200:
                    flow_stats = response.json().get(str(dpid_int), [])
                    
                    for flow in flow_stats:
                        match = flow.get('match', {})
                        if 'ipv4_src' in match and 'ipv4_dst' in match:
                            src_ip = match['ipv4_src']
                            dst_ip = match['ipv4_dst']
                            byte_count = flow.get('byte_count', 0)
                            packet_count = flow.get('packet_count', 0)

                            flow_key = f"{src_ip}->{dst_ip}"

                            # --- DEDUPLICAZIONE ---
                            # Riproduce il traffico solo se l'host sorgente è collegato a QUESTO switch
                            src_host_node = None
                            for host in self.hosts:
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
                                    "src": src_host_node,
                                    "dst": dst_ip,
                                    "bytes": delta_bytes,
                                    "packets": delta_packets
                                })

                            self.previous_stats[flow_key] = (
                                byte_count,
                                packet_count
                            )

            if data_to_reproduce:
                await traffic_reproduce(self, data_to_reproduce)

        except Exception as e:
            self.log.error(f"[!] Error in traffic_monitor: {e}")

def register_functions(obj):
    obj.tasks.append(traffic_monitor)
