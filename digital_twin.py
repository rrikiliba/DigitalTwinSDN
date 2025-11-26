import requests
import time
import json
import os

# --- CONFIGURAZIONE ---
RYU_IP = "127.0.0.1"
RYU_PORT = "8080"
BASE_URL = f"http://{RYU_IP}:{RYU_PORT}"
POLLING_INTERVAL = 3  # Secondi tra ogni aggiornamento
OUTPUT_FILE = "digital_twin_data.json"

class DigitalTwin:
    def __init__(self):
        self.network_data = {}      # Contiene gli Switch e le Statistiche
        self.network_links = []     # Contiene i collegamenti (Link)
        self.last_update_time = time.time()

    def get_topology(self):
        """Recupera la lista degli switch"""
        try:
            url = f"{BASE_URL}/v1.0/topology/switches"
            response = requests.get(url)
            if response.status_code == 200:
                switches = response.json()
                for sw in switches:
                    dpid = sw['dpid']
                    if dpid not in self.network_data:
                        self.network_data[dpid] = {
                            "ports": {}, 
                            "last_seen": time.ctime()
                        }
                return True
        except Exception as e:
            print(f"Errore Topologia Switch: {e}")
        return False
    
    def get_links(self):
        """Recupera la lista dei collegamenti tra switch"""
        try:
            url = f"{BASE_URL}/v1.0/topology/links"
            response = requests.get(url)
            if response.status_code == 200:
                self.network_links = response.json()
                return True
        except Exception as e:
            print(f"Errore Topologia Link: {e}")
        return False

    def update_stats(self):
        """Recupera stats e CALCOLA la velocità (Bps)"""
        current_time = time.time()
        time_diff = current_time - self.last_update_time
        
        if time_diff < 0.1: return 

        for dpid in self.network_data:
            try:
                # Nota: l'API richiede il dpid in formato intero
                url = f"{BASE_URL}/stats/port/{int(dpid, 16)}"
                response = requests.get(url)
                
                if response.status_code == 200:
                    # La chiave nel JSON di risposta è l'intero convertito in stringa
                    key_str = str(int(dpid, 16))
                    if key_str in response.json():
                        stats_list = response.json()[key_str]
                        
                        for port in stats_list:
                            port_no = str(port['port_no'])
                            if port_no == 'LOCAL': continue 
                            
                            rx_now = port['rx_bytes']
                            tx_now = port['tx_bytes']
                            
                            # Dati precedenti
                            port_data = self.network_data[dpid]["ports"].get(port_no, {})
                            rx_prev = port_data.get("total_rx", rx_now)
                            tx_prev = port_data.get("total_tx", tx_now)
                            
                            # Calcolo Velocità
                            rx_speed = (rx_now - rx_prev) / time_diff
                            tx_speed = (tx_now - tx_prev) / time_diff
                            
                            # Aggiornamento dati
                            self.network_data[dpid]["ports"][port_no] = {
                                "total_rx": rx_now,
                                "total_tx": tx_now,
                                "speed_rx_bps": round(rx_speed, 2),
                                "speed_tx_bps": round(tx_speed, 2)
                            }
            except Exception as e:
                print(f"Errore Stats {dpid}: {e}")
        
        self.last_update_time = current_time

    def save_to_json(self):
        """Salva lo stato COMPLETO (Switch + Link) su file"""
        full_twin_data = {
            "timestamp": time.ctime(),
            "switches": self.network_data,
            "links": self.network_links
        }
        with open(OUTPUT_FILE, 'w') as f:
            json.dump(full_twin_data, f, indent=4)

    def display_console(self):
        os.system('clear') 
        print(f"--- DIGITAL TWIN MONITOR [Update ogni {POLLING_INTERVAL}s] ---")
        print(f"Status: {len(self.network_data)} Switch rilevati, {len(self.network_links)} Link attivi.\n")
        
        for dpid, data in self.network_data.items():
            print(f"SWITCH {dpid}")
            for p, p_data in data['ports'].items():
                rx_spd = p_data['speed_rx_bps']
                tx_spd = p_data['speed_tx_bps']
                print(f"   Porta {p}: RX {rx_spd} B/s  |  TX {tx_spd} B/s")
        print(f"\n[Dati salvati in {OUTPUT_FILE}]")

def main():
    twin = DigitalTwin()
    print("Avvio Digital Twin... Attendi il primo ciclo.")
    time.sleep(1)
    
    while True:
        # 1. Recupera la struttura fisica
        twin.get_topology()
        twin.get_links()
        
        # 2. Recupera i dati dinamici
        twin.update_stats()
        
        # 3. Salva e Mostra
        twin.save_to_json()   
        twin.display_console()
        
        # 4. Attendi
        time.sleep(POLLING_INTERVAL)

if __name__ == "__main__":
    main()
