Idea di base della struttura del progetto:

1: Mininet da simulare

mininet reale
mininet: controller=remote,ip=127.0.0.1,port=6633
ryu-manager: ryu-manager ryu.app.simple_switch_13 ryu.app.ofctl_rest ryu.app.rest_topology --ofp-tcp-listen-port 6633

2: Digital twin
mininet: da generare con prompt python, deve avere un controller a 127.0.0.1:6653
ryu-manager: ryu-manager ryu.app.simple_switch_13 ryu.app.ofctl_rest ryu.app.rest_topology  --ofp-tcp-listen-port 6653
