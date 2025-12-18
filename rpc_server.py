import asyncio
import websockets
import json
import logging

class WebsocketRPCServer:
    def __init__(self, url: str, name: str = 'RPC', callback=None):
        logging.basicConfig(level=logging.INFO, format='[%(asctime)s] [%(levelname)s] [%(logger_name)s] %(message)s')
        self.log = logging.LoggerAdapter(logging.getLogger(__name__), {'logger_name': name})
        self.url = url
        self.callback = callback
        self.log.info(f"[+] Listener created for URL: {self.url}")

    async def serve_forever(self, reconnect_delay=1):
        if reconnect_delay > 30:
            reconnect_delay = 30

        while True:
            self.log.info("[_] Attempting connection...")

            try:
                
                async with websockets.connect(self.url, ping_interval=None) as websocket:
                    self.log.info("[+] Connection established. Listening for messages...")
                    reconnect_delay = 1

                    async for message in websocket:

                        if isinstance(message, bytes):
                            message = message.decode('utf-8')

                        if message.startswith("b'") and message.endswith("'"):
                            message = message[2:-1]

                        try:
                            self.log.info("[+] Message Received:")

                            parsed_message = json.loads(message)
                            

                            if 'id' in parsed_message:
                                response_id = parsed_message['id']
                                rpc_result = None

                                if self.callback:
                                    self.log.info(f"[+] Calling user callback for ID: {response_id}")
                                    try:
                                        rpc_result = await self.callback(parsed_message)
                                        self.log.info("[^] Callback successful.")
                                    except Exception as cb_e:
                                        error_type = type(cb_e).__name__
                                        self.log.error(f"[!] Error executing user callback. {error_type}: {cb_e}")

                                rpc_response = {
                                    "jsonrpc": "2.0",
                                    "result": rpc_result,
                                    "id": response_id
                                }

                                await websocket.send(json.dumps(rpc_response))
                                self.log.info(f"[^] Sent RPC Acknowledgment (ID: {response_id})")

                            elif 'method' in parsed_message:
                                self.log.info("[+] Received RPC Notification.")

                        except json.JSONDecodeError:
                            self.log.error(f"[!] Failed to decode JSON message (Type: {type(message).__name__}): {message}")
                        except Exception as e:
                            self.log.error(f"[!] Error processing message: {e}")

                    self.log.warning("[!] Connection closed. Attempting reconnect.")

            except Exception as e:
                error_type = type(e).__name__
                self.log.error(f"[!] {error_type} encountered: {e}\nRetrying in {reconnect_delay}s...")
                await asyncio.sleep(reconnect_delay)
                reconnect_delay = min(reconnect_delay * 2, 30)

if __name__ == "__main__":
    DEFAULT_WS_PORT = 6060
    DEFAULT_WS_URL = f"ws://127.0.0.1:{DEFAULT_WS_PORT}/v1.0/topology/ws"

    rpc = WebsocketRPCServer(DEFAULT_WS_URL)

    try:
        loop = asyncio.get_event_loop()
        loop.run_until_complete(rpc.serve_forever())
    except KeyboardInterrupt:
        rpc.log.info("[-] Client stopped by user.")
