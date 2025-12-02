import asyncio
import websockets
import json

# Porta 6060 
WS_URL = "ws://127.0.0.1:6060/v1.0/topology/ws"

async def listen_to_ryu():
    print(f"--- CLIENT RPC AVVIATO ---")
    print(f"Target: {WS_URL}")

    async for websocket in websockets.connect(WS_URL, ping_interval=None):
        try:
            print("CONNESSO! Invio richiesta di sottoscrizione...")

            subscribe_request = {
                "jsonrpc": "2.0",
                "method": "subscribe",
                "params": ["switches", "links"],
                "id": 1
            }
            await websocket.send(json.dumps(subscribe_request))
            # -----------------------------------

            print("In ascolto degli eventi...")
            
            async for message in websocket:
                data = json.loads(message)
      
                print(json.dumps(data, indent=4))
                
        except websockets.ConnectionClosed:
            print("Connessione chiusa dal server, riprovo tra 2 sec...")
            await asyncio.sleep(2)
        except Exception as e:
            print(f"Errore critico: {e}")
            await asyncio.sleep(2)

if __name__ == "__main__":
    try:
        asyncio.run(listen_to_ryu())
    except KeyboardInterrupt:
        print("\nClient fermato.")
