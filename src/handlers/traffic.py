import time, asyncio, aiohttp

# URL and Interval Configuration
STATS_URL = "http://localhost:6060/stats/flow" 
STATS_INTERVAL = 2

async def traffic_reproduce(self, batch):
    """
    Reproduce traffic batch in the twin net via iperf using Kbps.
    """
    if not batch:
        return

    self.log.info(f"[+] Reproducing traffic for {len(batch)} flows")
    
    for item in batch:
        try:
            src_host_name = item['src']
            dst_ip = item['dst']
            delta_bytes = item['bytes']

            # Calculate Kbps: (Bytes * 8 bits) / (Interval in seconds * 1,000)
            kbps = (delta_bytes * 8) / (STATS_INTERVAL * 1_000)

            # Minimum threshold to avoid useless iperf processes (e.g., 0.1 Kbps)
            if kbps < 0.1: 
                continue

            # Limit to avoid CPU overload (50 Mbps = 50,000 Kbps)
            MAX_KBPS = 50000 
            kbps = min(kbps, MAX_KBPS)

            # Retrieve Mininet node object from Digital Twin
            node = self.net.get(src_host_name) if hasattr(self, 'net') else self.get(src_host_name)
            
            if not node:
                self.log.error(f"[!] Node '{src_host_name}' not found in the system!")
                continue

            duration = max(0.5, STATS_INTERVAL - 0.2)
            
            # UDP iperf command using Kbps (-b ...K)
            cmd = [
                'iperf', '-c', dst_ip, 
                '-u', 
                '-b', f'{kbps:.2f}K', 
                '-t', f'{duration:.1f}'
            ]
            
            self.log.info(f"[=] {src_host_name} -> {dst_ip} @ {kbps:.2f} Kbps")
            node.popen(cmd)
            
        except Exception as e:
            self.log.error(f"[!] Critical error in reproduction: {e}")

async def traffic_monitor(self):
    """
    Monitors flow statistics from the Ryu controller and calculates deltas.
    """
    self.log.info(f"[+] Traffic Monitor Started (Units: Kbps)")
    
    if not hasattr(self, 'previous_stats'):
        self.previous_stats = {}

    async with aiohttp.ClientSession() as session:
        while True:
            start_time = time.time()
            data_to_reproduce = []

            dpid_map = getattr(self, 'dpid_to_name', None)
            if not dpid_map:
                await asyncio.sleep(2)
                continue
        
            for dpid_str in list(dpid_map.keys()):
                try:
                    dpid_int = int(dpid_str, 16)
                    url = f"{STATS_URL}/{dpid_int}"
                    
                    async with session.get(url, timeout=1.5) as response:
                        if response.status != 200: continue

                        data = await response.json()
                        flow_stats = data.get(str(dpid_int), [])

                        for flow in flow_stats:
                            match = flow.get('match', {})
                
                            # self.log.info(f'flow: {flow}')

                            # ignore non-ipv4 traffic
                            if match.get('dl_type') != 2048 and match.get('eth_type') != 2048:
                                continue

                            src_ip = match.get('ipv4_src') or match.get('nw_src')
                            dst_ip = match.get('ipv4_dst') or match.get('nw_dst')
                            
                            if not src_ip or not dst_ip:
                                continue

                            # Loop through all hosts known to the Mininet/Digital Twin network to find src host
                            target_host = None
                            for h in self.hosts:
                                # Check if this host's IP matches the source IP found in the OpenFlow flow entry
                                if h.IP() == src_ip:
                                    is_directly_connected = False
                                    
                                    # Examine every physical/virtual interface attached to this host
                                    for intf in h.intfList():
                                        # If the interface is connected to a link...
                                        if intf.link:
                                            # Get the two nodes at the ends of this link (e.g., Host1 and Switch1)
                                            n1, n2 = intf.link.intf1.node, intf.link.intf2.node
                                            
                                            # Identify which node is the 'neighbor' (the one that isn't the host itself)
                                            neighbor = n2 if n1 == h else n1
                                            
                                            # Get the DPID (Data Path ID) of that neighbor switch
                                            neighbor_dpid = getattr(neighbor, 'dpid', None)
                                            
                                            # Check if the neighbor is a switch and if its ID matches 
                                            # the current switch (dpid_int) we are currently polling.
                                            if neighbor_dpid and int(str(neighbor_dpid), 16) == dpid_int:
                                                # If matched, this host is physically plugged into the current switch
                                                is_directly_connected = True
                                                break
                                    
                                    # If the host is directly connected to this switch, we mark it as the 'target_host'
                                    # This host will be the one used to run the 'iperf' command.
                                    if is_directly_connected:
                                        target_host = h
                                        break
                                    
                            # If target_host is still None, it means the traffic is 'transit traffic' 
                            # (passing through this switch from another one). 
                            # We 'continue' (skip) to avoid reproducing the same traffic multiple times.
                            if not target_host:
                                continue

                            byte_count = flow.get('byte_count', 0)
                            flow_key = f"{dpid_int}:{src_ip}->{dst_ip}"

                            if flow_key not in self.previous_stats:
                                self.previous_stats[flow_key] = byte_count
                                continue

                            prev_bytes = self.previous_stats[flow_key]
                            delta_bytes = byte_count - prev_bytes
                            self.previous_stats[flow_key] = byte_count

                            if delta_bytes > 0:
                                data_to_reproduce.append({
                                    "src": target_host.name,
                                    "dst": dst_ip,
                                    "bytes": delta_bytes
                                })

                except Exception as e:
                    self.log.error(f"[!] Error polling DPID {dpid_str}: {e}")

            if data_to_reproduce:
                asyncio.ensure_future(traffic_reproduce(self, data_to_reproduce))
            
            elapsed = time.time() - start_time
            await asyncio.sleep(max(0.1, STATS_INTERVAL - elapsed))

def register_functions(obj):
    obj.tasks.append(traffic_monitor)