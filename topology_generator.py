from mininet.net import Mininet
from mininet.node import RemoteController, OVSKernelSwitch
from mininet.cli import CLI
<<<<<<< HEAD
from mininet.log import setLogLevel

def start_network():
    setLogLevel('info')
    
    print("*** Creazione della Rete Twin (Linear, 2 Switch)...")
    print("-> Controller Remoto: 127.0.0.1:6633")
    
    # 1. Inizializza la rete con Switch OVS e Controller Remoto
    net = Mininet(switch=OVSKernelSwitch, controller=RemoteController)
    
    # 2. Aggiungi il Controller (deve corrispondere a RYU nel Terminale 1)
    c1 = net.addController('c1', ip='127.0.0.1', port=6633)
    
    # 3. Aggiungi Switch e Host
    s1 = net.addSwitch('s1')
    s2 = net.addSwitch('s2')
    h1 = net.addHost('h1', ip='10.0.0.1')
    h2 = net.addHost('h2', ip='10.0.0.2')
    
    # 4. Aggiungi i Link (Collegamenti)
    net.addLink(h1, s1)
    net.addLink(s1, s2)
    net.addLink(s2, h2)
    
    # 5. Avvia la rete
    print("*** Avvio della rete...")
    net.build()
    c1.start()
    s1.start([c1])
    s2.start([c1])
    
    print("*** Rete ATTIVA. Premi 'pingall' per testare o 'exit' per uscire.")
    CLI(net)
    
    print("*** Arresto della rete...")
    net.stop()

if __name__ == '__main__':
    start_network()
#=======
#from mininet.link import TCLink
#
#def start_network (controller_ip = '127.0.0.1', controller_port = 6633):
#   print (f"Avvio la Rete Twin (linear,2) controllata da {controller_ip}:{controller_port}...")
#   
#   net = Mininet(switch=OVSKernelSwitch)        #create mininet
#   c1 = net.addController('c1',
#                          controller=RemoteController,
#                          ip=controller_ip,
#                          port=controller_port) #controller add
#   s1 = net.addSwitch('s1')
#   s2 = net.addSwitch('s2')
#   h1 = net.addHost('h1')
#   h2 = net.addHost('h2')                       #add host and switches
#
#   net.addLink(h1, s1)
#   net.addLink(s1, s2)
#   net.addLink(s2, h2)                          #add links
#
#   net.build()
#   net.start()                                  #net build
#   
#   return net
#
#if __name__ == "__main__":
#
#   twin_net = start_network()
#   print("La Rete Twin è attiva. Digita 'exit' per uscire.")
#   CLI (twin_net) 
#   twin_net.stop()
#>>>>>>> fcea7fe0e9c48cd5dc71d6efa460faa77780cb7b
#
