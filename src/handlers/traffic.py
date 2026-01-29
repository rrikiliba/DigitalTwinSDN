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
            
    while True:
        await asyncio.sleep(STATS_INTERVAL)
        current_time = time.time()

        # TODO: obtain data in the form
        data = [
            {
                "src": ...,
                "dst": ...,
                "size": ...
            },
            {
                "src": ...,
                "dst": ...,
                "size": ...
            },
            {
                ...
            }
        ]

        if len(data) > 0:
            await traffic_reproduce(self, data)

        self.last_update_time = current_time

def register_functions(obj):
    obj.tasks = [
        *obj.tasks,
        traffic_monitor
    ]
