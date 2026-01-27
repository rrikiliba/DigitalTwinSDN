import time, asyncio

STATS_URL = "http://localhost:6060/stats/flow"
STATS_INTERVAL = 1


async def traffic_reproduce(self, batch):
    for item in batch:
        src_host = item['src']
        dst_ip = item['dst']
        total_size = item['size']

        # Calculate payload
        # 65507 is the maximum ping size, so if total_size is more
        # divide it into more pings
        payload_num = max(int(total_size) // 65507, 1)
        payload_size = int(total_size) % 65507

        self.log.info(f"[>] Replaying: {src_host.name} -> {dst_ip} [Size: {payload_size}]")
        
        # Execute ping in background
        src_host.cmd(f"ping -c {payload_num} -s {payload_size} {dst_ip} &")

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