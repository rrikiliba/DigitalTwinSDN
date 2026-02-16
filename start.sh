#!/bin/bash
SESSION_NAME="DigitalTwinSDN"

echo "[installing packages]"
pip install --disable-pip-version-check -r requirements.txt

echo "[starting session]"
sudo -v

run_mininet() {
    local prefix="sudo mn --controller=remote,ip=127.0.0.1:6666 --switch=ovs,protocols=OpenFlow13 --topo="
    local default_topo="linear,2"
    local input_topo

    # Clear the screen first
    clear

    # Prompt the user
    read -r -p "Enter your mininet topology (empty for default [$default_topo]): " input_topo

    # Execute with the user's input or the default
    if [[ -z "$input_topo" ]]; then
        $prefix$default_topo
    else
        $prefix$input_topo
    fi
}
export -f run_mininet

# Define commands for each pane
CMD1="run_mininet"
CMD2="clear; sudo python3 src/digital_twin.py"
CMD3="clear; sudo python3 src/utils/twin_checker.py"
CMD4="clear; sudo python3 src/utils/twin_checker.py 6060"
CMD5="clear; ryu-manager src/custom_switch_13.py ryu.app.rest_topology ryu.app.ofctl_rest --observe-links"
CMD6="clear; ryu-manager ryu.app.gui_topology ryu.app.ws_topology ryu.app.rest_topology ryu.app.ofctl_rest src/custom_switch_13.py --wsapi-port 6060 --ofp-tcp-listen-port 6666 --observe-links"

# Terminate previous session if found
tmux has-session -t $SESSION_NAME 2>/dev/null
if [ $? = 0 ]; then
  echo "Trovata una sessione precedente. La termino per ricaricare il nuovo layout..."
  tmux kill-session -t $SESSION_NAME
  sleep 1
fi

# Session setup
tmux new-session -d -s $SESSION_NAME
tmux set-option -t $SESSION_NAME status-position top
tmux set-window-option -t $SESSION_NAME pane-border-status top

# Panels setup
# ------------------------------------------
# -            -             -             -
# -     1      -             -             -
# -            -             -      5      -
# --------------             -             -
# -            -             -             -
# -     2      -      4      ---------------
# -            -             -             -
# --------------             -             -
# -            -             -      6      -
# -     3      -             -             -
# -            -             -             -
# ------------------------------------------


# Panel 1: mininet terminal for the live network
tmux select-pane -t $SESSION_NAME -T "Mininet (Live)"
tmux send-keys -t $SESSION_NAME "$CMD1" C-m

tmux split-window -t $SESSION_NAME -h -p 67
tmux split-window -t $SESSION_NAME -h -p 50

tmux split-window -t $SESSION_NAME -v -p 50

# Panel 6: twin network topology and traffic checker
tmux select-pane -t $SESSION_NAME -T "Digital Twin Checker"
tmux send-keys -t $SESSION_NAME "$CMD3" C-m

#Panel 5: Live Network Checker (top right)
tmux select-pane -t $SESSION_NAME -U
tmux select-pane -t $SESSION_NAME -T "Live Network Checker"
tmux send-keys -t $SESSION_NAME "$CMD4" C-m

# Panel 4: digital twin main script
tmux select-pane -t $SESSION_NAME -L
tmux select-pane -t $SESSION_NAME -T "Digital Twin Manager"
tmux send-keys -t $SESSION_NAME "$CMD2" C-m

tmux select-pane -t $SESSION_NAME -L
tmux split-window -t $SESSION_NAME -v -p 66

# Panel 2: ryu controller for the live network
tmux select-pane -t $SESSION_NAME -T "Live Ryu Controller"
tmux send-keys -t $SESSION_NAME "$CMD6" C-m

tmux split-window -t $SESSION_NAME -v -p 50

# Panel 3: ryu controller for the twin network
tmux select-pane -t $SESSION_NAME -T "Twin Ryu Controller"
tmux send-keys -t $SESSION_NAME "$CMD5" C-m

tmux attach-session -t $SESSION_NAME
