# DigitalTwinSDN

This is the repository for the group project of the Networking (module 2) course at the University of Trento.

The topic that was chosen, among the available ones, is the Software Defined Digital Twin Network; as such, the objective is to create an environment with a Live Network, which symbolizes a real life network with varying topology and active traffic, and a twin Network. All changes in topology, as well as traffic on the Live net should be mirrored on the Twin.

The students responsible for this project are:

- [Enrico Comper](https://github.com/enricocomper)
- [Jacopo Scanavacca]()
- [Riccardo Libanora](https://github.com/rrikiliba)

## How it works

Using the comnetsemu environment, both Live and Twin network are created with their own ryu controller. The core of the project, on the other hand, is a python script that, thanks to the apps bundled with ryu itself, is able to:

- subscribe to the ryu RPC (over websocket) and provide callbacks to the topology update events that ryu generates (via ryu.app.ws_topology)
  - once parsed the event message, said callbacks can edit the Twin's topology to mirror any changes in the Live net (via the mininet python SDK)
  - by using this asyncronous method, we do not need to poll and compare the topology constantly
- regularly poll the traffic status of the Live net (via ryu.app.ofctl_rest)
  - and then reproduce it in the Twin net

## Getting started

Running the project is fairly simple. The following snippet should get you up and running.

```bash
# ssh into the comnetsemu virtual machine:
# if you're using vagrant, as recommended:
vagrant ssh comnetsemu
# clone this repo and access it
git clone https://github.com/rrikiliba/DigitalTwinSDN.git
cd DigitalTwinSDN
# use the `start` script: this will install any missing dependencies and start the whole environment inside a tmux session.
./start.sh 
# you will have total liberty on the network creation inside mininet, just type your desired topology in the top left panel
# with the same syntax you would use as command line argument for mininet itself (default is linear,2)
```

### What you see on screen

The script `start.sh` will take care of creating 5 individual tmux panels that contain the important components of the project. 

- Top left: mininet terminal. This panel is the only interactive one, as it allows the user to create and emulate the Live network. It will wait for user input to start, so that it allows for customization, as well as leaving some time for the other components to start up correctly
- top middle: digital twin script. The `digital_twin.py` python script is executed in this panel and its various logs can therefore be checked here. You will see the reception and parsing of the topology messages in real time, among other things
- top right: other logs. Using the `twin_checker.py` script, in this panel is generated a report of the current topology and traffic status of the Twin network, so that you can quickly check that any modifications you made to the Live net or any traffic you generated in it are correctly mirrored
- bottom left: Twin ryu controller. The ryu controller for the Twin network is run here, so any relevant logs can be checked in real time
- bottom right: Live ryu controller. The ryu controller for the Live network is run in this last panel
