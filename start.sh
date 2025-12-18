#!/bin/bash
SESSION_NAME="DigitalTwinSDN"

sudo -v

# --- CONFIGURAZIONE COMANDI ---

# CMD1: Mininet (Il comando 'echo' simula la pressione del tasto Invio per l'input della topologia)
CMD1="sudo ./mininet.sh"

# CMD2: Manager Script (Aggiunto 'sleep 15' per aspettare che RYU si avvii bene)
CMD2="clear; echo 'Waiting for RYU...'; sleep 15; sudo python3 digital_twin.py"

# CMD3: Topology Checker (Aggiunto 'sleep 15')
CMD3="clear; echo 'Waiting for RYU...'; sleep 15; sudo python3 topology_checker.py"

# CMD4: Digital Twin Controller (Controller secondario per la rete ombra)
# Usiamo una porta OFP diversa (6634) per non andare in conflitto con quello principale
CMD4="clear; echo 'Twin Controller'; ryu-manager ryu.app.simple_switch_13 ryu.app.rest_topology --ofp-tcp-listen-port 6634 --observe-links"

# CMD5: Live Network Controller (QUELLO IMPORTANTE)
# Usa il comando che abbiamo verificato funzionare: porta API 6060
CMD5="clear; echo 'Live Controller'; ryu-manager ryu.app.simple_switch_13 ryu.app.ofctl_rest ryu.app.ws_topology ryu.app.rest_topology --wsapi-port 6060 --observe-links"

# --- AVVIO SESSIONE TMUX ---

# Either attach to tmux session or create it
tmux has-session -t $SESSION_NAME 2>/dev/null
if [ $? = 0 ]; then
  tmux attach-session -t $SESSION_NAME
  exit 0
fi
tmux new-session -d -s $SESSION_NAME

# Set a title for each pane
tmux set-option -t $SESSION_NAME status-position top
tmux set-window-option -t $SESSION_NAME pane-border-status top

# Set pane layout
tmux split-window -v -p 50
tmux select-pane -t 0
tmux split-window -h -t 0 -p 66
tmux select-pane -t 2
tmux split-window -h -t 2 -p 50
tmux select-pane -t 1
tmux split-window -h -p 50

# Set pane titles
tmux select-pane -t 0 -T "1. Mininet (Live Network)"
tmux select-pane -t 1 -T "2. Manager Script (Wait 15s)"
tmux select-pane -t 2 -T "3. Topology Checker (Wait 15s)"
tmux select-pane -t 3 -T "4. Twin Controller"
tmux select-pane -t 4 -T "5. Live RYU Controller (Port 6060)"

# Send the commands to the correct panes
tmux send-keys -t $SESSION_NAME:0.0 "$CMD1" C-m
tmux send-keys -t $SESSION_NAME:0.1 "$CMD2" C-m
tmux send-keys -t $SESSION_NAME:0.2 "$CMD3" C-m
tmux send-keys -t $SESSION_NAME:0.3 "$CMD4" C-m
tmux send-keys -t $SESSION_NAME:0.4 "$CMD5" C-m

# Attach to the session
tmux attach-session -t $SESSION_NAME
