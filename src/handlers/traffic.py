import time, asyncio, requests

STATS_URL = "http://localhost:6060/stats/flow"
STATS_INTERVAL = 1

async def traffic_reproduce(self, batch):
    # MTU ridotta a 1400 per hping3 (più sicura per UDP)
    MTU = 1400
    # Limite per evitare il crash della VM (Fork Bomb)
    MAX_PACKETS = 5

    for item in batch:
        src_host = item['src']
        dst_ip = item['dst']
        remaining = int(item['size'])

        self.log.info(f"[>] Reproducing flow: {src_host.name} -> {dst_ip} ({remaining} bytes)")

        sent = 0
        # Ciclo di frammentazione richiesto dal tuo compagno
        while remaining > 0 and sent < MAX_PACKETS:
            pkt_size = min(remaining, MTU)
            
            # hping3 --udp: non aspetta risposta e non raddoppia il traffico (no Echo Reply)
            # -c 1: invia un singolo pacchetto
            # -d: dimensione del payload
            src_host.cmd(f"hping3 --udp -c 1 -d {pkt_size} {dst_ip} &")
            
            remaining -= pkt_size
            sent += 1

async def traffic_monitor(self):
    self.log.info("[+] Traffic Monitor Task Started")
    # Inizializza il dizionario se non esiste
    if not hasattr(self, 'previous_byte_count_monitor'):
        self.previous_byte_count_monitor = {}

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
