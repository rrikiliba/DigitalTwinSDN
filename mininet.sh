#!/bin/sh
PREFIX="clear; sudo mn --controller=remote,ip=127.0.0.1:6666 --topo="
DEFAULT="linear,2"

read -r -p "Enter your mininet topology (empty for default topology): " INPUT ; 
[ -z "$CMD1_IN" ] && eval "$PREFIX$DEFAULT" || eval "$PREFIX$INPUT"