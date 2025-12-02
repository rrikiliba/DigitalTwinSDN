import logging
from mininet.net import Mininet
from mininet.node import Host, OVSSwitch, DefaultController, RemoteController
from mininet.link import Link
from mininet.clean import cleanup

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

class DigitalTwin(Mininet):
    def __init__(self, **kwargs):
        self.dpid_to_name = {}
        self.mac_to_name = {}
        self.switch_count = 0
        self.host_count = 0
        kwargs.setdefault('host', Host)
        kwargs.setdefault('switch', OVSSwitch)
        kwargs.setdefault('controller', DefaultController)
        kwargs.setdefault('link', Link)
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
            switch_name = f"s{self.switch_count}"
            
            logger.info(f"** NEW SWITCH DETECTED ** -> {switch_name}")
            self.addSwitch(switch_name, dpid=dpid)
            self.dpid_to_name[dpid] = switch_name
        
        port_names = [p['name'] for p in switch_data.get('ports', [])]
        logger.info(f"  Ports reported: {', '.join(port_names)}")


    def event_host_add(self, host_data):
        mac = host_data.get("mac")
        ipv4 = host_data.get("ipv4", [])
        port_info = host_data.get("port", {})
        dpid_hex = port_info.get("dpid")
        
        # Check if we already have a short name for this MAC
        if mac in self.mac_to_name:
            host_name = self.mac_to_name[mac]
            logger.info(f"Host {host_name} (MAC: {mac}) is already registered.")
        else:
            # Assign a new sequential short name (h1, h2, ...)
            self.host_count += 1
            host_name = f"h{self.host_count}"

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

        if self.linksBetween(self.get(host_name), self.get(switch_name)):
            logger.info(f"Link between {host_name} and {switch_name} appears to exist.")
        else:
            logger.info(f"** ADDING LINK **: {host_name} <-> {switch_name}")
            self.addLink(self.get(host_name), self.get(switch_name))


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
            handler(data)
        else:
            logger.info(f"Message method '{method}' was ignored.")

if __name__ == "__main__":
    from rpc_server import WebsocketRPCServer
    import asyncio

    ryu = RemoteController('ryu', ip='127.0.0.1', port=6666)
    net = DigitalTwin(controller=ryu, build=False)

    rpc = WebsocketRPCServer('ws://127.0.0.1:8080/v1.0/topology/ws', callback=net.topology_update)

    try:
        loop = asyncio.get_event_loop()
        loop.run_until_complete(rpc.serve_forever())
    except KeyboardInterrupt:
        rpc.log.info("Client stopped by user.")
        net.stop()
        cleanup()