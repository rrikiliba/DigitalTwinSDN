# DigitalTwinSDN

This repository contains the group project for the Networking (module 2) course at the University of Trento (A.Y. 2025/2026).

The objective is to develop a Software Defined Digital Twin Network. The system manages a "Live Network" (representing a real-world environment with dynamic topology and traffic) and a "Twin Network" that mirrors its state in real-time.

**Project Members:**
- Enrico Comper
- Jacopo Scanavacca
- Riccardo Libanora

## How it works

The project leverages the ComnetEmu environment and Ryu SDN controllers to synchronize two distinct emulated networks. The core logic is handled by a set of Python scripts that perform:

- **Topology Synchronization:** The system subscribes to Ryu RPC events via WebSockets (`ryu.app.ws_topology`). When a change is detected in the Live network, the `digital_twin.py` script uses the Mininet SDK to dynamically replicate the modification in the Twin.
- **Traffic Replication:** The `traffic.py` module polls the Live Controller's Flow Statistics every 2 seconds. It calculates the bandwidth consumption (`delta_bytes`) for active IPv4 flows and reproduces the load in the Twin using **unidirectional UDP streams via iperf**. This ensures the Twin reflects the real network's congestion without control-plane interference.

## UI Layout (Tmux)

The `start.sh` script automates the environment setup using a 5-panel Tmux layout:

- **Mininet CLI (Top Left):** The interactive terminal for the Live network. Type your desired topology here (e.g., `linear,2`, `ring,4`, or `tree,depth=2,fanout=3`).
- **Ryu Controllers (Bottom Left):** Two separate panels running the controllers for the Live (Port 6666) and Twin (Port 6060) networks.
- **Digital Twin Manager (Center):** Logs from `digital_twin.py` showing the parsing of topology events and RPC callbacks.
- **Digital Twin Checker (Right):** A live dashboard (`twin_checker.py`) that displays a side-by-side comparison of the topology and real-time traffic throughput measured in KB/s.

## Getting started

1. **SSH into the VM:**
   ```bash
   vagrant ssh comnetsemu
