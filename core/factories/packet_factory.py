#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""TECMP-Tool Packet Factory - Clean Minimal Version"""

import logging
from typing import Dict, Any, Optional, List

# Basic imports only
try:
    from core.packets.transport.udp import UDPPacket
    from core.packets.transport.tcp import TCPPacket
except ImportError:
    UDPPacket = None
    TCPPacket = None

try:
    from core.packets.tecmp.tecmp_packet import TECMPPacket
except ImportError:
    TECMPPacket = None

class PacketFactory:
    """Simple packet factory"""
    def __init__(self):
        self.logger = logging.getLogger("TECMP-Tool.PacketFactory")
    
    def create_packet(self, packet_type: str, **kwargs) -> Any:
        """Create a packet of specified type"""
        ptype = packet_type.lower()
        if ptype == 'tcp' and TCPPacket:
            return TCPPacket(**kwargs)
        elif ptype == 'udp' and UDPPacket:
            return UDPPacket(**kwargs)
        elif ptype == 'tecmp' and TECMPPacket:
            return TECMPPacket(**{k: v for k, v in kwargs.items() if k not in {"can_id", "lin_id", "frame_id", "cycle", "data", "ide", "rtr", "dlc", "wup", "sleep", "checksum", "tx", "ack", "err", "overflow"}})
        else:
            raise ValueError(f"Unknown or unavailable type: {packet_type}")

    def get_available_types(self) -> List[str]:
        """Get available packet types"""
        types = []
        if TCPPacket: types.append('tcp')
        if UDPPacket: types.append('udp')
        if TECMPPacket: types.append('tecmp')
        return types

def get_packet_registry():
    """Return empty registry for compatibility"""
    return {}

def create_tcp_packet(src_port: int, dst_port: int, **kwargs):
    """Create TCP packet"""
    if TCPPacket:
        return TCPPacket(src_port=src_port, dst_port=dst_port, **kwargs)
    raise ImportError("TCP packet not available")

def create_udp_packet(src_port: int, dst_port: int, **kwargs):
    """Create UDP packet"""
    if UDPPacket:
        return UDPPacket(src_port=src_port, dst_port=dst_port, **kwargs)
    raise ImportError("UDP packet not available")

# Exports
__all__ = [
    'PacketFactory',
    'get_packet_registry',
    'create_tcp_packet',
    'create_udp_packet'
]
