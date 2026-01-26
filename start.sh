#!/bin/bash
SESSION_NAME="DigitalTwinSDN"

echo "[installing packages]"
pip install -r requirements.txt

echo "[starting session]"
sudo -v

# For each pane, clear and send the designated command
# 1: Mininet creation and terminal
CMD1="./mininet.sh"
# 2: DigitalTwin script 
CMD2="clear; sudo python3 digital_twin.py"
# 3: Check and print topology/network stats of the twin
CMD3="clear; sudo python3 twin_checker.py"
# 4: Twin ryu controller
CMD4="clear; ryu-manager ryu.app.simple_switch_13 ryu.app.rest_topology ryu.app.ofctl_rest --observe-links"
# 5: Live ryu controller
CMD5="clear; ryu-manager ryu.app.gui_topology ryu.app.ws_topology ryu.app.rest_topology ryu.app.ofctl_rest ryu.app.simple_switch_13 --wsapi-port 6060 --ofp-tcp-listen-port 6666 --observe-links"

# Either attach to tmux session or create it
tmux has-session -t $SESSION_NAME 2>/dev/null
if [ $? = 0 ]; then
  tmux attach-session -t $SESSION_NAME
  exit 0
fi
tmux new-session -d -s $SESSION_NAME

# Set a title for each pane, so that we know what we're looking at
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
tmux select-pane -t 0 -T "Mininet (for Live Network)"
tmux select-pane -t 1 -T "Digital Twin manager script"
tmux select-pane -t 2 -T "Digital Twin topology checker"
tmux select-pane -t 3 -T "Digital Twin ryu controller"
tmux select-pane -t 4 -T "Live Network ryu controller"

# Send the commands to the correct panes
tmux send-keys -t $SESSION_NAME:0.0 "$CMD1" C-m
tmux send-keys -t $SESSION_NAME:0.1 "$CMD2" C-m
tmux send-keys -t $SESSION_NAME:0.2 "$CMD3" C-m
tmux send-keys -t $SESSION_NAME:0.3 "$CMD4" C-m
tmux send-keys -t $SESSION_NAME:0.4 "$CMD5" C-m

# Attach to the session
tmux attach-session -t $SESSION_NAME
