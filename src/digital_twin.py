import logging, time, asyncio, traceback
from mininet.net import Mininet
from mininet.node import RemoteController, OVSSwitch
from mininet.clean import cleanup
from handlers.topology import register_functions as register_topology_functions
from handlers.traffic import register_functions as register_traffic_functions

class DigitalTwin(Mininet):
    """
    A Mininet extension that builds and manages a network topology 
    dynamically based on external events (from a Ryu SDN controller).
    """    
    
    def start_iperf_servers(self):
        """Starts iperf servers on all hosts in daemon mode."""
        self.log.info("[+] Starting iperf servers on all hosts...")
        for host in self.hosts:
            # -s: server, -u: UDP, -D: daemon
            host.cmd("iperf -s -u -D")

    def __init__(self, name: str = 'TWN', **kwargs):
        # Logging configuration
        logging.basicConfig(level=logging.INFO, format='[%(asctime)s] [%(levelname)s] [%(logger_name)s] %(message)s')
        self.log = logging.LoggerAdapter(logging.getLogger(__name__), {'logger_name': name})
        
        # Data structures to map identifiers (DPID, MAC) to Mininet node names
        self.dpid_to_name = {}
        self.mac_to_name = {}
        
        # Map (dpid, port_no) -> mac
        self.dpid_port_to_mac = {}
        
        # Counters for sequential names
        self.switch_count = 0
        self.host_count = 0
        
        # Last update timestamp
        self.last_update_time = time.time()

        # Asyncio tasks to execute (e.g., statistics polling)
        self.tasks = []

        # Event handlers for topology updates
        self.events = {}

        # Statistics history for traffic monitoring
        self.previous_stats = {}

        # Initialize Mininet
        super().__init__(**kwargs)
        
        # Reference to self for compatibility with monitors
        self.net = self

    async def callback(self, message):
        """Callback for the RPC server that routes messages to handlers."""
        method = message.get("method")
        params = message.get("params", [])

        if not method or not params:
            self.log.error("[!] Invalid message format (missing method or params)")
            return

        data = params[0]
        event = self.events.get(method, None)
        
        if event is not None:    
            # Note: topology handlers are usually not async, 
            # they are called directly.
            event(self, data)
        else:
            self.log.info("[-] Message method '%s' was ignored.", method)

    def start(self):
        """Starts the Mininet network."""
        self.log.info("[+] Starting Mininet...")
        return super().start()

async def main_loop(net_obj, rpc_obj):
    """Main loop compatible with Python 3.6."""
    main_tasks = []

    # 1. Register the RPC server task
    # In Python 3.6 we use ensure_future instead of create_task
    main_tasks.append(asyncio.ensure_future(rpc_obj.serve_forever()))

    # 2. Register monitors (e.g., traffic_monitor)
    for task_func in net_obj.tasks:
        # Pass the 'net_obj' object to the task function
        main_tasks.append(asyncio.ensure_future(task_func(net_obj)))
    
    # Start all tasks and wait
    await asyncio.gather(*main_tasks)

if __name__ == "__main__":
    from utils.rpc_server import WebsocketRPCServer
    
    # 1. Mininet Initialization
    net = DigitalTwin(controller=RemoteController, switch=OVSSwitch)

    # Register management functions (Topology and Traffic)
    register_topology_functions(net)
    register_traffic_functions(net)

    net.addController('twn-c0')

    # 2. Start Mininet
    net.start()

    # 3. RPC Server Setup
    # Note: Ensure the URL matches the Ryu topology viewer URL
    rpc = WebsocketRPCServer('ws://127.0.0.1:6060/v1.0/topology/ws', callback=net.callback)
    rpc.log.info("[+] Starting RPC Server loop. Waiting for events...")

    # Start iperf listening in the DT
    net.start_iperf_servers()

    # 4. Event Loop Management (Compatible with Python 3.6.9)
    loop = asyncio.get_event_loop()
    
    try:
        # Instead of asyncio.run (3.7+), we use run_until_complete
        loop.run_until_complete(main_loop(net, rpc))

    except KeyboardInterrupt:
        print()
        net.log.info("[-] System stopped by user.")
    except Exception as e:
        net.log.error("[!]: %s" % e)
        traceback.print_exc()
    finally:
        # 5. Cleanup
        net.stop()
        cleanup()
        # Cleanly close the loop
        if loop.is_running():
            loop.close()