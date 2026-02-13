import logging, time
from mininet.net import Mininet
from mininet.node import RemoteController, OVSSwitch
from mininet.clean import cleanup
from handlers.topology import register_functions as register_topology_functions
from handlers.traffic import register_functions as register_traffic_functions

class DigitalTwin(Mininet):
    """
    A Mininet extension that builds and manages a network topology 
    dynamically based on external events (from a ryu SDN controller).
    """
    def __init__(self, name: str = 'TWN', **kwargs):
        # Configure logging for better output
        logging.basicConfig(level=logging.INFO, format='[%(asctime)s] [%(levelname)s] %(message)s')
        self.log = logging.getLogger(name)
        
        # Data structures to map network identifiers (DPID, MAC) to Mininet node names
        self.dpid_to_name = {}
        self.mac_to_name = {}
        # Stores MAC addresses associated with specific switch ports for filtering/linking
        # Key: (dpid, port_no) -> Value: mac
        self.dpid_port_to_mac = {}
        
        # Counters for sequential node naming
        self.switch_count = 0
        self.host_count = 0
        
        # Latest update timestamp
        self.last_update_time = time.time()

        # List of asyncio tasks to run simultaneusly (for network status polling)
        self.tasks = []

        # List of event handlers the system can provide (for async topology updates)
        self.events = {}

        #List of previous traffic in traffic monitoring and reproducing
        self.previous_stats = {}

        super().__init__(**kwargs)
        
    async def callback(self, message):
        # Callback for the RPC server that routes messages to event handlers defined in the object
        method = message.get("method")
        params = message.get("params", [])

        if not method or not params:
            self.log.error("[!] Invalid message format (missing method or params)")
            return

        data = params[0]

        event = self.events.get(method, None)
        if event is not None:    
            event(self, data)
        else:
            self.log.info(f"[-] Message method '{method}' was ignored.")



    def start(self):
        """Starts the Mininet network and its controllers."""
        self.log.info("[+] Starting Mininet...")
        return super().start()

async def main(net_obj, rpc_obj):
    main_tasks = []

    # 1. Registra il server RPC
    main_tasks.append(asyncio.create_task(rpc_obj.serve_forever()))

    # 2. Registra i monitor (es. traffic_monitor)
    for task_func in net_obj.tasks:
        # Passiamo l'oggetto 'net_obj' alla funzione
        main_tasks.append(asyncio.create_task(task_func(net_obj)))

    print(f"DEBUG: Avvio di {len(main_tasks)} task in parallelo...")
    
    # Questo avvia tutto e non si ferma finché non chiudi il programma
    await asyncio.gather(*main_tasks)

if __name__ == "__main__":
    from utils.rpc_server import WebsocketRPCServer
    import asyncio
    
    # 1. Initialize Mininet with a Remote Controller and OVS Switches
    net = DigitalTwin(controller=RemoteController, switch=OVSSwitch)

    register_topology_functions(net)
    register_traffic_functions(net)

    net.addController('twn-c0') # Add a controller instance

    # 2. Start Mininet (this brings up the controller and switches, if any are pre-configured)
    net.start()

    # 3. Setup the RPC server to listen for topology updates
    rpc = WebsocketRPCServer('ws://127.0.0.1:6060/v1.0/topology/ws', callback=net.callback)
    rpc.log.info("[+] Starting RPC Server loop. Waiting for events...")

    # 4. Start the event loop to 
    #       - serve RPC requests (topology changes)
    #       - start all tasks (traffic polling)
    try:

        #main_tasks = [task(net) for task in net.tasks]
        #main_tasks.append(rpc.serve_forever()
        #loop.run_until_complete(asyncio.gather(*main_tasks))
        
        asyncio.run(main(net, rpc))
    except KeyboardInterrupt:
        rpc.log.info("[-] Client stopped by user.")
    finally:
        # 5. Cleanup Mininet resources
        net.stop()
        cleanup()
