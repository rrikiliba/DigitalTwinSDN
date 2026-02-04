import time, asyncio, requests

STATS_URL = "http://localhost:6060/stats/flow"
STATS_INTERVAL = 1

async def traffic_reproduce(self, batch):
    """
    Riproduce il traffico nel Digital Twin usando hping3 via UDP.
    Sottrae l'overhead degli header (L2+L3+L4) per una precisione al singolo byte.
    """
    for item in batch:
        src_host_name = item['src']
        dst_ip = item['dst']
        total_delta_bytes = int(item['size'])

        # --- CONFIGURAZIONE PRECISIONE ---
        # Ethernet (14) + IP (20) + UDP (8) = 42 byte
        OVERHEAD = 42
        # MTU standard Ethernet
        REAL_MTU = 1500 
        # Payload massimo per pacchetto hping3 per arrivare a 1500 sul cavo
        MAX_PAYLOAD = REAL_MTU - OVERHEAD # 1458

        # Recupera il nodo Mininet
        node = self.get(src_host_name)
        if not node:
            continue

        # 1. Calcola quanti pacchetti "pieni" da 1500 byte servono
        full_packets = total_delta_bytes // REAL_MTU
        # 2. Calcola il resto (l'ultimo pacchetto non pieno)
        remainder = total_delta_bytes % REAL_MTU

        # Riproduzione pacchetti pieni (MTU 1500)
        if full_packets > 0:
            self.log.info(f"[>] Twin: {src_host_name} -> {dst_ip} | {full_packets} pkts x 1500B")
            # -2: UDP mode, -d: payload size, -c: count, -i u1: flood mode (1us interval)
            node.cmd(f"hping3 -2 -c {full_packets} -d {MAX_PAYLOAD} -i u1 {dst_ip} &")

        # Riproduzione del resto (Last packet)
        if remainder > 0:
            # Sottraiamo l'overhead dal resto. Se il resto è < 42, il payload sarà 0.
            last_payload = max(0, remainder - OVERHEAD)
            self.log.info(f"[>] Twin: {src_host_name} -> {dst_ip} | Last pkt: {remainder}B (payload {last_payload})")
            node.cmd(f"hping3 -2 -c 1 -d {last_payload} {dst_ip} &")

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

                            previous_bytes = self.previous_byte_count_monitor.get(flow_key, 0)
                            delta_bytes = byte_count - previous_bytes

                            if delta_bytes > 0:
                                data_to_reproduce.append({
                                    "src": src_host_node,
                                    "dst": dst_ip,
                                    "size": delta_bytes
                                })

                            self.previous_byte_count_monitor[flow_key] = byte_count

            if data_to_reproduce:
                await traffic_reproduce(self, data_to_reproduce)

        except Exception as e:
            self.log.error(f"[!] Error in traffic_monitor: {e}")

def register_functions(obj):
    obj.tasks.append(traffic_monitor)
