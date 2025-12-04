import logging
from mininet.net import Mininet
from mininet.node import RemoteController, OVSSwitch
from mininet.clean import cleanup
from mininet.link import Link

logging.basicConfig(level=logging.INFO, format='[%(asctime)s] [%(levelname)s] [TWIN] %(message)s')
logger = logging.getLogger(__name__)

class DigitalTwin(Mininet):
    def __init__(self, **kwargs):
        self.dpid_to_name = {}
        self.mac_to_name = {}
        self.dpid_port_to_mac = {}
        self.switch_count = 0
        self.host_count = 0
        super().__init__(**kwargs)
        

    def event_switch_enter(self, switch_data):
        dpid = switch_data.get("dpid")
        
        # Check if we already have a short name for this DPID
        if dpid in self.dpid_to_name:
            switch_name = self.dpid_to_name[dpid]
            logger.info(f"Switch {switch_name} (DPID: {dpid}) is already known.")
        else:
            # Assign a new sequential short name (s1, s2, ...)
            self.switch_count += 1
            switch_name = f"twin-s{self.switch_count}"
            
            logger.info(f"** NEW SWITCH DETECTED ** -> {switch_name}")
            
            # Add the switch to the topology
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
                self.dpid_port_to_mac[(dpid, p_no)] = p_mac

        logger.info(f"  Ports reported: {', '.join(port_names)}")


    def event_host_add(self, host_data):
        mac = host_data.get("mac")
        ipv4 = host_data.get("ipv4", [])
        port_info = host_data.get("port", {})
        dpid_hex = port_info.get("dpid")
        port_no = port_info.get("port_no")

        # --- FILTER GHOST HOSTS ---
        # If the MAC address detected as a "Host" is actually one of our 
        # Switch Port MACs, it is likely an LLDP packet being misidentified.
        if mac in self.dpid_port_to_mac.values():
            logger.warning(f"Ignoring Host Add for MAC {mac} - it belongs to a known Switch Port (Ghost Host detected).")
            return
        
        # Check if we already have a short name for this MAC
        if mac in self.mac_to_name:
            host_name = self.mac_to_name[mac]
            logger.info(f"Host {host_name} (MAC: {mac}) is already registered.")
        else:
            # Assign a new sequential short name (h1, h2, ...)
            self.host_count += 1
            host_name = f"twin-h{self.host_count}"

            logger.info(f"** NEW HOST DETECTED ** -> {host_name}")
            host_params = {'mac': mac}
            if ipv4:
                host_params['ip'] = ipv4[0] if ipv4[0] else None
            self.addHost(host_name, **host_params)
            self.mac_to_name[mac] = host_name

        switch_name = self.dpid_to_name.get(dpid_hex)
        
        if not switch_name:
            logger.warning(f"Mininet node name for DPID {dpid_hex} is unknown. Cannot create link.")
            return

        host_node = self.get(host_name)
        switch_node = self.get(switch_name)
        
        links = self.linksBetween(host_node, switch_node)
        
        if len(links) > 0:
            logger.info(f"Link between {host_name} and {switch_name} appears to exist.")
        else:
            logger.info(f"** ADDING LINK **: {host_name} <-> {switch_name}")
            
            # Determine MAC for the switch-side interface
            link_params = {}
            switch_mac = self.dpid_port_to_mac.get((dpid_hex, port_no))
            if switch_mac:
                # addr2 corresponds to the second node (switch_node)
                link_params['addr2'] = switch_mac

            # Add link
            link = self.addLink(host_node, switch_node, **link_params)
            
            # DYNAMIC FIX: If network is running, we need to attach the new interface 
            # to the OVS switch so packets can flow.
            if self.built:
                # Find which interface belongs to the switch
                if link.intf1.node == switch_node:
                    switch_node.attach(link.intf1)
                elif link.intf2.node == switch_node:
                    switch_node.attach(link.intf2)
                
                # Ensure the host interface is up
                host_node.cmd('ifconfig', link.intf1.name if link.intf1.node == host_node else link.intf2.name, 'up')

    def event_link_add(self, link_data):
        src_dpid = link_data.get("src", {}).get("dpid")
        src_port = link_data.get("src", {}).get("port_no")
        dst_dpid = link_data.get("dst", {}).get("dpid")
        dst_port = link_data.get("dst", {}).get("port_no")

        if not src_dpid or not dst_dpid:
            logger.error("Link add message missing source or destination DPID.")
            return

        src_name = self.dpid_to_name.get(src_dpid)
        dst_name = self.dpid_to_name.get(dst_dpid)

        if not src_name or not dst_name:
            logger.warning(
                f"Cannot add link: One or both switches are unknown (Src DPID: {src_dpid}, Dst DPID: {dst_dpid}). "
                f"Waiting for switch_enter events. Names: {src_name} <-> {dst_name}"
            )
            return

        src_node = self.get(src_name)
        dst_node = self.get(dst_name)

        if self.linksBetween(src_node, dst_node):
            logger.info(f"Link between {src_name} and {dst_name} already exists.")
            return

        logger.info(f"** ADDING SWITCH-TO-SWITCH LINK **: {src_name} <-> {dst_name}")
        
        try:
            # Determine MACs for both interfaces
            link_params = {}
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
            logger.warning(f"Error creating link between {src_name} and {dst_name}: {e}")


    async def topology_update(self, message):
        method = message.get("method")
        params = message.get("params", [])

        if not method or not params:
            logger.error("Invalid message format (missing method or params)")
            return

        data = params[0]

        handler_name = f"event_{method.split('_', 1)[1]}" if method.startswith("event_") else method
        handler = getattr(self, handler_name, None)
        
        if handler:
            # CRITICAL FIX: Removed net.stop() and net.start()
            # We only execute the handler. The handler is responsible for 
            # live-updating the topology (attaching ports, starting switches).
            handler(data)
        else:
            logger.info(f"Message method '{method}' was ignored.")

if __name__ == "__main__":
    from rpc_server import WebsocketRPCServer
    import asyncio
    
    # Initialize Mininet
    net = DigitalTwin(controller=RemoteController, switch=OVSSwitch)
    net.addController('twin-c0')

    # Start the network ONCE here. 
    # This creates the initial environment. New nodes will be added dynamically.
    logger.info("Starting Mininet core...")
    net.start()

    rpc = WebsocketRPCServer('ws://127.0.0.1:6060/v1.0/topology/ws', callback=net.topology_update)

    try:
        loop = asyncio.get_event_loop()
        loop.run_until_complete(rpc.serve_forever())
    except KeyboardInterrupt:
        rpc.log.info("Client stopped by user.")
        net.stop()
        cleanup()