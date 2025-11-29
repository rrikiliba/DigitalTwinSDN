# DigitalTwinSDN



Terminale 1: Lancio il controller con i moduli necessari per le API.

```bash
ryu-manager ryu.app.simple_switch_13 ryu.app.ofctl_rest ryu.app.rest_topology
```
- simple_switch_13: È lo switch vero e proprio, permette di scambiare pacchetti.
- ofctl_rest: Abilita le API per le statistiche (traffico/flussi).
- rest_topology: Abilita le API per la topologia (chi è collegato a chi).

Terminale 2:Mininet rete virtuale (2 host e 2 switch in linea).
Bash

```bash
sudo mn --controller=remote,ip=127.0.0.1 --topo=linear,2
```

Terminale 3: Il Digital Twin (Script Python) Questo è il terminale di controllo.
Test preliminare: Verifichiamo che il T3 parli con il T1 (Controller):
```bash
curl -X GET http://127.0.0.1:8080/v1.0/topology/switches
```
ESECUZIONE DEMO
Nel Terminale 3,  eseguo lo script che ho creato (digital_twin.py):

```bash
python3 digital_twin.py
```

IMPORTANTE:
ho aggiunto un script python per velocizzare la generazione della mininet, che parla con ryu sulla porta 6633, per maggiori info andate a vedere su
project_structure.md, in cui ho definito anche qualche dettaglio sul controller della SDN digital twin

