from ryu.base import app_manager
from ryu.controller import ofp_event
from ryu.controller.handler import CONFIG_DISPATCHER, MAIN_DISPATCHER
from ryu.controller.handler import set_ev_cls
from ryu.ofproto import ofproto_v1_3
from ryu.lib.packet import packet
from ryu.lib.packet import ethernet
from ryu.lib.packet import ether_types
from ryu.lib.packet import ipv4
from ryu.lib.packet import arp

class CustomSwitch13(app_manager.RyuApp):
    """
    Ryu application that implements a learning switch with OpenFlow 1.3.
    It installs specific flows for IPv4 and ARP to allow the Digital Twin 
    to monitor traffic based on IP addresses.
    """
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]

    def __init__(self, *args, **kwargs):
        super(CustomSwitch13, self).__init__(*args, **kwargs)
        # mac_to_port[dpid][mac] = port
        self.mac_to_port = {}

    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def switch_features_handler(self, ev):
        """
        Invoked at switch connection. 
        Installs the table-miss flow entry to send unknown packets to the controller.
        """
        datapath = ev.msg.datapath
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        # Table-miss flow entry (Default: send everything to controller)
        match = parser.OFPMatch()
        actions = [parser.OFPActionOutput(ofproto.OFPP_CONTROLLER,
                                          ofproto.OFPCML_NO_BUFFER)]
        self.add_flow(datapath, 0, match, actions)

    def add_flow(self, datapath, priority, match, actions, buffer_id=None):
        """Helper to add a flow entry to the switch."""
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        inst = [parser.OFPInstructionActions(ofproto.OFPIT_APPLY_ACTIONS,
                                             actions)]
        if buffer_id:
            mod = parser.OFPFlowMod(datapath=datapath, buffer_id=buffer_id,
                                    priority=priority, match=match,
                                    instructions=inst)
        else:
            mod = parser.OFPFlowMod(datapath=datapath, priority=priority,
                                    match=match, instructions=inst)
        datapath.send_msg(mod)

    @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
    def _packet_in_handler(self, ev):
        """
        Handles packets sent to the controller.
        Learns the MAC address and installs specific IP/ARP flows.
        """
        msg = ev.msg
        datapath = msg.datapath
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        in_port = msg.match['in_port']

        pkt = packet.Packet(msg.data)
        eth = pkt.get_protocols(ethernet.ethernet)[0]

        # Ignore LLDP packets
        if eth.ethertype == ether_types.ETH_TYPE_LLDP:
            return

        dst = eth.dst
        src = eth.src
        dpid = datapath.id
        self.mac_to_port.setdefault(dpid, {})

        self.logger.info("PacketIn: DPID %s | %s -> %s (Port %s)", dpid, src, dst, in_port)

        # Learning MAC address
        self.mac_to_port[dpid][src] = in_port

        # Determine output port
        if dst in self.mac_to_port[dpid]:
            out_port = self.mac_to_port[dpid][dst]
        else:
            out_port = ofproto.OFPP_FLOOD

        actions = [parser.OFPActionOutput(out_port)]

        # Install Flow Mod if we are not flooding
        if out_port != ofproto.OFPP_FLOOD:
            pkt_ipv4 = pkt.get_protocol(ipv4.ipv4)
            pkt_arp = pkt.get_protocol(arp.arp)

            if pkt_ipv4:
                # IPV4 MATCH (Requires eth_type=0x0800)
                # Adding in_port ensures flow stability for monitoring
                match = parser.OFPMatch(
                    eth_type=ether_types.ETH_TYPE_IP,
                    ipv4_src=pkt_ipv4.src,
                    ipv4_dst=pkt_ipv4.dst,
                    in_port=in_port
                )
                self.logger.info("Installing IP Flow: %s (Port %s) -> %s", pkt_ipv4.src, in_port, pkt_ipv4.dst)
                self.add_flow(datapath, 10, match, actions, msg.buffer_id)
            
            elif pkt_arp:
                # ARP MATCH (Prevents excessive ARP PacketIn events)
                match = parser.OFPMatch(
                    eth_type=ether_types.ETH_TYPE_ARP,
                    arp_spa=pkt_arp.src_ip,
                    arp_tpa=pkt_arp.dst_ip,
                    in_port=in_port
                )
                self.add_flow(datapath, 5, match, actions, msg.buffer_id)
            
            else:
                # STANDARD L2 MATCH (Fallback)
                match = parser.OFPMatch(in_port=in_port, eth_dst=dst)
                self.add_flow(datapath, 1, match, actions, msg.buffer_id)

        # Send packet out
        data = None
        if msg.buffer_id == ofproto.OFP_NO_BUFFER:
            data = msg.data

        out = parser.OFPPacketOut(datapath=datapath, buffer_id=msg.buffer_id,
                                  in_port=in_port, actions=actions, data=data)
        datapath.send_msg(out)