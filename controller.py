"""Minimal OpenFlow 1.3 controller for the D1 chat project.

The controller is intentionally scoped to D1:
- learns MAC addresses and forwards Ethernet traffic;
- identifies the project's TCP chat flow (destination/source TCP port 5000);
- logs chat-flow classification so socket traffic can be shown interacting
  with the SDN control plane.

This is not the D2 dynamic QoS/priority implementation yet.
"""

from __future__ import annotations

import logging
from typing import Dict

from os_ken.base import app_manager
from os_ken.controller import ofp_event
from os_ken.controller.handler import CONFIG_DISPATCHER, MAIN_DISPATCHER, set_ev_cls
from os_ken.lib.packet import ethernet, packet
from os_ken.lib.packet import ether_types
from os_ken.lib.packet import ipv4, tcp
from os_ken.ofproto import ofproto_v1_3

LOG = logging.getLogger("d1_chat_sdn")
CHAT_PORT = 5000


class ChatSDNController(app_manager.OSKenApp):
    """Learning-switch controller with TCP chat classification."""

    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.mac_to_port: Dict[int, Dict[str, int]] = {}
        LOG.info("D1 Chat SDN Controller started (OpenFlow 1.3, TCP port %s)", CHAT_PORT)

    def add_flow(self, datapath, priority, match, actions, idle_timeout=60):
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        instructions = [parser.OFPInstructionActions(ofproto.OFPIT_APPLY_ACTIONS, actions)]
        mod = parser.OFPFlowMod(
            datapath=datapath,
            priority=priority,
            idle_timeout=idle_timeout,
            match=match,
            instructions=instructions,
        )
        datapath.send_msg(mod)

    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def switch_features_handler(self, ev):
        datapath = ev.msg.datapath
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        # Table-miss: send unknown traffic to the controller.
        match = parser.OFPMatch()
        actions = [parser.OFPActionOutput(ofproto.OFPP_CONTROLLER, ofproto.OFPCML_NO_BUFFER)]
        self.add_flow(datapath, 0, match, actions, idle_timeout=0)

        self.mac_to_port.setdefault(datapath.id, {})
        LOG.info("Switch connected: dpid=%s", datapath.id)

    @staticmethod
    def is_chat_flow(ip_packet, tcp_packet) -> bool:
        return (
            ip_packet is not None
            and tcp_packet is not None
            and (tcp_packet.src_port == CHAT_PORT or tcp_packet.dst_port == CHAT_PORT)
        )

    @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
    def packet_in_handler(self, ev):
        msg = ev.msg
        datapath = msg.datapath
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        in_port = msg.match["in_port"]

        pkt = packet.Packet(msg.data)
        eth = pkt.get_protocol(ethernet.ethernet)

        if eth is None:
            return

        if eth.ethertype == ether_types.ETH_TYPE_LLDP:
            return

        dpid = datapath.id
        mac_table = self.mac_to_port.setdefault(dpid, {})
        mac_table[eth.src] = in_port

        ip_packet = pkt.get_protocol(ipv4.ipv4)
        tcp_packet = pkt.get_protocol(tcp.tcp)
        is_chat = self.is_chat_flow(ip_packet, tcp_packet)

        if is_chat:
            LOG.info(
                "[CHAT-TRAFFIC] dpid=%s %s:%s -> %s:%s",
                dpid,
                ip_packet.src,
                tcp_packet.src_port,
                ip_packet.dst,
                tcp_packet.dst_port,
            )

        out_port = mac_table.get(eth.dst, ofproto.OFPP_FLOOD)
        actions = [parser.OFPActionOutput(out_port)]

        if out_port != ofproto.OFPP_FLOOD:
            # Learned forwarding rule. Chat packets are given a higher priority
            # so the controller has an explicit classification path for the
            # application's TCP service.
            priority = 200 if is_chat else 100
            match_kwargs = {
                "in_port": in_port,
                "eth_src": eth.src,
                "eth_dst": eth.dst,
            }
            if is_chat:
                match_kwargs.update({"eth_type": ether_types.ETH_TYPE_IP, "ip_proto": 6})
                if tcp_packet.dst_port == CHAT_PORT:
                    match_kwargs["tcp_dst"] = CHAT_PORT
                else:
                    match_kwargs["tcp_src"] = CHAT_PORT

            self.add_flow(
                datapath,
                priority,
                parser.OFPMatch(**match_kwargs),
                actions,
            )

        data = None if msg.buffer_id != ofproto.OFP_NO_BUFFER else msg.data
        out = parser.OFPPacketOut(
            datapath=datapath,
            buffer_id=msg.buffer_id,
            in_port=in_port,
            actions=actions,
            data=data,
        )
        datapath.send_msg(out)
