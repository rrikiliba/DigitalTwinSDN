from mininet.net import Mininet
from mininet.node import RemoteController, OVSKernelSwitch
from mininet.cli import CLI
from mininet.link import TCLink

def start_network (controller_ip = '127.0.0.1', controller_port = 6633):
   print (f"Avvio la Rete Twin (linear,2) controllata da {controller_ip}:{controller_port}...")
   
   net = Mininet(switch=OVSKernelSwitch)        #create mininet
   c1 = net.addController('c1',
                          controller=RemoteController,
                          ip=controller_ip,
                          port=controller_port) #controller add
   s1 = net.addSwitch('s1')
   s2 = net.addSwitch('s2')
   h1 = net.addHost('h1')
   h2 = net.addHost('h2')                       #add host and switches

   net.addLink(h1, s1)
   net.addLink(s1, s2)
   net.addLink(s2, h2)                          #add links

   net.build()
   net.start()                                  #net build
   
   return net

if __name__ == "__main__":

   twin_net = start_network()
   print("La Rete Twin è attiva. Digita 'exit' per uscire.")
   CLI (twin_net) 
   twin_net.stop()
