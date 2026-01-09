def get_connected_host(self, switch_node, port_no):
        """
        Helper: Finds which Host is connected to a specific Switch Port.
        Mininet stores links, we need to iterate to find the matching interface.
        """
        port_no = int(port_no)
        for link in self.links:
            # Check if intf1 is the switch port
            if link.intf1.node == switch_node:
                # OVS ports might be strings or ints, verify conversion
                link_port = self.ports.get(link.intf1, -1) 
                # In Mininet standard, we often have to rely on port mapping logic or checking link names
                # A more robust way in Mininet is checking the node's connections:
                if switch_node.ports[link.intf1] == port_no:
                    if link.intf2.node.name.startswith('twn-h'): # It's a host
                        return link.intf2.node
            
            # Check if intf2 is the switch port
            elif link.intf2.node == switch_node:
                if switch_node.ports[link.intf2] == port_no:
                    if link.intf1.node.name.startswith('twn-h'): # It's a host
                        return link.intf1.node
        return None

    async def monitor_traffic(self):
        """
        Fetches statistics from the Live Controller and triggers the Digital Twin
        to mimic the traffic load.
        """
        # URL of the Ryu controller APIs (Pannello 5)
        STATS_URL = "http://localhost:6060/stats/port"
        
        while True:
            current_time = time.time()
            time_diff = current_time - self.last_update_time

            # Avoid spamming requests too fast (min 1 second interval)
            if time_diff >= 1.0:
                traffic_snapshot = {} # Store traffic data for this cycle

                for dpid in list(self.dpid_to_name.keys()): # Use list() to avoid runtime change errors
                    # Initialize structure if missing
                    if dpid not in self.network_data:
                        self.network_data[dpid] = {"ports": {}}

                    try:
                        # Fetch stats from Live Ryu
                        url = f"{STATS_URL}/{int(dpid, 16)}"
                        response = requests.get(url)
                        
                        if response.status_code == 200:
                            body = response.json()
                            key_str = str(int(dpid, 16))
                            
                            if key_str in body:
                                stats_list = body[key_str]
                                for port in stats_list:
                                    port_no = str(port['port_no'])
                                    if port_no == 'LOCAL': continue # Ignore internal port

                                    rx_now = port['rx_bytes']
                                    tx_now = port['tx_bytes']

                                    # Get previous values to calculate delta
                                    port_data = self.network_data[dpid]["ports"].get(port_no, {})
                                    rx_prev = port_data.get("total_rx", rx_now)
                                    # tx_prev = port_data.get("total_tx", tx_now) # Not used for generation trigger, but good for stats

                                    # Calculate Speed (Bytes per second)
                                    # Note: We focus on RX speed on the Switch, 
                                    # which corresponds to TX speed from the connected Host.
                                    rx_speed = (rx_now - rx_prev) / time_diff
                                    
                                    # Update stored data
                                    self.network_data[dpid]["ports"][port_no] = {
                                        "total_rx": rx_now,
                                        "total_tx": tx_now,
                                        "speed_rx_bps": rx_speed,
                                    }

                                    # Add to snapshot for reproduction
                                    if dpid not in traffic_snapshot: traffic_snapshot[dpid] = {}
                                    traffic_snapshot[dpid][port_no] = rx_speed

                    except Exception as e:
                        self.log.error(f"[!] Error fetching stats for DPID {dpid}: {e}")

                # Trigger traffic reproduction with the fresh snapshot
                if traffic_snapshot:
                    await self.reproduce_traffic(traffic_snapshot)

                self.last_update_time = current_time

            await asyncio.sleep(2) # Wait 2 seconds before next poll

    async def reproduce_traffic(self, traffic_stats):
        """
        Analyzes the traffic snapshot and makes Digital Twin hosts generate traffic.
        Logic: If Switch Port X has high RX, the Host connected to Port X must send data.
        """
        import random
        
        # Threshold: Only reproduce if traffic is significant (> 1KB/s) to avoid noise
        THRESHOLD_BPS = 1000 

        for dpid, ports in traffic_stats.items():
            switch_name = self.dpid_to_name.get(dpid)
            if not switch_name: continue
            
            switch_node = self.get(switch_name)

            for port_no, speed in ports.items():
                if speed > THRESHOLD_BPS:
                    # 1. Identify the Source Host
                    src_host = self.get_connected_host(switch_node, port_no)
                    
                    if src_host:
                        # 2. Identify a Target Host
                        # Get all hosts except the source
                        all_hosts = [h for h in self.hosts if h != src_host]
                        
                        if all_hosts:
                            dst_host = random.choice(all_hosts)
                            
                            # 3. Calculate intensity (Simplification)
                            # If speed is huge, send more packets.
                            # > 100KB/s -> 10 packets, else 1 packet
                            count = 5 if speed > 100000 else 1
                            
                            self.log.info(f"[~] Replaying Traffic: {src_host.name} -> {dst_host.name} ({int(speed)} Bps)")
                            
                            # 4. Execute Ping (Async to not block the loop)
                            # Using cmdAsync allows Mininet to run this in the background
                            # -c: count, -i 0.2: fast interval, -q: quiet
                            src_host.cmdAsync(f"ping -c {count} -i 0.2 -q {dst_host.IP()} &")
