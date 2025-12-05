import logging
from mininet.net import Mininet
from mininet.node import RemoteController, OVSSwitch
from mininet.clean import cleanup

class DigitalTwin(Mininet):
    """
    A Mininet extension that builds and manages a network topology 
    dynamically based on external events (from a ryu SDN controller).
    """
    def __init__(self, name: str = 'TWN', **kwargs):
        # Configure logging for better output
        logging.basicConfig(level=logging.INFO, format='[%(asctime)s] [%(levelname)s] [%(logger_name)s] %(message)s')
        self.log = logging.LoggerAdapter(logging.getLogger(__name__), {'logger_name': name})
        
        # Data structures to map network identifiers (DPID, MAC) to Mininet node names
        self.dpid_to_name = {}
        self.mac_to_name = {}
        # Stores MAC addresses associated with specific switch ports for filtering/linking
        # Key: (dpid, port_no) -> Value: mac
        self.dpid_port_to_mac = {}
        
        # Counters for sequential node naming
        self.switch_count = 0
        self.host_count = 0
        
        super().__init__(**kwargs)
        
    def start(self):
        """Starts the Mininet network and its controllers."""
        self.log.info("[+] Starting Mininet...")
        return super().start()

    def event_switch_enter(self, switch_data):
        """Handles a new switch entering the network (or an update)."""
        dpid = switch_data.get("dpid")
        
        # Check if we already have a short name for this DPID
        if dpid in self.dpid_to_name:
            switch_name = self.dpid_to_name[dpid]
            self.log.info(f"[_] Switch {switch_name} (DPID: {dpid}) is already known.")
        else:
            # Assign a new sequential short name (twn-s1, twn-s2, ...)
            self.switch_count += 1
            switch_name = f"twn-s{self.switch_count}"
            
            self.log.info(f"[+] New switch detected: {switch_name}")
            
            # Add the switch to the Mininet topology
            s = self.addSwitch(switch_name, dpid=dpid)
            self.dpid_to_name[dpid] = switch_name

            # DYNAMIC FIX: If the network is already running (built), we must 
            # start this specific switch so it connects to the controller.
            if self.built:
                switch_node = self.get(switch_name)
                # Connect to all configured controllers
                switch_node.start(self.controllers)
        
        # Store Port MACs for later link creation and HOST FILTERING
        ports = switch_data.get('ports', [])
        port_names = []
        for p in ports:
            port_names.append(p.get('name'))
            p_no = p.get('port_no')
            p_mac = p.get('hw_addr')
            if p_no and p_mac:
                # Store the MAC using (dpid, port_no) as the key
                self.dpid_port_to_mac[(dpid, p_no)] = p_mac

        self.log.info(f"  Ports reported: {', '.join(port_names)}")


    def event_host_add(self, host_data):
        """Handles a new host being detected and linked to a switch."""
        mac = host_data.get("mac")
        ipv4 = host_data.get("ipv4", [])
        port_info = host_data.get("port", {})
        dpid_hex = port_info.get("dpid")
        port_no = port_info.get("port_no")

        # --- FILTER GHOST HOSTS ---
        # If the MAC address detected as a "Host" is actually one of our 
        # Switch Port MACs, it is likely an LLDP packet being misidentified.
        if mac in self.dpid_port_to_mac.values():
            self.log.warning(f"[_] Ignoring Host Add for MAC {mac} - it belongs to a known Switch Port (Ghost Host detected).")
            return
        
        # Check if we already have a short name for this MAC
        if mac in self.mac_to_name:
            host_name = self.mac_to_name[mac]
            self.log.info(f"[_] Host {host_name} (MAC: {mac}) is already registered.")
        else:
            # Assign a new sequential short name (twn-h1, twn-h2, ...)
            self.host_count += 1
            host_name = f"twn-h{self.host_count}"

            self.log.info(f"[+] New host detected: {host_name}")
            host_params = {'mac': mac}
            if ipv4:
                # Use the first IPv4 address if available
                host_params['ip'] = ipv4[0] if ipv4[0] else None
            self.addHost(host_name, **host_params)
            self.mac_to_name[mac] = host_name

        # Find the switch name associated with the DPID
        switch_name = self.dpid_to_name.get(dpid_hex)
        
        if not switch_name:
            self.log.warning(f"[!] Mininet node name for DPID {dpid_hex} is unknown. Cannot create link.")
            return

        host_node = self.get(host_name)
        switch_node = self.get(switch_name)
        
        # Check if a link already exists between the host and switch
        links = self.linksBetween(host_node, switch_node)
        
        if len(links) > 0:
            self.log.info(f"[_] Link between {host_name} and {switch_name} appears to exist.")
        else:
            self.log.info(f"[+] Adding link: {host_name} <-> {switch_name}")
            
            # Determine MAC for the switch-side interface
            link_params = {}

            # Explicitly set Host Interface MAC (addr1)
            link_params['addr1'] = mac

            # Retrieve the MAC of the switch port to use for the link interface on the switch side
            switch_mac = self.dpid_port_to_mac.get((dpid_hex, port_no))
            if switch_mac:
                # addr2 corresponds to the second node (switch_node)
                link_params['addr2'] = switch_mac

            # Add link (creates veth pair)
            link = self.addLink(host_node, switch_node, **link_params)
            
            # DYNAMIC FIX: If network is running, we need to attach the new interface 
            # to the OVS switch so packets can flow.
            if self.built:
                # Find which interface belongs to the switch and attach it
                if link.intf1.node == switch_node:
                    switch_node.attach(link.intf1)
                elif link.intf2.node == switch_node:
                    switch_node.attach(link.intf2)
                
                # Ensure the host interface is up
                host_iface_name = link.intf1.name if link.intf1.node == host_node else link.intf2.name
                host_node.cmd('ifconfig', host_iface_name, 'up')

    def event_link_add(self, link_data):
        """Handles a switch-to-switch link being discovered."""
        src_dpid = link_data.get("src", {}).get("dpid")
        src_port = link_data.get("src", {}).get("port_no")
        dst_dpid = link_data.get("dst", {}).get("dpid")
        dst_port = link_data.get("dst", {}).get("port_no")

        if not src_dpid or not dst_dpid:
            self.log.error("[!] Link add message missing source or destination DPID.")
            return

        src_name = self.dpid_to_name.get(src_dpid)
        dst_name = self.dpid_to_name.get(dst_dpid)

        if not src_name or not dst_name:
            self.log.warning(
                f"[!] Cannot add link: One or both switches are unknown (Src DPID: {src_dpid}, Dst DPID: {dst_dpid}). "
                f"[!] Waiting for switch_enter events. Names: {src_name} <-> {dst_name}"
            )
            return

        src_node = self.get(src_name)
        dst_node = self.get(dst_name)

        # Check if the link already exists
        if self.linksBetween(src_node, dst_node):
            self.log.info(f"[_] Link between {src_name} and {dst_name} already exists.")
            return

        self.log.info(f"[+] Adding switch to switch link: {src_name} <-> {dst_name}")
        
        try:
            # Determine MACs for both interfaces
            link_params = {}
            # Retrieve the MACs for the interfaces from stored port data
            src_mac = self.dpid_port_to_mac.get((src_dpid, src_port))
            dst_mac = self.dpid_port_to_mac.get((dst_dpid, dst_port))
            
            if src_mac: link_params['addr1'] = src_mac
            if dst_mac: link_params['addr2'] = dst_mac

            # addLink handles creating the veth pair in the kernel
            link = self.addLink(src_node, dst_node, **link_params)

            # DYNAMIC FIX: If network is running, we must manually attach 
            # the new interfaces to their respective OVS bridges.
            if self.built:
                if isinstance(src_node, OVSSwitch):
                    src_node.attach(link.intf1)
                if isinstance(dst_node, OVSSwitch):
                    dst_node.attach(link.intf2)

        except Exception as e:
            self.log.warning(f"[!] Error creating link between {src_name} and {dst_name}: {e}")

    def event_link_delete(self, link_data):
        src_dpid = link_data.get("src", {}).get("dpid")
        dst_dpid = link_data.get("dst", {}).get("dpid")

        src_name = self.dpid_to_name.get(src_dpid)
        dst_name = self.dpid_to_name.get(dst_dpid)

        if not src_name or not dst_name:
            self.log.warning(f"[!] Link delete ignored: Unknown switches {src_dpid} <-> {dst_dpid}")
            return

        src_node = self.get(src_name)
        dst_node = self.get(dst_name)

        links = self.linksBetween(src_node, dst_node)
        for link in links:
            self.log.info(f"[-] Removing link: {src_name} <-> {dst_name}")
            if self.built:
                if isinstance(src_node, OVSSwitch): src_node.detach(link.intf1)
                if isinstance(dst_node, OVSSwitch): dst_node.detach(link.intf2)
            self.delLink(link)

    def event_switch_leave(self, switch_data):
        dpid = switch_data.get("dpid")
        name = self.dpid_to_name.get(dpid)

        if not name:
            self.log.warning(f"[!] Switch leave ignored: Unknown DPID {dpid}")
            return

        self.log.info(f"[-] Switch leaving: {name}")
        node = self.get(name)

        # Remove associated links first
        for link in list(self.links):
            if link.intf1.node == node or link.intf2.node == node:
                if self.built:
                    if isinstance(link.intf1.node, OVSSwitch): link.intf1.node.detach(link.intf1)
                    if isinstance(link.intf2.node, OVSSwitch): link.intf2.node.detach(link.intf2)
                self.delLink(link)

        # Stop and remove switch
        node.stop()
        if node in self.switches: self.switches.remove(node)
        if name in self.nameToNode: del self.nameToNode[name]
        del self.dpid_to_name[dpid]

    async def topology_update(self, message):
        """
        Entry point for receiving external topology updates via RPC.
        Parses the message and dispatches it to the correct event handler.
        """
        method = message.get("method")
        params = message.get("params", [])

        if not method or not params:
            self.log.error("[!] Invalid message format (missing method or params)")
            return

        data = params[0]

        # Convert event_switch_enter -> switch_enter to find the handler
        handler_name = f"event_{method.split('_', 1)[1]}" if method.startswith("event_") else method
        handler = getattr(self, handler_name, None)
        
        if handler:
            handler(data)
        else:
            self.log.info(f"[-] Message method '{method}' was ignored.")

if __name__ == "__main__":
    from rpc_server import WebsocketRPCServer
    import asyncio
    
    # 1. Initialize Mininet with a Remote Controller and OVS Switches
    net = DigitalTwin(controller=RemoteController, switch=OVSSwitch)
    net.addController('twn-c0') # Add a controller instance

    # 2. Start Mininet (this brings up the controller and switches, if any are pre-configured)
    net.start()

    # 3. Setup the RPC server to listen for topology updates
    rpc = WebsocketRPCServer('ws://127.0.0.1:6060/v1.0/topology/ws', callback=net.topology_update)

    # 4. Start the event loop to serve RPC requests
    try:
        loop = asyncio.get_event_loop()
        rpc.log.info("[+] Starting RPC Server loop. Waiting for events...")
        loop.run_until_complete(rpc.serve_forever())
    except KeyboardInterrupt:
        rpc.log.info("[-] Client stopped by user.")
    finally:
        # 5. Cleanup Mininet resources
        net.stop()
        cleanup()