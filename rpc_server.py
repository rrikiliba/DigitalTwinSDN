import asyncio
import websockets
import json
import logging

logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] [%(levelname)s] [%(server_name)s] %(message)s'
)

base_logger = logging.getLogger('WebsocketRPC')

class WebsocketRPCServer:
    def __init__(self, url: str, name: str = 'RPC', callback=None):
        self.url = url
        self.name = name
        self.callback = callback
        self.log = logging.LoggerAdapter(base_logger, {'server_name': self.name})
        self.log.info(f"created for URL: {self.url}")

    async def serve_forever(self, reconnect_delay=1):
        if reconnect_delay > 30:
            reconnect_delay = 30
        
        while True:
            self.log.info("Attempting connection...")
            
            try:
                async with websockets.connect(self.url) as websocket:
                    self.log.info("Connection established. Listening for messages...")
                    reconnect_delay = 1

                    async for message in websocket:
                        
                        if isinstance(message, bytes):
                            message = message.decode('utf-8')

                        # Fixes messages wrapped in literal Python byte string notation (b'...')
                        if message.startswith("b'") and message.endswith("'"):
                            message = message[2:-1]
                        
                        try:
                            self.log.info("Message Received:")

                            parsed_message = json.loads(message)
                            print(json.dumps(parsed_message, indent=4))
                            
                            if 'id' in parsed_message:
                                response_id = parsed_message['id']
                                rpc_result = None
                                
                                if self.callback:
                                    self.log.info(f"Calling user callback for ID: {response_id}")
                                    try:
                                        rpc_result = await self.callback(parsed_message)
                                        self.log.info(f"Callback successful. Result type: {type(rpc_result).__name__}")
                                    except Exception as cb_e:
                                        error_type = type(cb_e).__name__
                                        self.log.error(f"Error executing user callback for ID {response_id}. {error_type}: {cb_e}")
                                
                                rpc_response = {
                                    "jsonrpc": "2.0",
                                    "result": rpc_result,
                                    "id": response_id
                                }
                                
                                await websocket.send(json.dumps(rpc_response))
                                self.log.info(f"Sent RPC Acknowledgment (ID: {response_id})")

                            elif 'method' in parsed_message:
                                self.log.info("Received RPC Notification.")

                        except json.JSONDecodeError:
                            self.log.error(f"Failed to decode JSON message (Type: {type(message).__name__}): {message}")
                        except Exception as e:
                            self.log.error(f"Error processing message: {e}")
                    
                    self.log.warning("Connection closed. Attempting reconnect.")

            except Exception as e:
                error_type = type(e).__name__
                self.log.error(f"{error_type} encountered: {e}\nRetrying in {reconnect_delay}s...")
                await asyncio.sleep(reconnect_delay)
                reconnect_delay = min(reconnect_delay * 2, 30)

if __name__ == "__main__":
    DEFAULT_WS_URL = "ws://127.0.0.1:6060/v1.0/topology/ws"

    rpc = WebsocketRPCServer(DEFAULT_WS_URL)
    
    try:
        loop = asyncio.get_event_loop()
        loop.run_until_complete(rpc.serve_forever())
    except KeyboardInterrupt:
        rpc.log.info("Client stopped by user.")