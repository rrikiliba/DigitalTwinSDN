#!/bin/sh
# Aggiunto --switch ovsk,protocols=OpenFlow13 per parlare con Ryu
# Aggiunto --mac per avere indirizzi MAC semplici (00:00...01)
# Rimossa la porta :6666 per usare quella standard di Ryu
PREFIX="clear; sudo mn --controller=remote,ip=127.0.0.1 --switch ovsk,protocols=OpenFlow13 --mac --topo="
DEFAULT="linear,2"

read -r -p "Enter your mininet topology (empty for default topology): " INPUT ;
[ -z "$INPUT" ] && eval "$PREFIX$DEFAULT" || eval "$PREFIX$INPUT"
