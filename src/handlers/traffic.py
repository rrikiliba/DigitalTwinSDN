import time, asyncio

STATS_URL = "http://localhost:6060/stats/flow"
STATS_INTERVAL = 1


async def traffic_reproduce(self, batch):
    for item in batch:
        src_host = item['src']
        dst_ip = item['dst']
        total_size = int(item['size'])

        # Maximum packet size allowed by ping
        MTU = 65507

        # Calculate how many full packets and the leftover
        full_pings = total_size // MTU
        remainder = total_size % MTU

        node = self.get(src_host)

        if full_pings > 0:
            self.log.info(f"[>] Reproducing traffic: {src_host.name} -> {dst_ip} [{full_pings} x {MTU}]")
            node.cmd(f"ping -c {full_pings} -s {MTU} {dst_ip} &")
        
        if remainder > 0:
            self.log.info(f"[>] Reproducing traffic: {src_host.name} -> {dst_ip} [1 x {remainder}]")
            node.cmd(f"ping -c 1 -s {remainder} {dst_ip} &")

async def traffic_monitor(self):

    self.log.info("[+] Traffic Monitor Task Started")

    while True:
        await asyncio.sleep(STATS_INTERVAL)
        current_time = time.time()
        data_to_reproduce = []
        
        try:
            # Get dpid of the active switches
            switches = self.dpid_to_name.keys()
            
            for dpid in switches:
                # Ask switches for the flow
                # Ryu uses integer dpid for the stats
                dpid_int = int(dpid, 16)
                response = requests.get(f"{STATS_URL}/{dpid_int}", timeout=1)
                
                if response.status_code == 200:
                    flow_stats = response.json().get(str(dpid_int), [])
                    
                    for flow in flow_stats:
                        # Filter flows with ip_src and ip_dst
                        match = flow.get('match', {})
                        if 'ipv4_src' in match and 'ipv4_dst' in match:
                            
                            # Search source node with the ip
                            src_ip = match['ipv4_src']
                            dst_ip = match['ipv4_dst']
                            byte_count = flow.get('byte_count', 0)
                            
                            #Create flow_key for dictionary previous_byte_monitor
                            flow_key = f"{src_ip}->{dst_ip}"

                            previous_bytes = self.previous_byte_count_monitor.get(flow_key, 0)
                            delta_bytes = byte_count - previous_bytes
                            # Logic to decide if traffic must be reproduced
                            # so if byte count grew from last time

                            if delta_bytes > 0:
                                src_host_node = None
                                for host in self.hosts:
                                    if host.IP() == src_ip:
                                    src_host_node = host
                                    break
                                #If a source node is found, I append the flows to reproduce
                                if src_host_node:
                                    data_to_reproduce.append({
                                        "src": src_host_node,
                                        "dst": dst_ip,
                                        "size": delta_bytes
                                    })

                            self.previous_byte_count_monitor[flow_key] = byte_count

        # Send datas to traffic reproduce
        if data_to_reproduce:
            await traffic_reproduce(self, data_to_reproduce)

        except Exception as e:
            self.log.error(f"[!] Error in traffic_monitor: {e}")

        if len(data) > 0:
            await traffic_reproduce(self, data)

        self.last_update_time = current_time

def register_functions(obj):
    obj.tasks = [
        *obj.tasks,
        traffic_monitor
    ]
	
