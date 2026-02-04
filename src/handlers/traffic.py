import time, asyncio, requests

STATS_URL = "http://localhost:6060/stats/flow"
STATS_INTERVAL = 1

async def traffic_reproduce(self, batch):
    for item in batch:
        src_host = item['src']
        dst_ip = item['dst']
        total_size = int(item['size'])
        
        # Limita la dimensione per evitare di bloccare il kernel
        MTU = 65507
        size = min(total_size, MTU) 

        # Esegue un singolo ping per segnalare l'attività del flusso
        # Ridotto per evitare di saturare la CPU con troppi processi
        self.log.info(f"[>] Sync traffic: {src_host.name} -> {dst_ip} ({total_size} bytes)")
        src_host.cmd(f"ping -c 1 -s {size} {dst_ip} &")

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
